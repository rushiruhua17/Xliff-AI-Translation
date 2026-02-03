import unittest


class _FakeCombo:
    def __init__(self, items):
        self._items = list(items)
        self._current_index = 0 if self._items else -1

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._current_index

    def setCurrentIndex(self, idx):
        self._current_index = idx

    def currentData(self):
        if self._current_index < 0 or self._current_index >= len(self._items):
            return None
        return self._items[self._current_index].get("data")

    def itemData(self, idx):
        if idx < 0 or idx >= len(self._items):
            return None
        return self._items[idx].get("data")

    def currentText(self):
        if self._current_index < 0 or self._current_index >= len(self._items):
            return ""
        return self._items[self._current_index].get("text", "")


class TestCollectTaskMappings(unittest.TestCase):
    def test_collect_raises_when_no_models_available(self):
        from ui.modern.settings.model_page import collect_task_mappings

        combos = {"translation": _FakeCombo([])}
        with self.assertRaises(ValueError):
            collect_task_mappings(combos)

    def test_collect_uses_item_data_when_current_data_missing(self):
        from ui.modern.settings.model_page import collect_task_mappings

        combos = {
            "translation": _FakeCombo(
                [{"text": "DeepSeek - deepseek-chat", "data": "DeepSeek_deepseek-chat"}]
            )
        }
        combos["translation"]._items[0]["data"] = None
        self.assertEqual(collect_task_mappings(combos)["translation"], "DeepSeek_deepseek-chat")

    def test_collect_falls_back_to_text_parsing(self):
        from ui.modern.settings.model_page import collect_task_mappings

        combos = {
            "repair": _FakeCombo(
                [{"text": "DeepSeek - deepseek-chat", "data": None}]
            )
        }
        self.assertEqual(collect_task_mappings(combos)["repair"], "DeepSeek_deepseek-chat")


if __name__ == "__main__":
    unittest.main()

