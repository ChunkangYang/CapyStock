"""S13 — Docker smoke test。

build image → run container → 30 秒內 /api/v1/health 回 200 → 清理。

需要 docker daemon。沒有 docker 時自動 skip。
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import time
import uuid
from contextlib import closing

import httpx
import pytest


IMAGE_TAG = "capystock:smoke-test"
CONTAINER_NAME = f"capystock-smoke-{uuid.uuid4().hex[:8]}"
HEALTH_URL_PATH = "/api/v1/health"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=5, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="docker daemon 未啟動（CI/本機 docker 不可用，跳過 e2e smoke）",
)


@pytest.fixture(scope="module")
def built_image():
    proc = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, timeout=900,
    )
    if proc.returncode != 0:
        pytest.fail(f"docker build 失敗：\n{proc.stderr[-2000:]}")
    yield IMAGE_TAG
    subprocess.run(["docker", "rmi", "-f", IMAGE_TAG], capture_output=True)


@pytest.fixture
def running_container(built_image):
    port = _free_port()
    proc = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-p", f"{port}:8000",
            "-e", "CAPYSTOCK_SCHEDULER_DISABLED=1",
            built_image,
        ],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail(f"docker run 失敗：{proc.stderr}")
    try:
        yield port
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)


def test_health_returns_200_within_30s(running_container):
    port = running_container
    url = f"http://127.0.0.1:{port}{HEALTH_URL_PATH}"
    deadline = time.time() + 30
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
            last_err = f"status={r.status_code} body={r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.0)
    pytest.fail(f"30 秒內未拿到 200，最後錯誤：{last_err}")
