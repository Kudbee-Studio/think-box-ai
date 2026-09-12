"""Unit tests for thinkbox/occupancy.py MeshCellManager — horizontal isolation."""

import unittest
from thinkbox.occupancy import MeshCellManager


class TestMeshCellManager(unittest.TestCase):
    def test_create_and_admit(self):
        manager = MeshCellManager()
        cell = manager.create("payments", "owner_1", capabilities=["ledger:write"])
        self.assertTrue(cell.cell_id.startswith("cell_"))
        self.assertTrue(manager.admit(cell.cell_id, "agent_a"))
        self.assertIn("agent_a", manager.members_in(cell.cell_id))

    def test_capability_scoped_to_cell(self):
        manager = MeshCellManager()
        cell = manager.create("payments", "owner_1", capabilities=["ledger:write"])
        self.assertTrue(manager.is_contained(cell.cell_id, "ledger:write"))
        self.assertFalse(manager.is_contained(cell.cell_id, "network:egress"))

    def test_compromised_cell_loses_everything(self):
        manager = MeshCellManager()
        cell = manager.create("payments", "owner_1", capabilities=["ledger:write"])
        manager.admit(cell.cell_id, "agent_a")
        self.assertTrue(manager.expel_all(cell.cell_id))
        self.assertEqual(manager.members_in(cell.cell_id), [])
        self.assertFalse(manager.is_contained(cell.cell_id, "ledger:write"))
        self.assertFalse(manager.admit(cell.cell_id, "agent_b"))

    def test_compromised_peer_does_not_inherit(self):
        manager = MeshCellManager()
        good = manager.create("core", "owner_1", capabilities=["file:read"])
        bad = manager.create("beta", "owner_2", capabilities=["file:write"])
        manager.expel_all(bad.cell_id)
        self.assertTrue(manager.is_contained(good.cell_id, "file:read"))
        self.assertFalse(manager.is_contained(bad.cell_id, "file:write"))

    def test_missing_cell(self):
        manager = MeshCellManager()
        self.assertFalse(manager.admit("cell_x", "a"))
        self.assertFalse(manager.expel_all("cell_x"))
        self.assertEqual(manager.members_in("cell_x"), [])

    def test_cell_count(self):
        manager = MeshCellManager()
        manager.create("a", "o1")
        manager.create("b", "o1")
        manager.create("c", "o2")
        self.assertEqual(manager.cell_count(), 3)


if __name__ == "__main__":
    unittest.main()