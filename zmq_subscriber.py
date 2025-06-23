import zmq
import gzip
import json
import os
import time
import threading
from typing import Dict
from datetime import datetime
from google.cloud import storage
from google.cloud import firestore

# Directory to store the final JSON
base_directory = "OVfiets"
os.makedirs(base_directory, exist_ok=True)

db = firestore.Client()
flush_lock = threading.Lock()

combined_data = {}
capacity_cache = {}
pending_updates = {}

def create_socket(context):
    """
    Creates and returns a configured ZeroMQ SUB socket.
    """
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://vid.openov.nl:6703")
    topic = "/OVfiets"
    print(f"Subscribing to topic {topic}")
    socket.setsockopt_string(zmq.SUBSCRIBE, topic)
    return socket

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

write_timer = None
def save_and_upload():
    global write_timer
    write_combined_json()
    upload_to_gcs(base_directory+'/combined_data.json', 'locations.json')
    flush_pending_updates()
    write_timer = None

def save_and_upload_delayed():
    global write_timer
    if write_timer is not None:
        write_timer.cancel()
    write_timer = threading.Timer(1.0, save_and_upload)
    write_timer.start()

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

def receive_messages(socket):
    """
    Handle incoming messages on the given socket and update combined_data.
    """
    topic_received = socket.recv_string()
    while True:
        try:
            message = socket.recv(flags=zmq.NOBLOCK)
            decompressed_message = gzip.decompress(message)
            message_str = decompressed_message.decode('utf-8')
            json_data = json.loads(message_str)
            location_code = topic_received.split("/")[-1]
            print(f"[{location_code}] received {json_data['extra'].get('rentalBikes', 'unknown')} rentalBikes with fetchTime {json_data['extra']['fetchTime']}")
            if 'rentalBikes' in json_data['extra']:
                combined_data[location_code] = get_useful_data(json_data)
                handle_capacity(location_code, int(json_data['extra']['rentalBikes']))
            
            topic_received = socket.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            # No more messages available
            return

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

def handle_capacity(code: str, capacity: int):
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
            print(f"[{code}] No update persisted because {old_min} <= {capacity} <= {old_max}")
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

    print(f"[{code}] Queued update: {new_min}–{new_max}")

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

# Main loop
try:
    context = zmq.Context()
    socket = create_socket(context)
    capacity_cache = load_monthly_capacity_cache()
    while True:
        try:
            receive_messages(socket)
            filter_old_entries()
            save_and_upload_delayed()
        except zmq.ZMQError:
            print("Connection lost. Retrying in 5 minutes.")
            socket.close()
            context.term()
            time.sleep(300) # 5 minutes * 60 = 300 seconds
            context = zmq.Context()
            socket = create_socket(context)
except KeyboardInterrupt:
    print("Interrupted by user.")
finally:
    # Clean up resources
    if write_timer is not None:
        write_timer.cancel()
    socket.close()
    context.term()