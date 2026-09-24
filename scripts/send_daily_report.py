#!/usr/bin/env python
"""把當日自動模擬交易日報送到 Telegram。

`--model` 選要送哪個模型的日報（兩本帳本各自獨立、平行跑）：
  pocket（預設）：舊三盤模型，🤖 三盤模型
  turtle        ：海龜投資法模型，🐢 海龜模型（不支援 image 版，強制退回 html）
標題一律帶模型標籤，避免兩邊日報混在同一個 Telegram 對話裡分不清是哪個模型送的。

三種版型（`--style`，turtle 只有 html/text）：
  image（預設）：Pillow 畫成日報圖，sendPhoto + 短 caption；找不到 CJK 字型時自動退回 html
  html         ：<pre> 等寬表格，sendMessage(parse_mode=HTML)
  text         ：純文字（舊版）

token/chat_id 取自環境變數 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
（Actions 走 secrets；本機可用 --token/--chat 覆寫）。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.services import auto_trade_service as ats     # noqa: E402
from api.services import turtle_trade_service as tts   # noqa: E402
from api.services import report_image                  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"


def send_html(token: str, chat: str, text: str) -> dict:
    r = httpx.post(API.format(token=token, method="sendMessage"), timeout=30.0,
                   data={"chat_id": chat, "text": text, "parse_mode": "HTML",
                         "disable_web_page_preview": "true"})
    return r.json()


def send_photo(token: str, chat: str, png: Path, caption: str) -> dict:
    with open(png, "rb") as f:
        r = httpx.post(API.format(token=token, method="sendPhoto"), timeout=60.0,
                       data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
                       files={"photo": (png.name, f, "image/png")})
    return r.json()


def build_caption(log: dict) -> str:
    yen = lambda v: f"¥{round(v or 0):,}"
    return (f"🤖 <b>三盤模型 自動模擬交易日報 {log.get('date')}</b>\n"
            f"總權益 {yen(log.get('equity_jpy'))}"
            f"（{(log.get('total_return_pct') or 0) * 100:+.2f}%）"
            f"｜進 {len(log.get('opened') or [])}｜出 {len(log.get('closed') or [])}"
            f"｜持倉 {log.get('open_count', 0)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="送出自動模擬交易日報到 Telegram")
    ap.add_argument("--model", choices=["pocket", "turtle"], default="pocket",
                    help="pocket=舊三盤模型（預設）／turtle=海龜投資法模型")
    ap.add_argument("--style", choices=["image", "html", "text"], default="image")
    ap.add_argument("--date", default="", help="日報日期 YYYY-MM-DD（預設最新一筆 log）")
    ap.add_argument("--token", default=os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    ap.add_argument("--chat", default=os.environ.get("TELEGRAM_CHAT_ID", ""))
    ap.add_argument("--out", default="", help="圖片輸出路徑（預設 data/auto_trade_log/report_<date>.png）")
    args = ap.parse_args()

    if not args.token or not args.chat:
        print("[telegram] 未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID → 略過")
        return 0

    svc = tts if args.model == "turtle" else ats

    d = args.date
    if not d:
        if args.model == "turtle":
            d = svc.latest_log_date()
        else:
            logs = svc.list_daily_logs(days=1)
            d = logs[0]["date"] if logs else None
        if not d:
            print("[telegram] 沒有任何每日 log")
            return 1
    log = svc.read_daily_log(d)
    if log is None:
        print(f"[telegram] 找不到 {d} 的 log")
        return 1

    style = args.style
    if args.model == "turtle" and style == "image":
        print("[telegram] 海龜模型日報不支援 image 版 → 退回 html")
        style = "html"
    if style == "image" and not report_image.has_cjk_font():
        print("[telegram] 找不到 CJK 字型 → 退回 html 版")
        style = "html"

    if style == "image":
        out = Path(args.out) if args.out else ats.DAILY_LOG_DIR / f"report_{d}.png"
        png = report_image.render_daily_report(log, ats.build_equity_curve(), out)
        res = send_photo(args.token, args.chat, png, build_caption(log))
        print(f"[telegram] sendPhoto {png} → ok={res.get('ok')} {res.get('description', '')}")
    elif style == "html":
        res = send_html(args.token, args.chat, svc.format_report_html(log))
        print(f"[telegram] sendMessage(HTML) → ok={res.get('ok')} {res.get('description', '')}")
    else:
        res = send_html(args.token, args.chat, svc.format_report(log))
        print(f"[telegram] sendMessage(text) → ok={res.get('ok')} {res.get('description', '')}")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
