import json
from pathlib import Path

stale_batch_rental_bikes: dict[str, int] = json.loads((Path(__file__).parent / "stale_batch_rental_bikes.json").read_text())

def is_stale_batch(rental_bikes_per_code: dict[str, int]) -> bool:
    return all(stale_batch_rental_bikes.get(code) == rental_bikes for code, rental_bikes in rental_bikes_per_code.items())
