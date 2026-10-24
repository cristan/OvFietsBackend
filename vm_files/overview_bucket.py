import os
import time
from typing import Any

combined_data = {}

import io
import gzip
import json
from google.cloud import storage

def create_gzipped_json(locations: list[dict[str, Any]]) -> bytes:
    # Convert the data to JSON
    json_bytes = json.dumps(
        locations, ensure_ascii=False
    ).encode("utf-8")

    # Gzip in memory
    return gzip.compress(json_bytes)

def upload_gzipped_json(gzipped_json: bytes, destination_blob_name: str):
    client = storage.Client()
    bucket_name = os.getenv("PUBLIC_BUCKET_NAME")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload to GCS
    blob.cache_control = "no-cache, max-age=0"
    blob.content_encoding = "gzip"
    blob.content_type = "application/json"
    blob.metadata = {"minimum-app-compatibility": "1"}
    blob.upload_from_file(io.BytesIO(gzipped_json))

    print(f"Uploaded {destination_blob_name} to {bucket_name} (gzip-compressed)")

def write_gzipped_json(gzipped_json: bytes, path: str):
    temporary_path = path + ".tmp"
    with open(temporary_path, "wb") as file:
        file.write(gzipped_json)
    os.replace(temporary_path, path)

    print(f"Wrote {path}")

def publish_combined_data():
    gzipped_json = create_gzipped_json(list(combined_data.values()))
    public_directory = os.getenv("PUBLIC_DIRECTORY")
    if public_directory is None:
        upload_gzipped_json(gzipped_json, "locations.json")
    else:
        write_gzipped_json(gzipped_json, os.path.join(public_directory, "locations.json.gz"))

def filter_old_entries():
    twoWeeksAgo = int(time.time()) - (14 * 24 * 60 * 60)

    # Collect keys to remove (can't modify dict while iterating)
    keys_to_remove = []

    for location_code, data in combined_data.items():
        fetch_time = data["extra"].get("fetchTime")

        if fetch_time < twoWeeksAgo:
            keys_to_remove.append(location_code)

    # Remove the old entries
    for key in keys_to_remove:
        del combined_data[key]
        print(f"Removed old location data: {key}")

def get_useful_data(entry: dict[str, Any], three_month_max: int) -> dict[str, Any]:
    useful_data = {
        # strip because Duiven has a space at the end of its description.
        'description': entry.get('description', '').strip(),
        'stationCode': entry.get('stationCode'),

        'city': entry.get('city'),
        'postalCode': entry.get('postalCode'),
        'street': entry.get('street'),
        'houseNumber': entry.get('houseNumber'),

        'lat': entry.get('lat'),
        'lng': entry.get('lng'),

        'link': {'uri': entry['link']['uri']},
        'extra': {
            'locationCode': entry['extra']['locationCode'],
            'fetchTime': entry['extra']['fetchTime'],
            # Not always present, but we filter out entries without it beforehand
            'rentalBikes': entry['extra']['rentalBikes']
        },
        'infoImages': [
            {
                "title": img["title"],
                "body": img["body"],
            }
            for img in entry.get("infoImages", [])
            if img.get("title") != "Zelfservice huurlocatie"
        ],
        'openingHours': entry.get('openingHours'),
        'maxCapacity': three_month_max
    }

    if 'serviceType' in entry['extra']:
        useful_data['extra']['serviceType'] = entry['extra']['serviceType']

    return useful_data

def overview_set_capacity(code: str, json_data: dict[str, Any], three_month_max: int):
    combined_data[code] = get_useful_data(json_data, three_month_max)