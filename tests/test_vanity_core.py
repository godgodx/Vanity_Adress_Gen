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
        from vanity_core import BITCOIN_FIRST_CHAR_PROBABILITY

        # Ethereum/Tor keep the classic uniform alphabet math.
        self.assertEqual(16.0 * 16.0, estimate_difficulty("ab", "end", "ethereum"))
        self.assertEqual(32.0 * 32.0, estimate_difficulty("a", "both", "tor", "b"))
        self.assertAlmostEqual(
            256.0, estimate_difficulty("ab", "start", "ethereum"), delta=1e-9
        )

        # Bitcoin start patterns use the measured first-character distribution.
        self.assertAlmostEqual(
            1.0 / BITCOIN_FIRST_CHAR_PROBABILITY["A"],
            estimate_difficulty("A", "start", "bitcoin"),
            delta=1e-6,
        )

    def test_bitcoin_rare_first_characters_are_much_harder(self):
        # Characters like T/z are ~24x rarer than 1/58 as first body character,
        # so their difficulty must be far above the naive 58 estimate...
        self.assertGreater(estimate_difficulty("T", "start", "bitcoin"), 1000)
        # ...while common leading characters are easier than 58.
        self.assertLess(estimate_difficulty("A", "start", "bitcoin"), 30)

    def test_bitcoin_god_start_estimate_matches_measurement(self):
        # Monte-Carlo measurement: ~4.5-4.8M attempts per 'god' start match.
        self.assertAlmostEqual(
            4_600_000, estimate_difficulty("god", "start", "bitcoin"), delta=500_000
        )


if __name__ == "__main__":
    unittest.main()


class PatternLengthTests(unittest.TestCase):
    def test_overlong_ethereum_pattern_is_rejected(self):
        valid, error = validate_pattern("a" * 41, "ethereum")

        self.assertFalse(valid)
        self.assertIn("too long", error)

    def test_max_length_ethereum_pattern_is_accepted(self):
        self.assertEqual(validate_pattern("a" * 40, "ethereum"), (True, ""))

    def test_overlong_bitcoin_pattern_is_rejected(self):
        valid, error = validate_pattern("a" * 34, "bitcoin")

        self.assertFalse(valid)
        self.assertIn("too long", error)

    def test_overlong_tor_pattern_is_rejected(self):
        valid, error = validate_pattern("a" * 57, "tor")

        self.assertFalse(valid)
        self.assertIn("too long", error)
