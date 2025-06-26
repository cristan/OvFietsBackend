import threading
from typing import Dict
from datetime import datetime
from google.cloud import firestore

db = firestore.Client()
flush_lock = threading.Lock()

pending_updates = {}
capacity_cache = {}

def get_current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")  # e.g., "2025-06"

def load_monthly_capacity_cache() -> Dict[str, dict]:
    current_month = get_current_month()
    snapshot = db.collection("monthly_location_stats") \
        .where("month", "==", current_month) \
        .get()

    cache = {}
    for doc in snapshot:
        data = doc.to_dict()
        code = data["code"]
        print(f"[{code}] Loaded from cache | month: {data['month']} | min: {data['min']} | max: {data['max']}")
        cache[code] = data

    print(f"Loaded {len(cache)} documents into capacity cache.")
    return cache

def history_set_capacity(code: str, capacity: int):
    current_month = get_current_month()
    existing = capacity_cache.get(code)

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
        capacity_cache[code] = updated
        pending_updates[code] = updated

    print(f"[{code}] Queued update with min: {new_min}, max: {new_max}")

def flush_pending_updates():
    with flush_lock:
        if not pending_updates:
            return

        batch = db.batch()
        for code, data in pending_updates.items():
            doc_id = f"{code}_{data['month']}"
            ref = db.collection("monthly_location_stats").document(doc_id)
            batch.set(ref, data)

        batch.commit()
        print(f"✅ Flushed {len(pending_updates)} document(s) at {datetime.utcnow().isoformat()}")

        pending_updates.clear()