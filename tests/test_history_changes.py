import unittest

from history_changes import Change, Publication, add_reading, changes_for_recent_history, changes_in_effect_since, \
    codes_to_publish, from_json, merge_changes, to_json

# (fetchTime, rentalBikes) of gn001 as zmq_subscriber processes them:
# its 855 in the stale batch at 1792618066 is left out
gn001_readings = [
    (1792617068, 327), (1792617123, 327), (1792617178, 327), (1792617234, 327), (1792617289, 327),
    (1792617345, 329), (1792617400, 329), (1792617456, 329), (1792617511, 329), (1792617567, 329),
    (1792617622, 330), (1792617677, 330), (1792617733, 329), (1792617788, 329), (1792617844, 330),
    (1792617899, 331), (1792617955, 331), (1792618010, 331), (1792618121, 331), (1792618177, 331),
    (1792618232, 331), (1792618288, 331), (1792618343, 331), (1792618398, 330), (1792618454, 331),
    (1792618509, 331), (1792618565, 331), (1792618620, 331), (1792618675, 331),
]

gn001_changes = [
    Change(29876951, 327), Change(29876955, 329), Change(29876960, 330), Change(29876962, 329),
    Change(29876964, 331), Change(29876973, 330), Change(29876974, 331),
]

def add_readings(changes: list[Change], readings: list[tuple[int, int]]) -> list[Change]:
    for fetch_time, rental_bikes in readings:
        changes = add_reading(changes, fetch_time, rental_bikes)
    return changes

class HistoryChangesTest(unittest.TestCase):

    def test_keeps_one_change_per_minute_in_which_the_rental_bikes_changed(self):
        self.assertEqual(gn001_changes, add_readings([], gn001_readings))

    def test_a_later_reading_in_the_same_minute_replaces_the_change_of_that_minute(self):
        # 1792617844 and 1792617899 are both in minute 29876964
        changes = add_readings([], gn001_readings[:15])
        self.assertEqual(Change(29876964, 330), changes[-1])

        self.assertEqual(Change(29876964, 331), add_reading(changes, 1792617899, 331)[-1])

    def test_a_later_reading_in_the_same_minute_can_undo_the_change_of_that_minute(self):
        # 1792676820 and 1792676875 are both in minute 29877947
        self.assertEqual([Change(29877946, 158)], add_readings([], [(1792676765, 158), (1792676820, 161), (1792676875, 158)]))

    def test_json_holds_the_minutes_and_rental_bikes_as_deltas(self):
        self.assertEqual({
            "minuteDeltas": [29876951, 4, 5, 2, 2, 9, 1],
            "rentalBikeDeltas": [327, 2, 1, -1, 2, -1, 1],
        }, to_json(gn001_changes))
        self.assertEqual(gn001_changes, from_json(to_json(gn001_changes)))

    def test_changes_in_effect_since_a_minute_include_the_change_in_effect_at_that_minute(self):
        self.assertEqual([
            Change(29876960, 330), Change(29876962, 329), Change(29876964, 331),
            Change(29876973, 330), Change(29876974, 331),
        ], changes_in_effect_since(gn001_changes, 29876961))

    def test_merging_lets_the_newer_changes_win_from_their_first_minute(self):
        published = gn001_changes[:4]
        in_memory = [Change(29876962, 329), Change(29876964, 331), Change(29876973, 330), Change(29876974, 331)]
        self.assertEqual(gn001_changes, merge_changes(published, in_memory))

    def test_recent_history_holds_every_change_of_a_location_not_yet_published_since_start(self):
        self.assertEqual(gn001_changes, changes_for_recent_history(gn001_changes, None, 29877200))

    def test_recent_history_holds_the_changes_since_the_last_publication(self):
        publication = Publication(29876963, Change(29876962, 329))
        self.assertEqual([
            Change(29876962, 329), Change(29876964, 331), Change(29876973, 330), Change(29876974, 331),
        ], changes_for_recent_history(gn001_changes, publication, 29877200))

    def test_recent_history_holds_the_published_changes_of_the_last_three_and_a_half_hours(self):
        publication = Publication(29876975, Change(29876974, 331))
        self.assertEqual([Change(29876973, 330), Change(29876974, 331)],
                         changes_for_recent_history(gn001_changes, publication, 29877183))
        self.assertEqual([Change(29876974, 331)], changes_for_recent_history(gn001_changes, publication, 29877184))

    def test_publishes_locations_not_yet_published_since_start_first_and_at_most_20_per_batch(self):
        # 21 locations not yet published since the start, and gn001, which is due to be republished
        unpublished_since_start = {
            "Apg001": 5, "Arn002": 4, "Bd003": 196, "Bmr001": 9, "Co002": 8, "Cps003": 4, "DRON001": 14,
            "Dz001": 6, "Gnn001": 0, "Gp001": 8, "Hde001": 17, "Hgz001": 8, "Hto001": 8, "Kpnz002": 7,
            "Mmlh002": 5, "Mth002": 4, "Ns001": 8, "Ot001": 9, "Ow002": 7, "Rtd003": 9, "Rtd004": 10,
        }
        changes_per_code = {code: [Change(29876951, rental_bikes)] for code, rental_bikes in unpublished_since_start.items()}
        changes_per_code["gn001"] = gn001_changes
        publications = {"gn001": Publication(29876951, Change(29876951, 327))}

        self.assertEqual([
            "Apg001", "Arn002", "Bd003", "Bmr001", "Co002", "Cps003", "DRON001", "Dz001", "Gnn001", "Gp001",
            "Hde001", "Hgz001", "Hto001", "Kpnz002", "Mmlh002", "Mth002", "Ns001", "Ot001", "Ow002", "Rtd003",
        ], codes_to_publish(changes_per_code, publications, 29877143))

    def test_republishes_a_changed_location_three_hours_after_its_last_publication(self):
        changes_per_code = {"gn001": gn001_changes}
        publications = {"gn001": Publication(29876963, Change(29876962, 329))}

        self.assertEqual([], codes_to_publish(changes_per_code, publications, 29877142))
        self.assertEqual(["gn001"], codes_to_publish(changes_per_code, publications, 29877143))

    def test_does_not_republish_an_unchanged_location(self):
        changes_per_code = {"gn001": gn001_changes}
        publications = {"gn001": Publication(29876975, Change(29876974, 331))}

        self.assertEqual([], codes_to_publish(changes_per_code, publications, 29877200))

if __name__ == "__main__":
    unittest.main()
