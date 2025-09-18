import gzip
import json
import time
import zmq
from firestore_history import load_monthly_capacity_cache, track_historic_capacity, flush_pending_updates, \
    track_hourly_capacity, load_latest_hours_per_code, get_three_month_max, prune_old_months
from overview_bucket import filter_old_entries, upload_combined_data, overview_set_capacity
import threading

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
            print(f"[{location_code}] Received {json_data['extra'].get('rentalBikes', 'unknown')} rentalBikes with fetchTime {json_data['extra']['fetchTime']}")
            if 'rentalBikes' in json_data['extra']:
                capacity = int(json_data['extra']['rentalBikes'])
                track_historic_capacity(location_code, capacity)
                track_hourly_capacity(location_code, capacity)

                three_month_max = get_three_month_max(location_code)
                overview_set_capacity(location_code, json_data, three_month_max)

            topic_received = socket.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            # No more messages available
            return

write_timer = None
def save_and_upload():
    global write_timer
    upload_combined_data()
    flush_pending_updates()
    prune_old_months()
    write_timer = None

def save_and_upload_delayed():
    global write_timer
    if write_timer is not None:
        write_timer.cancel()
    write_timer = threading.Timer(1.0, save_and_upload)
    write_timer.start()

# Main loop
try:
    context = zmq.Context()
    socket = create_socket(context)
    load_monthly_capacity_cache()
    load_latest_hours_per_code()
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