from itertools import accumulate
from typing import NamedTuple

location_history_minutes = 8 * 24 * 60
min_minutes_between_publications = 3 * 60
location_file_max_age_minutes = 5
late_publication_margin_minutes = 25
# Covers the previous location file, which caches still serve for a while after a republish
recent_history_minutes = min_minutes_between_publications + location_file_max_age_minutes + late_publication_margin_minutes
max_location_files_per_batch = 20

class Change(NamedTuple):
    epoch_minute: int
    rental_bikes: int

class Publication(NamedTuple):
    epoch_minute: int
    last_change: Change

def add_reading(changes: list[Change], fetch_time: int, rental_bikes: int) -> list[Change]:
    epoch_minute = fetch_time // 60
    changes_before_minute = changes[:-1] if changes and changes[-1].epoch_minute == epoch_minute else changes
    if changes_before_minute and changes_before_minute[-1].rental_bikes == rental_bikes:
        return changes_before_minute
    return changes_before_minute + [Change(epoch_minute, rental_bikes)]

def changes_in_effect_since(changes: list[Change], epoch_minute: int) -> list[Change]:
    first_index_to_keep = max((index for index, change in enumerate(changes) if change.epoch_minute <= epoch_minute), default=0)
    return changes[first_index_to_keep:]

def merge_changes(older: list[Change], newer: list[Change]) -> list[Change]:
    if not newer:
        return older
    return [change for change in older if change.epoch_minute < newer[0].epoch_minute] + newer

def changes_for_recent_history(changes: list[Change], publication: Publication | None, now_epoch_minute: int) -> list[Change]:
    if publication is None:
        return changes
    return changes_in_effect_since(changes, min(now_epoch_minute - recent_history_minutes, publication.epoch_minute))

def codes_to_publish(changes_per_code: dict[str, list[Change]], publications: dict[str, Publication], now_epoch_minute: int) -> list[str]:
    unpublished_since_start = sorted(code for code in changes_per_code if code not in publications)
    republishable = sorted(
        (code for code, publication in publications.items()
         if changes_per_code[code][-1] != publication.last_change
         and now_epoch_minute - publication.epoch_minute >= min_minutes_between_publications),
        key=lambda code: publications[code].epoch_minute
    )
    return (unpublished_since_start + republishable)[:max_location_files_per_batch]

def deltas(values: list[int]) -> list[int]:
    return [value - previous_value for value, previous_value in zip(values, [0] + values)]

def to_json(changes: list[Change]) -> dict[str, list[int]]:
    return {
        "minuteDeltas": deltas([change.epoch_minute for change in changes]),
        "rentalBikeDeltas": deltas([change.rental_bikes for change in changes]),
    }

def from_json(history: dict[str, list[int]]) -> list[Change]:
    epoch_minutes = accumulate(history["minuteDeltas"])
    rental_bikes = accumulate(history["rentalBikeDeltas"])
    return [Change(epoch_minute, rental_bikes) for epoch_minute, rental_bikes in zip(epoch_minutes, rental_bikes)]
