import unittest

from address_match import AddressIndex, parse


def idx(*rows):
    return AddressIndex([(r, None) if isinstance(r, str) else r for r in rows])


class TestMatch(unittest.TestCase):
    def test_abbrev_vs_spelled(self):
        i = idx("3700 2ND AVE N")
        self.assertTrue(i.lookup("3700 2nd avenue n, st petersburg, fl 33713"))
        self.assertTrue(i.lookup("3700 2nd ave n, saint petersburg, fl 33713"))

    def test_no_substring_false_positive(self):
        i = idx("453 5th ave n", "100 34TH ST N")
        self.assertFalse(i.lookup("6453 5th ave n, st petersburg, fl"))
        self.assertFalse(i.lookup("2100 34th st n, st petersburg, fl"))

    def test_direction_must_agree(self):
        i = idx("3821 1ST AVE S")
        self.assertFalse(i.lookup("3821 1st avenue n, st petersburg, fl"))
        self.assertTrue(i.lookup("3821 1st avenue s, st petersburg, fl"))
        self.assertFalse(i.lookup("156 18th ave se, st petersburg, fl") and idx("156 18th ave s").lookup("156 18th ave se, x"))

    def test_directionless_csv_row_matches_either(self):
        i = idx("3545 5TH AVE")
        self.assertTrue(i.lookup("3545 5th avenue s, st petersburg, fl"))

    def test_mlk(self):
        i = idx("4420 DR ML KING JR ST N")
        self.assertTrue(i.lookup("4420 dr martin luther king jr street n, st petersburg, fl"))

    def test_ordinals_spelled(self):
        self.assertTrue(idx("500 1ST AVE N").lookup("500 first avenue north, st petersburg, fl"))

    def test_unit_stripped(self):
        self.assertTrue(idx("2593 38TH AVE N").lookup("2593 38th avenue n #b, st petersburg, fl"))
        self.assertTrue(idx("654 100TH AVE N").lookup("654 100th avenue n unit 205, st petersburg"))

    def test_fraction_kept(self):
        i = idx("3529 1/2 22ND AVE S")
        self.assertTrue(i.lookup("3529 1/2 22nd avenue s, st petersburg, fl"))
        self.assertFalse(i.lookup("3529 22nd avenue s, st petersburg, fl"))

    def test_range_expanded_same_parity(self):
        i = idx("1737-1741 10TH ST S")
        self.assertTrue(i.lookup("1739 10th street s, x"))
        self.assertFalse(i.lookup("1738 10th street s, x"))

    def test_city_part_ignored(self):
        self.assertTrue(idx("10 PASADENA AVE N").lookup("10 pasadena ave n, Petersburg, FL"))

    def test_bare_street_row_unparseable(self):
        i = idx("18th Ave S")
        self.assertEqual(i.dropped, ["18th Ave S"])
        self.assertFalse(i.lookup("237 18th ave s, x"))

    def test_zone_per_row_and_dupes(self):
        i = AddressIndex([("1935 CENTRAL AVE", "CRT-2"), ("1935 Central Ave", "CRT-2"), ("1935 CENTRAL AVE", "CCT-2")])
        self.assertEqual(sorted(z for z, _ in i.lookup("1935 central avenue, st petersburg")), ["CCT-2", "CRT-2"])

    def test_parse_garbage(self):
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("Bayfront Medical Center"))


if __name__ == "__main__":
    unittest.main()
