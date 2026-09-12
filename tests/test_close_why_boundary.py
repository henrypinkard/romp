"""A verdict's why is cut at a boundary, never mid-word, and the brief judge is told when it was cut (T388).

The closer's block why used to be stored as a raw 300-character slice. A why that listed several questions was cut
mid-word ("... Also say whether the d"), and the brief judge, fed the stump as material, reported a half-stated fifth
question the user had to restate. Now a why is cut at a sentence end or a word boundary with a visible ellipsis, the
cap stays where the tuning pin holds it, and the owed why the brief reads says where the recorded reason
ends. Synthetic text only."""
import json
import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp()
os.environ.setdefault("XDG_STATE_HOME", _TMP)
os.environ.setdefault("ROMP_STATE_DIR", os.path.join(_TMP, "romp"))
from romp_load import load_source

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
jd = load_source("romp_judge", os.path.join(BIN, "romp-judge"))

SENT = ("The exporter keeps two clients and the history budget is a fraction of device memory. "
        "Also say whether the default should follow the setting or the session. "
        "And name the client the tests should target when both are present.")


class CutWhy(unittest.TestCase):
    def test_a_short_why_is_untouched(self):
        self.assertEqual(jd._cut_why("  which   client should the exporter target?  ", 300),
                         "which client should the exporter target?")

    def test_a_long_why_is_cut_at_a_sentence_end_with_a_visible_mark(self):
        out = jd._cut_why(SENT, 120)
        self.assertTrue(out.endswith("." + jd.WHY_CUT_MARK), out)
        self.assertEqual(out, "The exporter keeps two clients and the history budget is a fraction of device memory." + jd.WHY_CUT_MARK)
        self.assertNotIn("Also say whether the d", out, "no stump of the next sentence")

    def test_no_sentence_end_past_half_the_cap_cuts_at_a_word_boundary(self):
        text = "a" + " word" * 80                      # one long sentence, no terminator
        out = jd._cut_why(text, 100)
        self.assertTrue(out.endswith(jd.WHY_CUT_MARK))
        body = out[:-1]
        self.assertLessEqual(len(body), 100)
        self.assertFalse(body.endswith("wor"), "never mid-word")
        self.assertTrue(body.endswith("word"), body[-12:])

    def test_one_unbroken_token_falls_to_the_bare_cap(self):
        out = jd._cut_why("x" * 500, 100)
        self.assertEqual(out, "x" * 100 + jd.WHY_CUT_MARK)

    def test_exactly_at_the_cap_is_not_cut(self):
        text = "y" * 300
        self.assertEqual(jd._cut_why(text, 300), text)


class TheCloserParse(unittest.TestCase):
    def test_a_block_why_longer_than_the_cap_is_cut_at_a_boundary_not_mid_word(self):
        why = " ".join(["Question %d: should the exporter keep the old client for this tenant too?" % i for i in range(12)])
        raw = json.dumps({"done": [], "block": [{"goal": 1, "why": why}]})
        out = jd._parse_close(raw, 1)
        got = out["block"][1]
        self.assertTrue(got.endswith("?" + jd.WHY_CUT_MARK), got[-40:])
        self.assertLessEqual(len(got), jd.WHY_MAX + 1)
        self.assertLessEqual(len(got), jd.WHY_MAX + 1, "the ceiling stands; the cut lands at a boundary under it")

    def test_a_short_block_why_is_stored_whole(self):
        raw = json.dumps({"done": [], "block": [{"goal": 1, "why": "which client should the exporter target?"}]})
        self.assertEqual(jd._parse_close(raw, 1)["block"][1], "which client should the exporter target?")

    def test_a_planner_ops_why_keeps_its_cap_and_never_ends_mid_word(self):
        out = jd._cut_why("word " * 100, jd.WHY_MAX)
        self.assertTrue(out.endswith("word" + jd.WHY_CUT_MARK), out[-12:])
        self.assertLessEqual(len(out), jd.WHY_MAX + 1)


class TheBriefsMaterial(unittest.TestCase):
    def test_the_owed_why_says_where_a_cut_reason_ends(self):
        nd = {"blockWhy": "Decide the retry policy for the exporter." + jd.WHY_CUT_MARK}
        owed = jd._owed_why(nd)
        self.assertTrue(owed.startswith("Decide the retry policy for the exporter." + jd.WHY_CUT_MARK))
        self.assertIn("the recorded reason ends here", owed)

    def test_a_whole_why_gets_no_note(self):
        self.assertEqual(jd._owed_why({"blockWhy": "Decide the retry policy."}), "Decide the retry policy.")


if __name__ == "__main__":
    unittest.main()
