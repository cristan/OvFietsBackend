import json
from pathlib import Path

stale_batch_rental_bikes: dict[str, int] = json.loads((Path(__file__).parent / "stale_batch_rental_bikes.json").read_text())

def is_stale_batch(rental_bikes_per_code: dict[str, int]) -> bool:
    codes_in_stale_batch = [code for code in rental_bikes_per_code if code in stale_batch_rental_bikes]
    return all(rental_bikes_per_code[code] == stale_batch_rental_bikes[code] for code in codes_in_stale_batch)

def rental_bikes_missing_from_stale_batch(rental_bikes_per_code: dict[str, int]) -> dict[str, int]:
    codes_not_in_stale_batch = [code for code in rental_bikes_per_code if code not in stale_batch_rental_bikes]
    return {code: rental_bikes_per_code[code] for code in codes_not_in_stale_batch}
