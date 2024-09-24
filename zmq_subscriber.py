import zmq
import gzip
import json
import os

# Create a ZeroMQ context
context = zmq.Context()

# Create a SUB (subscriber) socket
socket = context.socket(zmq.SUB)

# Connect to the server
socket.connect("tcp://vid.openov.nl:6703")

# Subscribe to the /OVfiets topic
topic = "/OVfiets"
socket.setsockopt_string(zmq.SUBSCRIBE, topic)

print(f"Subscribed to topic: {topic}")

# Directory to store the final JSON
base_directory = "OVfiets"
os.makedirs(base_directory, exist_ok=True)

# Initialize a dictionary to accumulate the data
combined_data = {"locaties": {}}

# Function to write the accumulated data to a file
def write_combined_json():
    file_path = os.path.join(base_directory, "combined_data.json")
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(combined_data, json_file, ensure_ascii=False)
    print(f"Combined JSON saved to {file_path}")

# Only return the fields useful for the overview call
def get_useful_data(entry):
    useful = {}
    useful['description'] = entry.get('description')
    useful['stationCode'] = entry.get('stationCode')
    useful['lat'] = entry.get('lat')
    useful['lng'] = entry.get('lng')
    useful['extra'] = {}
    useful['extra']['locationCode'] = entry['extra']['locationCode']
    useful['extra']['fetchTime'] = entry['extra']['fetchTime']
    useful['openingHours'] = entry.get('openingHours')
    return useful

# Loop to handle receiving messages
while True:
    try:
        # Blocking call to receive the first topic (wait for incoming message)
        topic_received = socket.recv_string()

        # Check for available messages in non-blocking mode
        while True:
            try:
                # Non-blocking receive of the actual message data
                message = socket.recv(flags=zmq.NOBLOCK)

                # Attempt to decompress the message assuming it's gzipped
                try:
                    decompressed_message = gzip.decompress(message)
                    # Decode the decompressed message as UTF-8
                    message_str = decompressed_message.decode('utf-8')

                    # Try to parse the string as JSON
                    json_data = json.loads(message_str)

                    # Get the location code from the topic (e.g., eml001 from /OVfiets/EML/eml001)
                    location_code = topic_received.split("/")[-1]

                    # Log a one-liner when JSON is received
                    print(f"Received JSON for location: {location_code}")

                    # Add or update the location data in the combined dictionary
                    combined_data["locaties"][location_code] = get_useful_data(json_data)

                except (OSError, json.JSONDecodeError):
                    print(f"Received non-compressed or non-JSON message")

                # After handling the message, receive the next topic
                topic_received = socket.recv_string(flags=zmq.NOBLOCK)

            except zmq.Again:
                # No more messages available
                break

        # Write the accumulated data to the JSON file
        # TODO: filter out old entries
        write_combined_json()

    except KeyboardInterrupt:
        print("Interrupted")
        break

# Clean up
socket.close()
context.term()