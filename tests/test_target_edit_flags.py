import unittest


class TestTargetEditFlags(unittest.TestCase):
    def test_target_not_editable_when_pending_exists(self):
        from core.xliff_obj import TranslationUnit
        from core.xliff_model import XliffTableModel
        from PyQt6.QtCore import Qt

        u = TranslationUnit(id="1", source_raw="s", target_raw="")
        u.target_abstracted = "old"
        u.pending_target = "proposal"
        u.state = "edited"

        m = XliffTableModel([u])
        idx = m.index(0, 6)
        flags = m.flags(idx)
        self.assertFalse(bool(flags & Qt.ItemFlag.ItemIsEditable))

    def test_target_editable_when_no_pending(self):
        from core.xliff_obj import TranslationUnit
        from core.xliff_model import XliffTableModel
        from PyQt6.QtCore import Qt

        u = TranslationUnit(id="1", source_raw="s", target_raw="")
        u.target_abstracted = "t"
        u.pending_target = None
        u.state = "edited"

        m = XliffTableModel([u])
        idx = m.index(0, 6)
        flags = m.flags(idx)
        self.assertTrue(bool(flags & Qt.ItemFlag.ItemIsEditable))


if __name__ == "__main__":
    unittest.main()

