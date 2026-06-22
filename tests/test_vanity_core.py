import unittest

from vanity_core import estimate_difficulty, matches_pattern, validate_pattern


class PatternValidationTests(unittest.TestCase):
    def test_bitcoin_rejects_non_base58_characters(self):
        valid, error = validate_pattern("0OIl", "bitcoin")

        self.assertFalse(valid)
        self.assertIn("Invalid", error)

    def test_ethereum_accepts_hex_case_insensitively(self):
        valid, error = validate_pattern("DeAdBEEF", "ethereum")

        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_tor_rejects_outside_base32_alphabet(self):
        valid, error = validate_pattern("hello8", "tor")

        self.assertFalse(valid)
        self.assertIn("Invalid", error)


class PatternMatchingTests(unittest.TestCase):
    def test_bitcoin_start_match_ignores_fixed_prefix(self):
        self.assertTrue(matches_pattern("1AbcDefGh", "Abc", "bitcoin", "start"))
        self.assertFalse(matches_pattern("1AbcDefGh", "abc", "bitcoin", "start"))

    def test_ethereum_match_ignores_0x_and_case(self):
        address = "0xDEADBEEF00000000000000000000000000000000"

        self.assertTrue(matches_pattern(address, "dead", "ethereum", "start"))
        self.assertTrue(matches_pattern(address, "BEEF", "ethereum", "anywhere"))

    def test_tor_match_ignores_onion_suffix(self):
        address = "abcdef234567abcdef234567abcdef234567abcdef234567abcd.onion"

        self.assertTrue(matches_pattern(address, "abcd", "tor", "start"))
        self.assertTrue(matches_pattern(address, "abcd", "tor", "end"))
        self.assertTrue(matches_pattern(address, "def234", "tor", "anywhere"))

    def test_both_position_requires_start_and_end(self):
        address = "0xabc0000000000000000000000000000000000def"

        self.assertTrue(matches_pattern(address, "abc", "ethereum", "both", "def"))
        self.assertFalse(matches_pattern(address, "abc", "ethereum", "both", "bad"))


class DifficultyEstimateTests(unittest.TestCase):
    def test_basic_difficulty_values(self):
        self.assertEqual(58.0, estimate_difficulty("A", "start", "bitcoin"))
        self.assertEqual(16.0 * 16.0, estimate_difficulty("ab", "end", "ethereum"))
        self.assertEqual(32.0 * 32.0, estimate_difficulty("a", "both", "tor", "b"))


if __name__ == "__main__":
    unittest.main()
