"""Offline checks for roadmap items 5 and 6."""
import unittest

from coherence import PROFILE_VERSION, build_attitude_profile, render_attitude_profile
from engagement import DEFAULT_TARGET, engagement_band, engagement_factors


class Roadmap56Tests(unittest.TestCase):
    def setUp(self):
        self.persona = {"uuid": "demo-001", "age": 47, "province": "서울"}
        self.demo = {"Q2": 47, "Q3": 2}

    def test_attitude_profile_is_deterministic_and_renderable(self):
        a = build_attitude_profile(self.persona, self.demo)
        b = build_attitude_profile(self.persona, self.demo)
        self.assertEqual(a, b)
        self.assertEqual(a["version"], PROFILE_VERSION)
        self.assertIn("문항 간", render_attitude_profile(a))

    def test_engagement_factors_are_normalized(self):
        records = [{"engagement_score": i / 20} for i in range(21)]
        factors = engagement_factors(records)
        self.assertEqual(len(records), len(factors))
        self.assertAlmostEqual(sum(factors) / len(factors), 1.0, places=8)

        weighted = {b: 0.0 for b in DEFAULT_TARGET}
        for record, factor in zip(records, factors):
            weighted[engagement_band(record["engagement_score"])] += factor
        total = sum(weighted.values())
        for band, target in DEFAULT_TARGET.items():
            self.assertAlmostEqual(weighted[band] / total, target, delta=0.04)


if __name__ == "__main__":
    unittest.main()
