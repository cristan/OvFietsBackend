import threading
from typing import Optional
from google.cloud import firestore
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

db = firestore.Client()
flush_lock = threading.Lock()

# code -> month -> stats
historic_capacity_cache = {}
pending_historic_updates = {}

def get_three_month_max(code: str) -> int:
    months = get_recent_months(3)
    code_data = historic_capacity_cache.get(code, {})
    return max((code_data.get(m, {}).get("max", 0) for m in months), default=0)

def get_recent_months(n: int = 3, now: Optional[datetime] = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    return [
        (now - relativedelta(months=i)).strftime("%Y-%m")
        for i in range(n)
    ]

def get_current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")  # e.g., "2025-06"

def load_monthly_capacity_cache():
    print("Loading monthly capacity cache")
    months = get_recent_months(3)
    snapshot = db.collection("monthly_location_stats") \
        .where("month", "in", months) \
        .stream()

    cache = {}
    for doc in snapshot:
        data = doc.to_dict()
        code = data["code"]
        print(f"[{code}] Loaded from cache | month: {data['month']} | min: {data['min']} | max: {data['max']}")
        cache.setdefault(code, {})[data["month"]] = data

    global historic_capacity_cache
    historic_capacity_cache = cache
    print(f"Loaded {len(cache)} documents into capacity cache.")

def track_historic_capacity(code: str, capacity: int):
    current_month = get_current_month()

    if code not in historic_capacity_cache:
        historic_capacity_cache[code] = {}

    existing = historic_capacity_cache[code].get(current_month)
    if existing is None:
        # First update for this code – force write
        new_min = new_max = capacity
    else:
        old_min = existing["min"]
        old_max = existing["max"]

        # Not more or less than the previous min and max: skip.
        if old_min <= capacity <= old_max:
            return

        new_min = min(old_min, capacity)
        new_max = max(old_max, capacity)

    updated = {
        "code": code,
        "month": current_month,
        "min": new_min,
        "max": new_max,
    }

    with flush_lock:
        historic_capacity_cache[code][current_month] = updated
        pending_historic_updates[code] = updated

    print(f"[{code}] Queued monthly update with min: {new_min}, max: {new_max}")

def flush_pending_updates():
    with flush_lock:
        if not pending_historic_updates:
            return

        batch = db.batch()

        # Monthly updates
        for code, data in pending_historic_updates.items():
            doc_id = f"{code}_{data['month']}"
            ref = db.collection("monthly_location_stats").document(doc_id)
            batch.set(ref, data)

        batch.commit()
        print(f"✅ Flushed {len(pending_historic_updates)} historic document(s) at {datetime.now(timezone.utc).isoformat()}")

        pending_historic_updates.clear()

def prune_old_months():
    valid_months = set(get_recent_months(3))
    for code in list(historic_capacity_cache.keys()):
        for month in list(historic_capacity_cache[code].keys()):
            if month not in valid_months:
                del historic_capacity_cache[code][month]