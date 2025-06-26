import os
import time
import json
from google.cloud import storage

# Directory to store the final JSON
base_directory = "OVfiets"
os.makedirs(base_directory, exist_ok=True)

combined_data = {}

def write_combined_json():
    file_path = os.path.join(base_directory, "combined_data.json")
    to_write = list(combined_data.values())
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(to_write, json_file, ensure_ascii=False)
    print(f"Combined JSON saved to {file_path}")

def upload_to_gcs(source_file_name, destination_blob_name):
    client = storage.Client()
    bucket_name = os.getenv("PUBLIC_BUCKET_NAME")
    print(f"Uploading {source_file_name} to bucket {bucket_name} as {destination_blob_name}.")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.cache_control = "no-cache, max-age=0"
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

def write_and_upload_to_gcs():
    write_combined_json()
    upload_to_gcs(base_directory+'/combined_data.json', 'locations.json')

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
    return {
        # strip because Duiven has a space at the end of its description.
        'description': entry.get('description', '').strip(),
        'stationCode': entry.get('stationCode'),
        'lat': entry.get('lat'),
        'lng': entry.get('lng'),
        'link': {'uri': entry['link']['uri']},
        'extra': {
            'locationCode': entry['extra']['locationCode'],
            'fetchTime': entry['extra']['fetchTime'],
            # Not always present, but we filter out entries without it beforehand
            'rentalBikes': entry['extra']['rentalBikes']
        },
        'openingHours': entry.get('openingHours')
    }

def overview_set_capacity(code, json_data):
    combined_data[code] = get_useful_data(json_data)