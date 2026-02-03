import unittest


class TestRepairWorkerSignal(unittest.TestCase):
    def test_segment_repaired_signal_accepts_str_unit_id(self):
        from core.repair import RepairWorker

        w = RepairWorker([], client=None)
        captured = {}

        def _slot(unit_id, fixed_text, state):
            captured["args"] = (unit_id, fixed_text, state)

        w.segment_repaired.connect(_slot)
        w.segment_repaired.emit("2", "{1}Serial Number{2}", "edited")
        self.assertEqual(captured["args"][0], "2")


if __name__ == "__main__":
    unittest.main()
