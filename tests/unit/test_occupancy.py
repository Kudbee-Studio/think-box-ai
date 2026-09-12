"""Unit tests for thinkbox/occupancy.py — KUDBEE occupancy mesh."""

import unittest
from thinkbox.occupancy import OccupancyMonitor


class TestOccupancyMonitor(unittest.TestCase):
    def test_record_and_sample(self):
        monitor = OccupancyMonitor()
        monitor.record_agent(grounded=True)
        monitor.record_agent(grounded=True)
        monitor.record_agent(grounded=False)
        sample = monitor.sample(load=0.5)
        self.assertEqual(sample.active_agents, 3)
        self.assertAlmostEqual(sample.grounded_ratio, 2 / 3)
        self.assertEqual(sample.load, 0.5)

    def test_release_agent(self):
        monitor = OccupancyMonitor()
        monitor.record_agent(grounded=True)
        monitor.release_agent()
        sample = monitor.sample(load=0.1)
        self.assertEqual(sample.active_agents, 0)

    def test_release_never_negative(self):
        monitor = OccupancyMonitor()
        monitor.release_agent()
        monitor.release_agent()
        self.assertEqual(monitor.summary()["active_agents"], 0)

    def test_cells_floor_at_one(self):
        monitor = OccupancyMonitor()
        monitor.set_cells(5)
        monitor.set_cells(0)
        self.assertEqual(monitor.summary()["active_cells"], 1)

    def test_summary_empty(self):
        monitor = OccupancyMonitor()
        summary = monitor.summary()
        self.assertEqual(summary["active_agents"], 0)
        self.assertEqual(summary["grounded_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()