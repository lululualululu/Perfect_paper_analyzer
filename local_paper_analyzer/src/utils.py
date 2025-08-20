import os, json, datetime, time
from typing import Dict, Any, Optional

def utc_minute_str(dt: datetime.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    dt_utc = dt.astimezone(datetime.timezone.utc)
    return dt_utc.strftime('%Y%m%d%H%M')

def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"processed_ids": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(path: str, state: Dict[str, Any]):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

import re, json as _json

def extract_json_block(s: str) -> dict:
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if not m: return {}
    blk = m.group(0)
    try: return _json.loads(blk)
    except Exception:
        blk2 = re.sub(r',\s*}', '}', blk); blk2 = re.sub(r',\s*]', ']', blk2)
        try: return _json.loads(blk2)
        except Exception: return {}

def update_progress(path: str, stage: str, current: Optional[int] = None, total: Optional[int] = None, note: str = ""):
    payload = {"stage": stage, "current": current, "total": total, "note": note, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] progress write failed: {e}")
