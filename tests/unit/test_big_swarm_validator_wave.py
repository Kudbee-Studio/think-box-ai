"""Unit tests for big_swarm validator wave sampling."""

import unittest

from experiments.big_swarm import Compartment, validator_sample_primary


class TestValidatorSamplePrimary(unittest.TestCase):
    def test_all_failed_primaries_still_sampled(self) -> None:
        results = [
            Compartment(
                slot=i,
                worker_id=f"W{i}",
                role="PRIMARY",
                capability="research:primary",
                ok=False,
                tier="",
            )
            for i in range(10)
        ]
        sample = validator_sample_primary(results, 3)
        self.assertEqual(len(sample), 3)
        self.assertFalse(sample[0].ok)

    def test_ok_only_not_required(self) -> None:
        mixed = [
            Compartment(0, "a", "PRIMARY", "c", ok=True, tier="EVIDENCE"),
            Compartment(1, "b", "PRIMARY", "c", ok=False, tier=""),
            Compartment(2, "c", "PRIMARY", "c", ok=True, tier="UNVERIFIED"),
        ]
        sample = validator_sample_primary(mixed, 2)
        self.assertEqual([r.slot for r in sample], [0, 1])

    def test_zero_validators_empty(self) -> None:
        results = [Compartment(0, "a", "PRIMARY", "c", ok=True)]
        self.assertEqual(validator_sample_primary(results, 0), [])

    def test_ignores_validator_role_rows(self) -> None:
        results = [
            Compartment(0, "p", "PRIMARY", "c", ok=False),
            Compartment(1, "v", "VALIDATOR", "c", ok=True, tier="HYPOTHESIS"),
        ]
        sample = validator_sample_primary(results, 1)
        self.assertEqual(sample[0].role, "PRIMARY")


if __name__ == "__main__":
    unittest.main()
