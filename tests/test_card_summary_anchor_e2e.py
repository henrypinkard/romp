#!/usr/bin/env python3
"""The card's brief click, end to end through build_feed (T388): a blocked card whose brief has no validated
citation, whose newest trail segment holds only a tool call, and whose wrap-up sits in the same turn's second
segment. The base landed on the tool call (the segment's first landable atom, a collapsed tool group); the head
lands on the text atom that carries the brief's opening sentence, with the span the chat highlights. The same
harness shows a body read that raises leaving build_feed whole. SYNTHETIC fixtures only; a private synthetic sid."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.realpath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
os.environ["ROMP_KERNEL_NO_OPEN"] = "1"
os.environ.setdefault("ROMP_SERVE_TOKEN", "testtok")
os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp()
os.environ.pop("ROMP_STATE_DIR", None)  # a live kernel's export outranks the XDG floor
from romp_load import load_source
km = load_source("romp_kernel_anche2e", os.path.join(BIN, "romp-kernel"))
jd = km.jd

NOW = 1_788_300_000
T0 = NOW - 3600
SID = "f11e0002-1111-4222-8333-000000000002"    # private synthetic sid, never the shared placeholder
WRAP = ("Four questions before I go on. Should the history budget follow the device or the setting? "
        "Which client do the tests target? Do we keep the old exporter? Who owns the glossary file?")
BRIEF = "Should the history budget follow the device or the setting? The session asks four things it cannot decide alone."


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def uline(t, text, uuid, parent=None):
    return {"type": "user", "timestamp": iso(t), "uuid": uuid, "parentUuid": parent,
            "promptSource": "typed", "message": {"role": "user", "content": text}}


def tline(t, uuid, parent):
    return {"type": "assistant", "timestamp": iso(t), "uuid": uuid, "parentUuid": parent,
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "tu-" + uuid, "name": "Bash",
                                                          "input": {"command": "true"}}],
                        "stop_reason": "tool_use"}}


def aline(t, text, uuid, parent):
    return {"type": "assistant", "timestamp": iso(t), "uuid": uuid, "parentUuid": parent,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}}


class TheBriefClickEndToEnd(unittest.TestCase):
    def setUp(self):
        km._downtime[:] = []
        self.td = tempfile.TemporaryDirectory()
        td = Path(self.td.name)
        cdir = td / "launchdir"
        cdir.mkdir()
        proj = td / "projects"
        import re as _re
        pdir = proj / _re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(str(cdir)))
        pdir.mkdir(parents=True)
        # one turn, two segments: the typed opener and a shell call, then a typed prompt absorbed mid-turn and the
        # wrap-up that carries the four questions, thirteen minutes after the call
        recs = [uline(T0, "land the history gaps change", "u1"),
                tline(T0 + 60, "a1", "u1"),
                uline(T0 + 120, "keep going", "u2", "a1"),
                aline(T0 + 840, WRAP, "t9", "u2")]
        self.tpath = pdir / (SID + ".jsonl")
        self.tpath.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        names = td / "names"
        names.mkdir()
        (names / SID).write_text("web\t%s\t#abcdef\n" % str(cdir))
        self.saved = (jd.NAMES, jd.PROJECTS, jd.CAPDIR, jd.ARCHDIR, jd.GOALDIR, jd.STATE,
                      km.NAMES, km._live_map, km._GLOBAL_CLAUDE_MD, jd.gist_llm)
        jd.gist_llm = lambda p: ""
        km._autonudge_cache.clear()
        km._GLOBAL_CLAUDE_MD = td / "no-global-claude.md"
        jd.NAMES, jd.PROJECTS = names, proj
        jd.CAPDIR, jd.ARCHDIR, jd.GOALDIR = td / "captions", td / "archive", td / "goals"
        jd.STATE = td
        km.NAMES = names
        km._live_map = lambda: {SID: {"state": "idle", "since": NOW - 100, "model": "", "effort": "",
                                     "context": None, "compactPct": None, "color": None}}
        jd.GOALDIR.mkdir(parents=True, exist_ok=True)
        s = jd.parsed_session(SID, [str(self.tpath)], NOW)
        st0 = {"rompUuid": SID, "nodes": {}, "placements": {}, "status": {}}
        self.segs = [sg["id"] for turn in s["turns"] for sg in jd._segs(turn, st0)]
        km._SUMMARY_ANCHOR_MEMO.clear()

    def tearDown(self):
        (jd.NAMES, jd.PROJECTS, jd.CAPDIR, jd.ARCHDIR, jd.GOALDIR, jd.STATE,
         km.NAMES, km._live_map, km._GLOBAL_CLAUDE_MD, jd.gist_llm) = self.saved
        km._autonudge_cache.clear()
        self.td.cleanup()

    def _store(self, trail):
        g = SID + ":g1"
        (jd.GOALDIR / (SID + ".json")).write_text(json.dumps({
            "rompUuid": SID, "seq": 1, "lastNode": g,
            "nodes": {g: {"id": g, "text": "Land the history gaps change", "parentId": None,
                          "nodeComplete": False, "blocked": True, "cleared": False,
                          "trail": trail, "t": T0, "mt": T0 + 900,
                          "blockWhy": "four questions the user must answer", "blockSummary": BRIEF,
                          "summaryAnchor": None, "briefedMt": T0 + 900,
                          "log": [{"ev_t": T0 + 850, "src": "closer", "kind": "block", "at": T0 + 850,
                                   "why": "four questions the user must answer"}]}},
            "placements": {}, "status": {g: "blocked"}}))
        return g

    def _card(self, g):
        km._parse(str(self.tpath), SID, NOW)           # warm the kernel parse cache: the anchor tiers read it
        return next(a for a in km.build_feed(NOW)["asks"] if a.get("itemId") == g)

    def test_the_turn_holds_two_segments_the_first_a_tool_call_only(self):
        self.assertEqual(len(self.segs), 2, self.segs)

    def test_the_brief_click_lands_on_the_wrap_up_text_atom_not_the_tool_call(self):
        g = self._store(trail=[self.segs[0]])          # the newest trail segment: the tool call only
        card = self._card(g)
        self.assertEqual(card["summaryAnchorUuid"], "t9", "the text atom that carries the brief's opening sentence (the base: a1, the tool call)")
        self.assertEqual(card["summaryAnchorQuote"], "Should the history budget follow the device or the setting?")
        row = next(r for r in card["tree"] if r["id"] == g)
        self.assertEqual((row["summaryAnchorUuid"], row["summaryAnchorQuote"]), ("t9", card["summaryAnchorQuote"]),
                         "the modal's row carries the same landing")
        self.assertEqual(row["anchorUuid"], "a1", "the work anchor stays the segment's landable atom for the mark and time zones")

    def test_a_body_read_that_raises_leaves_build_feed_whole(self):
        g = self._store(trail=[self.segs[0]])
        real = km.jd._atom_text
        def boom(a):                                   # the wrap-up's body cannot be read; every other read is real
            if a.get("uuid") == "t9":
                raise km.em.LazyBodyRead("no record at the offset")
            return real(a)
        km.jd._atom_text = boom
        try:
            try:
                card = self._card(g)
            except Exception as ex:
                self.fail("build_feed raised on one unreadable body, so no session got a feed this cycle: %r" % (ex,))
        finally:
            km.jd._atom_text = real
        self.assertEqual(card["summaryAnchorUuid"], "t9", "no quote could be located, so the tier falls to the substantive text atom, never a raise")
        self.assertIsNone(card["summaryAnchorQuote"])
        self.assertGreaterEqual(km._SUMMARY_ANCHOR_STATS["fault"], 1)


if __name__ == "__main__":
    unittest.main()
