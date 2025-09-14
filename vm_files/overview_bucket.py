import os
import time

# Directory to store the final JSON
base_directory = "OVfiets"
os.makedirs(base_directory, exist_ok=True)

combined_data = {}

import io
import gzip
import json
from google.cloud import storage

def upload_gzipped_json(data, destination_blob_name):
    client = storage.Client()
    bucket_name = os.getenv("PUBLIC_BUCKET_NAME")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Convert the data to JSON
    json_bytes = json.dumps(
        list(data.values()), ensure_ascii=False
    ).encode("utf-8")

    # Gzip in memory
    gzipped_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gzipped_buffer, mode="wb") as f_out:
        f_out.write(json_bytes)
    gzipped_buffer.seek(0)  # rewind to the beginning

    # Upload to GCS
    blob.cache_control = "no-cache, max-age=0"
    blob.content_encoding = "gzip"
    blob.content_type = "application/json"
    blob.upload_from_file(gzipped_buffer, rewind=True)

    print(f"Uploaded {destination_blob_name} to {bucket_name} (gzip-compressed)")

def upload_combined_data():
    upload_gzipped_json(combined_data, "locations.json")

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

def get_useful_data(entry):
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
        'openingHours': entry.get('openingHours')
    }

    if 'serviceType' in entry['extra']:
        useful_data['extra']['serviceType'] = entry['extra']['serviceType']

    return useful_data

def overview_set_capacity(code, json_data):
    combined_data[code] = get_useful_data(json_data)