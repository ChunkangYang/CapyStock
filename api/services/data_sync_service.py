"""雲端同步服務（cloud-cache → cache）。

從 data.py router 搬移過來的同步邏輯 — router 與排程器（price_sync）共用同一實作，
不留兩條會 diverge 的 path。寫成**同步**函式（httpx.Client + ThreadPoolExecutor
並行下載），router 端用 asyncio.to_thread 包，排程器 handler 直接呼叫。

kinds 參數：
  None        → 全部 CSV + edinet_reports.json（Dashboard「雲端同步」按鈕全量行為）
  ["price"]   → 只處理 *_price.csv（GitHub 檔案列表與本地複製都只挑 price）
"""
from __future__ import annotations

import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import httpx

from capystock import config


def _parse_github_remote() -> tuple[str, str, str]:
    """解析 (owner, repo, branch)。優先讀 env var（Docker 友善）；
    fallback 解析 .git/config + .git/HEAD。"""
    env_repo = os.environ.get("CAPYSTOCK_GITHUB_REPO", "").strip()
    env_branch = os.environ.get("CAPYSTOCK_GITHUB_BRANCH", "").strip()
    if env_repo and env_branch and "/" in env_repo:
        owner, repo = env_repo.split("/", 1)
        return owner, repo, env_branch

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
    return owner, repo, m3.group(1)


def _wanted(name: str, kinds: Optional[list[str]]) -> bool:
    """檔名是否在本次同步範圍內。"""
    if kinds is None:
        return True
    if "price" in kinds and name.endswith("_price.csv"):
        return True
    if "margin" in kinds and name.endswith("_margin.csv"):
        return True
    return False


def run_cloud_sync(
    pull: bool = True,
    kinds: Optional[list[str]] = None,
    rescan: bool = True,
) -> dict:
    """同步雲端資料並（可選）重算訊號。同步函式，供 router（threadpool）與排程器共用。

    Raises: RuntimeError / httpx.HTTPError（呼叫端決定如何轉成 HTTP error）。
    """
    cloud_dir = config.PROJECT_ROOT / "data" / "cloud-cache"
    local_dir = config.CACHE_DIR
    local_dir.mkdir(parents=True, exist_ok=True)
    cloud_dir.mkdir(parents=True, exist_ok=True)

    pulled_info = None
    if pull:
        owner, repo, branch = _parse_github_remote()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/data/cloud-cache"
        headers = {"Accept": "application/vnd.github+json"}
        params = {"ref": branch}

        with httpx.Client(timeout=30.0) as client:
            r = client.get(api_url, params=params, headers=headers)
            if r.status_code == 404:
                raise RuntimeError("GitHub repo 上沒有 data/cloud-cache/ 目錄（先觸發一次 Cloud Fetch）")
            if r.status_code == 403:
                raise RuntimeError(f"GitHub API 拒絕（rate limit 或 private repo 需 token）: {r.text[:200]}")
            r.raise_for_status()
            files = r.json()
            if not isinstance(files, list):
                raise RuntimeError(f"GitHub API 回傳非預期格式: {str(files)[:200]}")

            # 只下載範圍內檔案（kinds=["price"] → 11k 檔縮到 3.7k）+ edinet_reports.json（全量時）
            targets = [
                f for f in files
                if _wanted(f["name"], kinds)
                or (kinds is None and f["name"] == "edinet_reports.json")
            ]

            def fetch_one(meta):
                name = meta["name"]
                dl = meta.get("download_url")
                if not dl:
                    return name, False, "no download_url"
                try:
                    resp = client.get(dl)
                    resp.raise_for_status()
                    (cloud_dir / name).write_bytes(resp.content)
                    return name, True, None
                except Exception as e:  # noqa: BLE001
                    return name, False, str(e)

            with ThreadPoolExecutor(max_workers=16) as ex:
                results = list(ex.map(fetch_one, targets))

        downloaded, dl_errors = [], []
        for name, ok, err in results:
            (downloaded if ok else dl_errors).append(name if ok else f"{name}: {err}")
        pulled_info = {
            "owner": owner, "repo": repo, "branch": branch,
            "downloaded": len(downloaded), "errors": dl_errors,
        }

    if not cloud_dir.exists():
        raise RuntimeError("data/cloud-cache 不存在，先在 GitHub 觸發一次 Cloud Fetch")

    copied, skipped = [], []
    for src in cloud_dir.glob("*.csv"):
        if not _wanted(src.name, kinds):
            continue
        try:
            shutil.copy2(src, local_dir / src.name)
            copied.append(src.name)
        except Exception as e:  # noqa: BLE001
            skipped.append({"file": src.name, "error": str(e)})

    if kinds is None:
        edinet_json = cloud_dir / "edinet_reports.json"
        if edinet_json.exists():
            try:
                shutil.copy2(edinet_json, local_dir / "edinet_reports.json")
                copied.append("edinet_reports.json")
            except Exception as e:  # noqa: BLE001
                skipped.append({"file": "edinet_reports.json", "error": str(e)})

    scan_summary = None
    if rescan:
        try:
            from api.services import scan_service as _scan_service
            from api.routers.scan import prime_live_signals_cache
            universe = _scan_service.load_universe()
            rows, errors = _scan_service.run_signals_scan(universe)
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            _scan_service.write_snapshot("signals", rows, today_str, guard=True)
            if errors:
                _scan_service.write_errors("signals", errors, today_str)
            prime_live_signals_cache(rows, errors, now)
            scan_summary = {"rows": len(rows), "errors": len(errors), "snapshot_date": today_str}
        except Exception as e:  # noqa: BLE001
            scan_summary = {"error": str(e)}

    return {
        "pulled": pulled_info,
        "copied_count": len(copied),
        "copied_sample": copied[:10],
        "skipped": skipped,
        "applied_to": str(local_dir),
        "rescan": scan_summary,
    }
