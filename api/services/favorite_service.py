"""我的最愛服務。"""
from datetime import datetime
from pathlib import Path
import json
import tempfile
from typing import Optional

from capystock import config


def _get_favorites_path() -> Path:
    """取得 favorites.json 路徑。"""
    data_dir = config.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "favorites.json"


def load() -> dict[str, dict]:
    """載入所有最愛。"""
    path = _get_favorites_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data: dict[str, dict]) -> None:
    """原子寫入 favorites.json（先寫 temp 再 replace）。"""
    path = _get_favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 使用臨時檔案確保原子寫入
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    # 原子替換
    tmp_path.replace(path)


def add(code: str, tag: str, name: str = "") -> dict:
    """加入或更新最愛（合併 tag）。"""
    fav = load()

    if code not in fav:
        fav[code] = {
            "code": code,
            "name": name,
            "tags": [],
            "added_at": datetime.now().isoformat(),
            "note": "",
        }

    # 合併 tag（避免重複，保持順序）
    tags = fav[code]["tags"]
    if tag not in tags:
        tags.append(tag)
        tags.sort()  # 固定順序
        fav[code]["tags"] = tags

    # 更新名稱（如果提供）
    if name:
        fav[code]["name"] = name

    _save(fav)
    return fav[code]


def remove(code: str, tag: Optional[str] = None) -> bool:
    """移除最愛。若指定 tag 則只移除該 tag；若 tag=None 則整筆刪除。"""
    fav = load()

    if code not in fav:
        return False

    if tag is None:
        # 整筆刪除
        del fav[code]
    else:
        # 只移除該 tag
        tags = fav[code]["tags"]
        if tag in tags:
            tags.remove(tag)
            if not tags:
                # 沒有 tag 了，整筆刪除
                del fav[code]
            else:
                fav[code]["tags"] = tags
        else:
            return False

    _save(fav)
    return True


def set_note(code: str, note: str) -> Optional[dict]:
    """設定備註。"""
    fav = load()

    if code not in fav:
        return None

    fav[code]["note"] = note
    _save(fav)
    return fav[code]


def list_favorites(tag: Optional[str] = None) -> list[dict]:
    """列出最愛。可選 tag 過濾。"""
    fav = load()
    result = []

    for entry in fav.values():
        if tag is None or tag in entry["tags"]:
            result.append(entry)

    # 按 added_at 逆序
    result.sort(key=lambda x: x["added_at"], reverse=True)
    return result
