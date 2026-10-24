import gzip
import json
import os
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import storage

from history_changes import Change, Publication, add_reading, changes_for_recent_history, changes_in_effect_since, \
    codes_to_publish, from_json, location_file_max_age_minutes, location_history_minutes, merge_changes, to_json

recent_history_blob_name = "recent_history.json"

changes_per_code: dict[str, list[Change]] = {}
publications: dict[str, Publication] = {}
has_changes_since_recent_history_upload = False

def public_bucket() -> storage.Bucket:
    return storage.Client().bucket(os.getenv("PUBLIC_BUCKET_NAME"))

def location_history_blob_name(code: str) -> str:
    return f"history/{code}.json"

def upload_history_file(bucket: storage.Bucket, blob_name: str, data: Any, cache_control: str):
    blob = bucket.blob(blob_name)
    blob.cache_control = cache_control
    blob.content_encoding = "gzip"
    blob.upload_from_string(gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8")), content_type="application/json")

def download_json(bucket: storage.Bucket, blob_name: str) -> Any:
    try:
        return json.loads(bucket.blob(blob_name).download_as_bytes())
    except NotFound:
        return None

def load_recent_history():
    recent_history = download_json(public_bucket(), recent_history_blob_name) or {}
    changes_per_code.update({code: from_json(history) for code, history in recent_history.items()})
    print(f"Loaded the recent history of {len(recent_history)} locations")

def track_rental_bikes(code: str, fetch_time: int, rental_bikes: int):
    global has_changes_since_recent_history_upload
    changes = changes_per_code.get(code, [])
    changes_with_reading = add_reading(changes, fetch_time, rental_bikes)
    if changes_with_reading != changes:
        changes_per_code[code] = changes_with_reading
        has_changes_since_recent_history_upload = True

def publish_location_history(bucket: storage.Bucket, code: str, now_epoch_minute: int):
    published_history = download_json(bucket, location_history_blob_name(code))
    published_changes = [] if published_history is None else from_json(published_history)
    changes = changes_in_effect_since(merge_changes(published_changes, changes_per_code[code]), now_epoch_minute - location_history_minutes)
    upload_history_file(bucket, location_history_blob_name(code), to_json(changes), f"public, max-age={location_file_max_age_minutes * 60}")
    publications[code] = Publication(now_epoch_minute, changes_per_code[code][-1])

def publish_history(now_epoch_minute: int):
    global has_changes_since_recent_history_upload
    bucket = public_bucket()
    codes = codes_to_publish(changes_per_code, publications, now_epoch_minute)
    for code in codes:
        publish_location_history(bucket, code, now_epoch_minute)
    for code, changes in changes_per_code.items():
        changes_per_code[code] = changes_for_recent_history(changes, publications.get(code), now_epoch_minute)
    if has_changes_since_recent_history_upload:
        recent_history = {code: to_json(changes) for code, changes in changes_per_code.items()}
        upload_history_file(bucket, recent_history_blob_name, recent_history, "public, max-age=60")
        has_changes_since_recent_history_upload = False
        print(f"Uploaded {recent_history_blob_name} with {len(recent_history)} locations")
    if codes:
        print(f"Uploaded the history of {', '.join(codes)}")
