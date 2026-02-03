import unittest


class TestTagAbstractorLxml(unittest.TestCase):
    def test_self_closing_ph(self):
        from core.abstractor import TagAbstractor

        a = TagAbstractor()
        raw = 'A<ph id="1"/>B'
        res = a.abstract(raw)
        self.assertEqual(res.abstracted_text, "A{1}B")
        self.assertIn("1", res.tags_map)
        self.assertIn('ph id="1"', res.tags_map["1"])

        rebuilt = a.reconstruct(res.abstracted_text, res.tags_map)
        self.assertIn('ph id="1"', rebuilt)

    def test_nested_g_is_single_token(self):
        from core.abstractor import TagAbstractor

        a = TagAbstractor()
        raw = 'X<g id="1"><ph id="2"/>Y</g>Z'
        res = a.abstract(raw)
        self.assertEqual(res.abstracted_text, "X{1}Z")
        self.assertIn("1", res.tags_map)
        self.assertIn("<g", res.tags_map["1"])
        self.assertIn('ph id="2"', res.tags_map["1"])

    def test_xmlns_is_stripped(self):
        from core.abstractor import TagAbstractor

        a = TagAbstractor()
        raw = '<ph xmlns="urn:test" id="1"/>'
        res = a.abstract(raw)
        self.assertEqual(res.abstracted_text, "{1}")
        self.assertNotIn("xmlns", res.tags_map["1"])

    def test_comment_is_preserved_not_tokenized(self):
        from core.abstractor import TagAbstractor

        a = TagAbstractor()
        raw = 'A<!--c--><ph id="1"/>B'
        res = a.abstract(raw)
        self.assertEqual(res.abstracted_text, "A<!--c-->{1}B")
        self.assertEqual(list(res.tags_map.keys()), ["1"])


if __name__ == "__main__":
    unittest.main()

