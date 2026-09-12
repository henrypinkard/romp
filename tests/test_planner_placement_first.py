#!/usr/bin/env python3
"""T377 (2026-09-12): the planner decides a unit's placement before it reads the unit's text, and its consumer trusts the same
verdict. Two review findings pinned here: the placement verdict's one volatile input, the episode floor, is taken ONCE per pass
and handed to both the planner and its consumer (a /clear landing mid-pass raised the floor between them, and a unit the
planner had yielded as placed reached the model with no text); and the placement lookup is an index built once per planner
call, not a walk of every recorded key per segment (the nudge gate's derivation grew twelve-fold). Synthetic transcripts."""
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_judge_apierror_no_fabricated_done import jd, uline, aline, SID, NOW, iso   # noqa: E402  the consumer harness


def _records(n):
    recs, prev, t = [], None, NOW - 4000
    for i in range(n):
        u, a = "u%03d" % i, "a%03d" % i
        recs.append(uline(t, "please handle item number %d for the notes api" % i, u, prev))
        recs.append(aline(t + 10, "handled item %d" % i, a, u))
        prev, t = a, t + 60
    return recs


class FloorTakenOncePerPass(unittest.TestCase):
    def test_a_floor_rising_after_the_planner_returns_never_sends_a_unit_without_text_to_the_model(self):
        calls = []
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); tpath = td / (SID + ".jsonl")
            tpath.write_text("\n".join(json.dumps(r) for r in _records(2)) + "\n")
            saved = (jd.GOALDIR, jd.PCACHE, jd.plan_llm, jd.opener_llm, jd._group_store, jd.episode_floor)
            jd.GOALDIR, jd.PCACHE = td / "goals", td / "pcache"
            def fake(text, *a, **k):
                calls.append(text); return '{"ops":[]}'
            jd.plan_llm = jd.opener_llm = fake
            jd._group_store = lambda *a, **k: None
            try:
                jd._PARSE_CACHE.clear(); jd._CHAIN_MEMO.clear()
                session = jd.parsed_session(SID, [str(tpath)], NOW)
                units = jd.plan_units(session, {"placements": {}, "nodes": {}, "seq": 0})
                self.assertTrue(units)
                store = jd.load_goals(SID)
                for u in units:                                        # every unit recorded under a DRIFTED key (the same text hash,
                    key = jd._unit_key(u[0], u[1])                     #  an earlier t): a fuzzy hit while the episode floor is low
                    parts = key.split(":"); parts[-2] = str(float(parts[-2]) - 100)
                    store["placements"][":".join(parts)] = None
                store["placementsV"] = jd.PLACEMENTS_V                 # no migration pass: the planner is called once
                jd.save_goals(SID, store)
                last_t = max(u[2] for u in units)
                state = {"after": False}
                real_plan_units = jd.plan_units
                def planned(*a, **k):                                  # the floor rises the moment the planner returns: the /clear
                    out = real_plan_units(*a, **k); state["after"] = True; return out   #  landing mid-pass
                jd.plan_units = planned
                jd.episode_floor = lambda sid: (last_t - 50) if state["after"] else 0   # between the drifted key's t and the unit's
                jd._plan_session(SID, str(tpath), NOW)                 #  own: not retired, but its recorded twin no longer dedups it
            finally:
                jd.plan_units = real_plan_units
                (jd.GOALDIR, jd.PCACHE, jd.plan_llm, jd.opener_llm, jd._group_store, jd.episode_floor) = saved
        self.assertTrue(all(isinstance(t, str) and t for t in calls), "the model never sees a unit without text: %r" % calls)


class PlacementLookupIsAnIndex(unittest.TestCase):
    def test_the_lookup_cost_is_a_build_once_index_not_a_walk_per_segment(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); tpath = td / (SID + ".jsonl")
            n = 60
            tpath.write_text("\n".join(json.dumps(r) for r in _records(n)) + "\n")
            jd._PARSE_CACHE.clear(); jd._CHAIN_MEMO.clear()
            session = jd.parsed_session(SID, [str(tpath)], NOW)
            placements = {"%s:%d:%08x" % (SID, NOW - 90000 + i, i): None for i in range(2300)}   # 2,300 recorded keys, none ours
            store = {"placements": placements, "nodes": {}, "seq": 0}
            count = [0]; real = jd._seg_key
            def counting(k):
                count[0] += 1; return real(k)
            jd._seg_key = counting
            try:
                units = jd.plan_units(session, store)
            finally:
                jd._seg_key = real
            self.assertGreaterEqual(len(units), n)
            self.assertLessEqual(count[0], len(placements) + 12 * n,
                                 "one normalization per recorded key and a handful per segment, not a walk per segment: %d" % count[0])


if __name__ == "__main__":
    unittest.main()
