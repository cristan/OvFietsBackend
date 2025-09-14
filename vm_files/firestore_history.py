import threading
from typing import Dict
from google.cloud import firestore
from datetime import datetime, timedelta, timezone

db = firestore.Client()
flush_lock = threading.Lock()

historic_capacity_cache = {}
pending_historic_updates = {}

hourly_first_seen_cache = {} # code => the last hour for which we have set `min`: the first value we have received for this location
pending_hourly_updates = {}

def load_latest_hours_per_code():
    print("Loading hourly capacity cache")
    snapshot = db.collection("hourly_location_capacity").stream()

    latest_per_code: Dict[str, str] = {}

    for doc in snapshot:
        data = doc.to_dict()
        code = data.get("code")
        hour = data.get("hour")

        if not code or not hour:
            continue  # skip incomplete docs

        # Keep only the latest hour per code
        if code not in latest_per_code or hour > latest_per_code[code]:
            latest_per_code[code] = hour

    global hourly_first_seen_cache
    hourly_first_seen_cache = latest_per_code
    print(f"Loaded {len(latest_per_code)} entries into hourly_first_seen_cache.")

def get_current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")  # e.g., "2025-06"

def load_monthly_capacity_cache():
    print("Loading monthly capacity cache")
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

    global historic_capacity_cache
    historic_capacity_cache = cache
    print(f"Loaded {len(cache)} documents into capacity cache.")

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
    now = datetime.now(timezone.utc)
    hour_key = now.strftime("%Y-%m-%dT%H")  # e.g., 2025-06-28T14 Note that this is UTC, not Dutch time!

    # Only write if we haven’t written for this code during this hour
    previous_hour = hourly_first_seen_cache.get(code)
    if previous_hour == hour_key:
        return

    hourly_first_seen_cache[code] = hour_key

    ttl = now + timedelta(days=8)
    doc_id = f"{code}_{hour_key}"

    pending_hourly_updates[doc_id] = {
        "code": code,
        "hour": hour_key,
        "first": capacity,
        "ttl": ttl,
        "timestamp": now,
    }

    print(f"[{code}] ⏱ First hourly capacity logged: {capacity} for hour {hour_key} at {now}")

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