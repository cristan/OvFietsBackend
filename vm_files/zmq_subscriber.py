import gzip
import json
import signal
import sys
import time
import zmq
from firestore_history import load_monthly_capacity_cache, track_historic_capacity, flush_pending_updates, \
    track_hourly_capacity, load_latest_hours_per_code, get_three_month_max, prune_old_months
from overview_bucket import filter_old_entries, upload_combined_data, overview_set_capacity
import threading
from datetime import datetime, timezone
from typing import Any
from history_bucket import Reading, queue_reading_for_hourly_upload, take_readings_of_all_hours, \
    take_readings_of_finished_hours, upload_parquet_files

def create_socket(context: zmq.Context) -> zmq.Socket:
    """
    Creates and returns a configured ZeroMQ SUB socket.
    """
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://vid.openov.nl:6703")
    socket.setsockopt(zmq.RCVTIMEO, 300000)  # 5 minute timeout
    topic = "/OVfiets"
    print(f"Subscribing to topic {topic}")
    socket.setsockopt_string(zmq.SUBSCRIBE, topic)
    return socket

pending_messages_lock = threading.Lock()
pending_messages: list[tuple[str, dict[str, Any]]] = []

def receive_messages(socket: zmq.Socket):
    """
    Receive messages on the given socket and queue them for processing.
    """
    topic_received = socket.recv_string()
    while True:
        try:
            message = socket.recv(flags=zmq.NOBLOCK)
            decompressed_message = gzip.decompress(message)
            message_str = decompressed_message.decode('utf-8')
            json_data = json.loads(message_str)
            location_code = topic_received.split("/")[-1]
            print(f"[{location_code}] Received {json_data['extra'].get('rentalBikes', 'unknown')} rentalBikes with fetchTime {json_data['extra']['fetchTime']}")
            if 'rentalBikes' in json_data['extra']:
                with pending_messages_lock:
                    pending_messages.append((location_code, json_data))

            topic_received = socket.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            # No more messages available
            return

def take_pending_messages() -> list[tuple[str, dict[str, Any]]]:
    with pending_messages_lock:
        taken_messages = list(pending_messages)
        pending_messages.clear()
        return taken_messages

def process_message(location_code: str, json_data: dict[str, Any], now: datetime):
    capacity = int(json_data['extra']['rentalBikes'])
    track_historic_capacity(location_code, capacity)
    track_hourly_capacity(location_code, capacity)
    queue_reading_for_hourly_upload(Reading(location_code, json_data['extra']['fetchTime'], capacity), now)

    three_month_max = get_three_month_max(location_code)
    overview_set_capacity(location_code, json_data, three_month_max)

write_timer = None
def save_and_upload():
    global write_timer
    now = datetime.now(timezone.utc)
    for location_code, json_data in take_pending_messages():
        process_message(location_code, json_data, now)
    filter_old_entries()
    upload_combined_data()
    flush_pending_updates()
    prune_old_months()
    upload_parquet_files(take_readings_of_finished_hours(now), now)
    write_timer = None

def save_and_upload_delayed():
    global write_timer
    if write_timer is not None:
        write_timer.cancel()
    write_timer = threading.Timer(1.0, save_and_upload)
    write_timer.start()

def exit_on_shutdown(signal_number, frame):
    print("Shutting down")
    # Raises SystemExit, which runs the finally block below, uploading any pending readings.
    # Without it, SIGTERM would terminate the process on the spot.
    sys.exit(0)

signal.signal(signal.SIGTERM, exit_on_shutdown)

# Main loop
try:
    context = zmq.Context()
    socket = create_socket(context)
    load_monthly_capacity_cache()
    load_latest_hours_per_code()
    while True:
        try:
            receive_messages(socket)
            save_and_upload_delayed()
        except zmq.Again:
            print("No data received for 5 minutes. Reconnecting.")
            socket.close()
            context.term()
            context = zmq.Context()
            socket = create_socket(context)
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
    upload_parquet_files(take_readings_of_all_hours(), datetime.now(timezone.utc))
    # Clean up resources
    if write_timer is not None:
        write_timer.cancel()
    socket.close()
    context.term()