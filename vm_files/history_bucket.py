import io
import os
import threading
from collections import defaultdict
from datetime import datetime
from typing import NamedTuple

import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

class Reading(NamedTuple):
    code: str
    fetch_time: int
    rental_bikes: int

parquet_columns = pa.schema([
    ("code", pa.string()),
    ("fetchTime", pa.timestamp("s", tz="UTC")),
    ("rentalBikes", pa.int16()),
])

pending_readings_lock = threading.Lock()
pending_readings_per_hour: dict[datetime, list[Reading]] = defaultdict(list)

def start_of_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)

def queue_reading_for_hourly_upload(reading: Reading, received_at: datetime):
    with pending_readings_lock:
        pending_readings_per_hour[start_of_hour(received_at)].append(reading)

def create_parquet_file(readings: list[Reading]) -> bytes:
    sorted_readings = sorted(readings)
    table = pa.table({
        "code": [reading.code for reading in sorted_readings],
        "fetchTime": [reading.fetch_time for reading in sorted_readings],
        "rentalBikes": [reading.rental_bikes for reading in sorted_readings],
    }, schema=parquet_columns)
    file = io.BytesIO()
    pq.write_table(table, file, compression="gzip")
    return file.getvalue()

def parquet_file_name(hour: datetime) -> str:
    return hour.strftime("date=%Y-%m-%d/%H.parquet")

def take_readings_of_finished_hours(now: datetime) -> dict[datetime, list[Reading]]:
    with pending_readings_lock:
        finished_hours = [hour for hour in pending_readings_per_hour if hour < start_of_hour(now)]
        return {hour: pending_readings_per_hour.pop(hour) for hour in finished_hours}

def upload_parquet_files_of_finished_hours(now: datetime):
    readings_per_finished_hour = take_readings_of_finished_hours(now)
    if not readings_per_finished_hour:
        return

    bucket = storage.Client().bucket(os.getenv("HISTORY_BUCKET_NAME"))
    for hour, readings in readings_per_finished_hour.items():
        file_name = parquet_file_name(hour)
        bucket.blob(file_name).upload_from_string(create_parquet_file(readings))
        print(f"Uploaded {len(readings)} readings to {file_name}")
