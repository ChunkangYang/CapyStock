"""資料管理 API：cache 概覽 + 批量 ingest + SSE。"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.ingest_service import IngestService, _cache_age, _cache_path, _load_meta
from api.services.scan_service import load_universe
from capystock import config, storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])
_svc = IngestService()

# in-memory 批量 job 狀態
_batch_jobs: dict[str, dict] = {}


class CacheOverviewRow(BaseModel):
    code: str
    name: str
    price_age_days: Optional[int] = None
    margin_age_days: Optional[int] = None
    flow_age_days: Optional[int] = None
    fundamental_age_days: Optional[int] = None


class BatchIngestRequest(BaseModel):
    codes: List[str]
    kinds: List[str]


class UniverseStock(BaseModel):
    code: str
    name: str
    market: str = ""


@router.get("/universe-list", response_model=List[UniverseStock])
async def universe_list():
    """回傳全市場股票清單（從 universe.csv）。"""
    try:
        rows = load_universe()
        return [UniverseStock(code=str(r["code"]), name=str(r.get("name", "")), market=str(r.get("market", ""))) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", response_model=List[CacheOverviewRow])
async def data_overview(scope: str = "watchlist"):
    """取得各 code 各 kind 的 cache 狀態。"""
    wl = storage.load_watchlist()
    codes = [item.get("code", "") for item in wl] if isinstance(wl, list) else list(wl.keys())

    rows = []
    for code in codes:
        name = ""
        if isinstance(wl, list):
            entry = next((w for w in wl if w.get("code") == code), {})
            name = entry.get("name", code)
        else:
            name = wl.get(code, {}).get("name", code)

        def age(kind: str) -> Optional[int]:
            td = _cache_age(code, kind)
            return td.days if td is not None else None

        rows.append(CacheOverviewRow(
            code=code, name=name,
            price_age_days=age("price"),
            margin_age_days=age("margin"),
            flow_age_days=age("flow"),
            fundamental_age_days=age("fundamental"),
        ))
    return rows


@router.post("/batch-ingest", response_model=dict)
async def batch_ingest(req: BatchIngestRequest):
    """批量觸發 ingest；回傳 job_id（使用 SSE 追蹤進度）。"""
    job_id = str(uuid.uuid4())
    tasks = [(code, kind) for code in req.codes for kind in req.kinds]
    _batch_jobs[job_id] = {
        "status": "running",
        "total": len(tasks),
        "done": 0,
        "results": [],
        "tasks": tasks,
    }
    # 同步執行（後端 asyncio task）
    asyncio.create_task(_run_batch(job_id, tasks))
    return {"job_id": job_id, "total": len(tasks)}


async def _run_batch(job_id: str, tasks: list[tuple[str, str]]):
    job = _batch_jobs[job_id]
    for code, kind in tasks:
        try:
            if kind == "margin":
                result = _svc.fetch_margin(code, force=True)
            elif kind == "flow":
                result = _svc.fetch_flow(code, force=True)
            else:
                result = None

            job["results"].append({
                "code": code, "kind": kind,
                "ok": result.ok if result else False,
                "source": result.source if result else "n/a",
                "rows": result.rows_fetched if result else 0,
                "error": result.error if result else None,
            })
        except Exception as e:
            job["results"].append({
                "code": code, "kind": kind, "ok": False, "error": str(e), "source": "error", "rows": 0,
            })
        job["done"] += 1
        await asyncio.sleep(0)

    job["status"] = "completed"


@router.get("/batch-ingest/{job_id}/stream")
async def batch_ingest_stream(job_id: str):
    """SSE 進度串流。"""
    if job_id not in _batch_jobs:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_gen():
        for _ in range(300):
            job = _batch_jobs.get(job_id)
            if not job:
                break
            import json
            yield f"data: {json.dumps({'done': job['done'], 'total': job['total'], 'status': job['status']})}\n\n"
            if job["status"] == "completed":
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/batch-ingest/{job_id}", response_model=dict)
async def get_batch_job(job_id: str):
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/cloud-sync/status")
async def cloud_sync_status():
    """回傳雲端 cache 狀態（從 data/cloud-cache/_fetch_report.json 讀）。"""
    import json

    cache_dir = config.PROJECT_ROOT / "data" / "cloud-cache"
    report_path = cache_dir / "_fetch_report.json"

    if not report_path.exists():
        return {"available": False, "message": "尚未從雲端拉取過資料"}

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        csv_files = sorted([p.name for p in cache_dir.glob("*.csv")])
        return {
            "available": True,
            "ended_utc": report.get("ended_utc"),
            "summary": report.get("summary", {}),
            "kinds": report.get("kinds", []),
            "files_count": len(csv_files),
            "files_sample": csv_files[:10],
        }
    except Exception as e:
        return {"available": False, "message": f"報告檔解析失敗: {e}"}


class CloudSyncRequest(BaseModel):
    pull: bool = True  # True=從 GitHub 下載最新；False=只套用現有 cloud-cache 到 cache


def _parse_github_remote() -> tuple[str, str, str]:
    """解析 (owner, repo, branch)。
    優先讀 env var（Docker 友善）；fallback 解析 .git/config + .git/HEAD。
      CAPYSTOCK_GITHUB_REPO=owner/repo
      CAPYSTOCK_GITHUB_BRANCH=feature/s25-portfolio
    """
    import os
    import re

    env_repo = os.environ.get("CAPYSTOCK_GITHUB_REPO", "").strip()
    env_branch = os.environ.get("CAPYSTOCK_GITHUB_BRANCH", "").strip()
    if env_repo and env_branch and "/" in env_repo:
        owner, repo = env_repo.split("/", 1)
        return owner, repo, env_branch

    # fallback: 從 .git/ 解析（非 docker 情境）
    git_dir = config.PROJECT_ROOT / ".git"
    cfg = git_dir / "config"
    head = git_dir / "HEAD"
    if not cfg.exists() or not head.exists():
        raise RuntimeError(
            "找不到 .git/config 或 .git/HEAD。"
            "若在 Docker 內執行，請在 docker-compose.yml 設定 env："
            "CAPYSTOCK_GITHUB_REPO=<owner>/<repo>、CAPYSTOCK_GITHUB_BRANCH=<branch>"
        )

    cfg_text = cfg.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"\[remote\s+\"origin\"\][^\[]*?url\s*=\s*(\S+)", cfg_text)
    if not m:
        raise RuntimeError("找不到 origin remote")
    url = m.group(1).strip()
    m2 = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
    if not m2:
        raise RuntimeError(f"無法解析 GitHub repo: {url}")
    owner, repo = m2.group(1), m2.group(2)

    head_text = head.read_text(encoding="utf-8").strip()
    m3 = re.match(r"ref:\s*refs/heads/(.+)$", head_text)
    if not m3:
        raise RuntimeError(f"HEAD 處於 detached 狀態：{head_text}")
    branch = m3.group(1)
    return owner, repo, branch


@router.post("/cloud-sync")
async def cloud_sync(req: CloudSyncRequest):
    """從雲端同步資料（用 GitHub API，不依賴本機 git CLI）：
    1. (可選) GitHub Contents API 列出 data/cloud-cache/，並行下載 -> data/cloud-cache/
    2. 複製 data/cloud-cache/*.csv -> data/cache/*.csv
    """
    import asyncio
    import shutil

    import httpx

    cloud_dir = config.PROJECT_ROOT / "data" / "cloud-cache"
    local_dir = config.CACHE_DIR
    local_dir.mkdir(parents=True, exist_ok=True)
    cloud_dir.mkdir(parents=True, exist_ok=True)

    pulled_info = None
    if req.pull:
        try:
            owner, repo, branch = _parse_github_remote()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"解析 git config 失敗: {e}")

        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/data/cloud-cache"
        headers = {"Accept": "application/vnd.github+json"}
        params = {"ref": branch}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(api_url, params=params, headers=headers)
                if r.status_code == 404:
                    raise HTTPException(status_code=404, detail="GitHub repo 上沒有 data/cloud-cache/ 目錄（先觸發一次 Cloud Fetch）")
                if r.status_code == 403:
                    raise HTTPException(status_code=403, detail=f"GitHub API 拒絕（rate limit 或 private repo 需 token）: {r.text[:200]}")
                r.raise_for_status()
                files = r.json()
                if not isinstance(files, list):
                    raise HTTPException(status_code=500, detail=f"GitHub API 回傳非預期格式: {str(files)[:200]}")

                # 並行下載所有檔案
                async def fetch_one(meta):
                    name = meta["name"]
                    dl = meta.get("download_url")
                    if not dl:
                        return name, False, "no download_url"
                    resp = await client.get(dl)
                    resp.raise_for_status()
                    (cloud_dir / name).write_bytes(resp.content)
                    return name, True, None

                results = await asyncio.gather(*(fetch_one(f) for f in files), return_exceptions=True)

            downloaded, dl_errors = [], []
            for res in results:
                if isinstance(res, Exception):
                    dl_errors.append(str(res))
                    continue
                name, ok, err = res
                if ok:
                    downloaded.append(name)
                else:
                    dl_errors.append(f"{name}: {err}")

            pulled_info = {
                "owner": owner, "repo": repo, "branch": branch,
                "downloaded": len(downloaded), "errors": dl_errors,
            }
        except HTTPException:
            raise
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"GitHub API 失敗: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"pull error: {e}")

    if not cloud_dir.exists():
        raise HTTPException(status_code=404, detail="data/cloud-cache 不存在，先在 GitHub 觸發一次 Cloud Fetch")

    copied = []
    skipped = []
    for src in cloud_dir.glob("*.csv"):
        dst = local_dir / src.name
        try:
            shutil.copy2(src, dst)
            copied.append(src.name)
        except Exception as e:
            skipped.append({"file": src.name, "error": str(e)})

    return {
        "pulled": pulled_info,
        "copied_count": len(copied),
        "copied_sample": copied[:10],
        "skipped": skipped,
        "applied_to": str(local_dir),
    }


@router.get("/latest-price/{code}")
async def get_latest_price(code: str):
    """只讀 cache，回傳最新收盤價。不發網路請求。"""
    import pandas as pd
    cache = _cache_path(code, "price")
    if not cache.exists():
        raise HTTPException(status_code=404, detail="no price cache")
    try:
        df = pd.read_csv(cache)
        if df.empty or "close" not in df.columns:
            raise HTTPException(status_code=404, detail="no close data")
        latest = float(df.iloc[-1]["close"])
        return {"code": code, "close": latest, "date": str(df.iloc[-1].get("date", ""))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
