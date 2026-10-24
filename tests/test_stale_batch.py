import re
import unittest
from pathlib import Path

from stale_batch import is_stale_batch

received_line = re.compile(r"\[(?P<code>\w+)\] Received (?P<rental_bikes>-?\d+) rentalBikes with fetchTime \d+")

def rental_bikes_in_arrival_order(log_file_name: str) -> dict[str, int]:
    lines = (Path(__file__).parent / "fixtures" / log_file_name).read_text().splitlines()
    matches = (received_line.fullmatch(line) for line in lines)
    return {match["code"]: int(match["rental_bikes"]) for match in matches if match}

class StaleBatchTest(unittest.TestCase):

    def test_recognizes_the_stale_batch(self):
        self.assertTrue(is_stale_batch(rental_bikes_in_arrival_order("stale_batch_1792618066.log")))

    def test_does_not_flag_the_batch_before_the_stale_batch(self):
        self.assertFalse(is_stale_batch(rental_bikes_in_arrival_order("batch_1792618010.log")))

if __name__ == "__main__":
    unittest.main()
