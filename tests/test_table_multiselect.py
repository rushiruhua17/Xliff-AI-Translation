import sys
import unittest


class TestModernTableMultiSelect(unittest.TestCase):
    def test_get_selected_units_multi(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QItemSelectionModel

        app = QApplication.instance() or QApplication(sys.argv)

        from core.xliff_obj import TranslationUnit
        from ui.modern.widgets.translation_table import ModernTranslationTable

        units = [
            TranslationUnit(id="1", source_raw="s1", target_raw=""),
            TranslationUnit(id="2", source_raw="s2", target_raw=""),
            TranslationUnit(id="3", source_raw="s3", target_raw=""),
        ]
        for u in units:
            u.source_abstracted = u.source_raw

        table = ModernTranslationTable()
        table.load_data(units)

        sm = table.selectionModel()
        i0 = table.model().index(0, 0)
        i2 = table.model().index(2, 0)

        sm.select(i0, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        sm.select(i2, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)

        selected = table.get_selected_units()
        self.assertEqual([u.id for u in selected], ["1", "3"])


if __name__ == "__main__":
    unittest.main()

