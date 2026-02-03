import unittest


class TestTokenSafeTranslation(unittest.TestCase):
    def test_split_and_reassemble_preserves_tokens_and_text(self):
        from core.token_safe_translation import split_by_known_tokens, reassemble_from_chunks

        tags_map = {"1": "<ph/>", "2": "<ph/>"}
        text = "A{1}B{2}C"
        r = split_by_known_tokens(text, tags_map)
        self.assertEqual(r.text_chunks, ["A", "B", "C"])
        self.assertEqual(r.tokens, ["{1}", "{2}"])
        self.assertEqual(reassemble_from_chunks(r.text_chunks, r.tokens), text)

    def test_split_ignores_unknown_braces(self):
        from core.token_safe_translation import split_by_known_tokens

        tags_map = {"1": "<ph/>"}
        text = "Keep {99} literal and A{1}B"
        r = split_by_known_tokens(text, tags_map)
        self.assertEqual(r.tokens, ["{1}"])
        self.assertEqual("".join(r.text_chunks), "Keep {99} literal and AB")

    def test_strip_known_tokens_only(self):
        from core.token_safe_translation import strip_known_tokens

        tags_map = {"1": "<ph/>"}
        self.assertEqual(strip_known_tokens("X{1}Y{99}", tags_map), "XY{99}")


if __name__ == "__main__":
    unittest.main()

