import unittest

from app.ingest.chunker import ChunkConfig, lc_recursive_ch_text, normalize_text_for_chunking


class ChunkerNormalizationTests(unittest.TestCase):
    def test_normalize_removes_soft_hyphen_and_joins_line_wrap_hyphenation(self):
        raw = "Hy\u00adphen and inter-\n national coop\u00aderation"
        normalized = normalize_text_for_chunking(raw)
        self.assertEqual(normalized, "Hyphen and international cooperation")

    def test_normalize_cleans_unicode_spacing_and_preserves_paragraph_break(self):
        raw = "A\u00A0\u202Fword\t\twith spaces\n\n\nNext\u200B line"
        normalized = normalize_text_for_chunking(raw)
        self.assertEqual(normalized, "A word with spaces\n\nNext line")

    def test_lc_recursive_chunking_uses_normalization(self):
        cfg = ChunkConfig(chunk_chars=256, overlap_chars=32)
        chunks = lc_recursive_ch_text("inter-\n national soft\u00adhyphen", cfg)
        self.assertTrue(chunks)
        joined = " ".join(chunks)
        self.assertIn("international", joined)
        self.assertNotIn("\u00ad", joined)


if __name__ == "__main__":
    unittest.main()
