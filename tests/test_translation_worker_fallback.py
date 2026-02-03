import unittest


class _FakeClient:
    def __init__(self):
        self.translate_text_chunks_calls = 0
        self.translate_batch_calls = 0

    def translate_text_chunks(self, *args, **kwargs):
        self.translate_text_chunks_calls += 1
        return []

    def translate_batch(self, segments, source_lang, target_lang, system_prompt=None):
        self.translate_batch_calls += 1
        seg = segments[0]
        return [{"id": seg["id"], "translation": "{1}Hello{2}"}]


class TestTranslationWorkerFallback(unittest.TestCase):
    def test_chunk_invalid_falls_back_to_legacy(self):
        from core.workers import TranslationWorker
        from core.xliff_obj import TranslationUnit

        u = TranslationUnit(id="11", source_raw="", target_raw="")
        u.source_abstracted = "{1}你好{2}"
        u.tags_map = {"1": "<ph id='1'/>", "2": "<ph id='2'/>"}
        u.state = "new"

        client = _FakeClient()
        w = TranslationWorker([u], client, "zh-CN", "en-US", profile=None)

        captured = {}

        def _on_batch(res_map):
            captured.update(res_map)

        w.batch_finished.connect(_on_batch)
        w.run()

        self.assertEqual(client.translate_text_chunks_calls, 1)
        self.assertEqual(client.translate_batch_calls, 1)
        self.assertIn("11", captured)
        self.assertEqual(captured["11"], "{1}Hello{2}")


if __name__ == "__main__":
    unittest.main()

