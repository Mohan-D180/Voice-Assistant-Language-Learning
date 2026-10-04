import unittest

from companion.text_utils import SentenceChunker, clean_for_speech


def run_chunker(tokens, **kwargs):
    chunker = SentenceChunker(**kwargs)
    out = []
    for token in tokens:
        out += chunker.feed(token)
    tail = chunker.flush()
    if tail:
        out.append(tail)
    return out


class ChunkerTests(unittest.TestCase):
    def test_splits_streamed_sentences(self):
        tokens = ["Hel", "lo the", "re. How ", "are you", " today?"]
        self.assertEqual(run_chunker(tokens), ["Hello there.", "How are you today?"])

    def test_keeps_decimals_together(self):
        self.assertEqual(run_chunker(["Pi is about 3", ".14 and that is neat."]),
                         ["Pi is about 3.14 and that is neat."])

    def test_bengali_danda(self):
        self.assertEqual(run_chunker(["আমি ভালো আছি। ", "তুমি কেমন আছো?"]),
                         ["আমি ভালো আছি।", "তুমি কেমন আছো?"])

    def test_cjk_without_spaces(self):
        self.assertEqual(run_chunker(["今天天气很好，我们去公园吧。", "你觉得怎么样？"]),
                         ["今天天气很好，我们去公园吧。", "你觉得怎么样？"])

    def test_short_fragments_are_merged(self):
        self.assertEqual(run_chunker(["Dr. Smith is here. Hi!"], min_chars=10),
                         ["Dr. Smith is here.", "Hi!"])

    def test_long_run_without_punctuation_is_cut(self):
        text = "word " * 100
        pieces = run_chunker([text], max_chars=50)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(len(p) <= 51 for p in pieces))

    def test_flush_returns_tail_once(self):
        chunker = SentenceChunker()
        chunker.feed("no ending here")
        self.assertEqual(chunker.flush(), "no ending here")
        self.assertIsNone(chunker.flush())


class CleanerTests(unittest.TestCase):
    def test_strips_markdown(self):
        self.assertEqual(clean_for_speech("**Sure**, here is `code` for you"),
                         "Sure, here is code for you")

    def test_removes_list_markers_and_headings(self):
        self.assertEqual(clean_for_speech("- first thing"), "first thing")
        self.assertEqual(clean_for_speech("# Title"), "Title")

    def test_links_keep_label_only(self):
        self.assertEqual(clean_for_speech("see [the docs](https://x.io/a) now"),
                         "see the docs now")
        self.assertEqual(clean_for_speech("go to https://x.io today"), "go to today")

    def test_removes_emoji(self):
        self.assertEqual(clean_for_speech("Great job 😀🎉"), "Great job")

    def test_keeps_snake_case(self):
        self.assertEqual(clean_for_speech("use my_var here"), "use my_var here")

    def test_unspeakable_becomes_empty(self):
        self.assertEqual(clean_for_speech("... --- ???"), "")
        self.assertEqual(clean_for_speech("🎉"), "")


if __name__ == "__main__":
    unittest.main()
