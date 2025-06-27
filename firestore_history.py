import threading
from typing import Dict
from datetime import datetime
from google.cloud import firestore
from datetime import datetime, timedelta

db = firestore.Client()
flush_lock = threading.Lock()

historic_capacity_cache = {}
pending_historic_updates = {}

hourly_min_cache = {}
pending_hourly_updates = {}

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

def track_historic_capacity(code: str, capacity: int):
    current_month = get_current_month()
    existing = historic_capacity_cache.get(code)

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
        historic_capacity_cache[code] = updated
        pending_historic_updates[code] = updated

    print(f"[{code}] Queued monthly update with min: {new_min}, max: {new_max}")

def track_hourly_capacity(code: str, capacity: int):
    now = datetime.utcnow()
    hour_key = now.strftime("%Y-%m-%dT%H")
    ttl = now + timedelta(days=8)

    previous = hourly_min_cache.get(code)

    if (previous is None or
            previous["hour"] != hour_key or
            capacity < previous["min"]):

        hourly_min_cache[code] = {"hour": hour_key, "min": capacity}

        doc_id = f"{code}_{hour_key}"
        pending_hourly_updates[doc_id] = {
            "code": code,
            "hour": hour_key,
            "ttl": ttl,
            "min": capacity,
        }

def flush_pending_updates():
    with flush_lock:
        if not pending_historic_updates and not pending_hourly_updates:
            return

        batch = db.batch()

        # Monthly updates
        for code, data in pending_historic_updates.items():
            doc_id = f"{code}_{data['month']}"
            ref = db.collection("monthly_location_stats").document(doc_id)
            batch.set(ref, data)

        # Hourly updates
        for doc_id, data in pending_hourly_updates.items():
            ref = db.collection("hourly_location_capacity").document(doc_id)
            batch.set(ref, data)

        batch.commit()
        print(f"✅ Flushed {len(pending_historic_updates)} historic document(s) and {len(pending_hourly_updates)} hourly updates at {datetime.utcnow().isoformat()}")

        pending_historic_updates.clear()
        pending_hourly_updates.clear()