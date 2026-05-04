"""定時健康檢查 worker — 簡單回 ok 字串給 scheduler 寫 log。"""
from datetime import datetime


def ping() -> dict:
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


def main():
    print(ping())


if __name__ == "__main__":
    main()
