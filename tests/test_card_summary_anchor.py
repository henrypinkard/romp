"""A card's brief or summary click lands on the text that carries it, never on a tool call (T388).

The manager's finding, 2026-09-12: a blocked card whose brief had no validated citation sent its summary click to
the node's WORK anchor, the newest trail segment's first assistant atom, a shell call inside a collapsed tool group,
while the quoted questions were the same turn's last text atom thirteen minutes later; four landings filed
pointer-exact on the wrong atom. The kernel now resolves such a click to the assistant text atom of that segment's
turn that carries the line's opening sentence (else the turn's last text atom), never a tool_use or thinking atom,
and ships the located span as the click's quote. Synthetic atoms only."""
import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp()
os.environ.setdefault("XDG_STATE_HOME", _TMP)
os.environ.setdefault("ROMP_STATE_DIR", os.path.join(_TMP, "romp"))
from romp_load import load_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
em = load_source("romp_event_model", os.path.join(BIN, "romp-event-model"))
jd = load_source("romp_judge", os.path.join(BIN, "romp-judge"))
km = load_source("romp_kernel", os.path.join(BIN, "romp-kernel"))

T0 = 1781300000


def tool(uuid, t):
    return {"type": "assistant", "uuid": uuid, "t": t, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "tu-" + uuid, "name": "Bash", "input": {"command": "true"}}]}}


def think(uuid, t):
    return {"type": "assistant", "uuid": uuid, "t": t, "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hm"}]}}


def text(uuid, t, body):
    return {"type": "assistant", "uuid": uuid, "t": t, "message": {"role": "assistant", "content": [{"type": "text", "text": body}]}}


QUESTIONS = ("Four questions before I go on. Should the history budget follow the device or the setting? "
             "Which client do the tests target? Do we keep the old exporter? Who owns the glossary file?")
BRIEF = "Should the history budget follow the device or the setting? The session asks four things it cannot decide alone."


class TheTextAtom(unittest.TestCase):
    def test_a_segment_of_tool_calls_lands_on_the_turns_text_atom_not_the_first_tool_call(self):
        seg = [tool("a1", T0), tool("a2", T0 + 1), tool("a3", T0 + 2), tool("a4", T0 + 3)]   # the newest trail segment: shell calls only
        turn = {"t": T0, "end": T0 + 800, "atoms": seg + [text("t9", T0 + 780, QUESTIONS)]}    # the turn's last text atom, later
        self.assertEqual(km._seg_jump(seg), "a1", "the WORK anchor: the first landable atom, a tool call (the collapsed group)")
        u, q = km._summary_text_anchor((turn, seg), BRIEF)
        self.assertEqual(u, "t9", "the brief click lands on the text atom that carries its opening sentence")
        self.assertEqual(q, "Should the history budget follow the device or the setting?", "the located span rides as the quote")

    def test_the_atom_carrying_the_opening_sentence_wins_over_a_later_text_atom(self):
        seg = [tool("a1", T0), text("t5", T0 + 10, QUESTIONS), text("t6", T0 + 20, "Done for now.")]
        turn = {"t": T0, "end": T0 + 30, "atoms": seg}
        u, q = km._summary_text_anchor((turn, seg), BRIEF)
        self.assertEqual((u, q), ("t5", "Should the history budget follow the device or the setting?"))

    def test_no_sentence_match_falls_to_the_segments_last_text_atom_with_no_quote(self):
        seg = [tool("a1", T0), text("t5", T0 + 10, "first note"), text("t6", T0 + 20, "second note")]
        turn = {"t": T0, "end": T0 + 30, "atoms": seg}
        self.assertEqual(km._summary_text_anchor((turn, seg), "Decide the retry policy for the exporter."), ("t6", None))

    def test_a_segment_without_text_falls_to_the_turns_last_text_atom(self):
        seg = [tool("a1", T0), think("th", T0 + 1)]
        turn = {"t": T0, "end": T0 + 60, "atoms": seg + [text("t7", T0 + 50, "wrap-up here")]}
        self.assertEqual(km._summary_text_anchor((turn, seg), "Nothing that matches."), ("t7", None))

    def test_thinking_and_tool_calls_alone_resolve_to_nothing(self):
        seg = [tool("a1", T0), think("th", T0 + 1)]
        turn = {"t": T0, "end": T0 + 5, "atoms": seg}
        self.assertEqual(km._summary_text_anchor((turn, seg), BRIEF), (None, None))
        self.assertEqual(km._summary_text_anchor(None, BRIEF), (None, None))

    def test_an_api_error_and_the_null_settle_are_never_the_landing(self):
        err = dict(text("e1", T0 + 5, "API Error: overloaded"), isApiError=True)
        seg = [tool("a1", T0), err, text("t2", T0 + 6, "the real reply")]
        turn = {"t": T0, "end": T0 + 10, "atoms": seg}
        self.assertEqual(km._summary_text_anchor((turn, seg), "Nothing matches."), ("t2", None))

    def test_the_opening_sentence_drops_a_list_number_and_stops_at_the_first_sentence_end(self):
        self.assertEqual(km._opening_sentence("1. Decide the retry policy. Then the rest."), "Decide the retry policy.")
        self.assertEqual(km._opening_sentence("\n\nShort? Yes it is."), "Short? Yes it is.", "a sentence end inside the first twelve characters is not the cut")
        self.assertEqual(km._opening_sentence(""), "")

    def test_the_memo_answers_a_repeat_without_reading_again(self):
        seg = [tool("a1", T0), text("t5", T0 + 10, QUESTIONS)]
        turn = {"t": T0, "end": T0 + 30, "atoms": seg}
        km._SUMMARY_ANCHOR_MEMO.clear()
        first = km._summary_text_anchor((turn, seg), BRIEF, memo_key=("11111111-2222-3333-4444-555555555555", "g1", "k1"))
        seg[1]["message"]["content"][0]["text"] = "changed under the memo"      # the same key: the memo answers, no re-read
        again = km._summary_text_anchor((turn, seg), BRIEF, memo_key=("11111111-2222-3333-4444-555555555555", "g1", "k1"))
        self.assertEqual(first, again)
        self.assertEqual(first[0], "t5")


class TheWiring(unittest.TestCase):
    def test_the_card_chain_tries_the_text_atom_before_the_latest_prose_walk_and_the_tree_rows_carry_it(self):
        src = open(os.path.join(ROOT, "kernel", "kernel.py"), encoding="utf-8").read()
        tier = src.index("_sa_u, _sa_q = _summary_text_anchor(seg_turn.get(_sk), _line, memo_key=(fsid, nid, _sk))")
        walk = src.index("_best = None                             # (substantive, seg_t): prefer substantive, then latest")
        self.assertLess(tier, walk, "the text-atom tier runs before the latest-prose walk and the work-anchor last resort")
        self.assertIn('"summaryAnchorUuid": _nsa_u,', src, "every tree row carries the brief line's own landing")
        self.assertIn('"summaryAnchorQuote": _nsa_q,', src)
        self.assertIn("else (_sa_q or None)),", src, "the card's quote falls to the text-atom tier's span")
        ts = open(os.path.join(ROOT, "ui", "webview", "feed.ts"), encoding="utf-8").read()
        self.assertIn("if (!repeat && node.summaryAnchorUuid) {", ts, "the modal's brief line prefers the brief's own landing")
        self.assertIn("anchorUuid: su, quote: sq", ts, "…and sends its span as the click's quote")
        self.assertIn("summaryAnchorUuid?: string | null;                            // the brief/summary line's own landing", ts)


if __name__ == "__main__":
    unittest.main()
