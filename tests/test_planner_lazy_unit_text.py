#!/usr/bin/env python3
"""T396 (2026-09-12): the planner read the unit text of every unplaced segment at every pass, as its emptiness gate and as the
yielded text, before its consumer's filters decided whether the unit reaches the model (42.8 MB of assistant bodies hydrated on
one boot through _unit_text<-_seam_text). The production callers now take the units lazily: the emptiness gate is decided from
the markers' scalars and the user bodies (_unit_nonempty), the text and the quote are read by _plan_session after its filters,
through the placed-yield road T377 built. Synthetic transcripts only (the golden builders)."""
import inspect
import os
import sys
import unittest
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_asm_checkpoint import em, G, SID, NOW, Harness, kernel_module   # noqa: E402


def _segments(tree):
    return [seg for t in tree["turns"] for seg in em.segments(t)]


class LazyUnitText(Harness):
    def test_the_scalar_emptiness_gate_equals_the_unit_texts_over_every_golden_scenario(self):
        jd = kernel_module().jd
        n = 0
        for name in G.SINGLE_FILE:
            records, sent = G.SINGLE_FILE[name]
            path = self.write("eq-" + name, records(), sent=sent)
            self.fresh(); em._CKPT_DIR_FN = None
            try:
                tree = self.parse(path)
            finally:
                em.set_checkpoint_dir(lambda: self.ck)
            for seg in _segments(tree):
                with self.subTest(scenario=name, seg=seg["id"]):
                    self.assertEqual(jd._unit_nonempty(seg["atoms"]), bool(jd._seam_text(seg)))
                    n += 1
        self.assertGreater(n, 20, "segments compared: %d" % n)

    def test_the_gate_over_the_three_sources_and_their_blind_spots(self):
        jd = kernel_module().jd
        user = lambda text, author="human": {"type": "user", "author": author, "uuid": "u", "t": 1.0,   # noqa: E731
                                            "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
        asst = lambda blocks, **kw: dict({"type": "assistant", "uuid": "a", "t": 2.0,                    # noqa: E731
                                          "message": {"role": "assistant", "content": blocks}}, **kw)
        self.assertTrue(jd._unit_nonempty([user("a real ask")]))
        self.assertTrue(jd._unit_nonempty([user("a peer's report", author="teammate")]), "a report is framed too")
        self.assertFalse(jd._unit_nonempty([user("<!-- romp-injected -->")]), "a text of romp markers alone strips to nothing")
        self.assertFalse(jd._unit_nonempty([dict(user("authorless"), author=None)]), "an authorless user atom is not framed")
        self.assertTrue(jd._unit_nonempty([asst([{"type": "text", "text": "a reply"}])]))
        self.assertFalse(jd._unit_nonempty([asst([{"type": "text", "text": "overloaded"}], isApiError=True)]), "an API error is noise")
        self.assertTrue(jd._unit_nonempty([asst([{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}])]), "a tool call alone is a unit")
        self.assertFalse(jd._unit_nonempty([asst([{"type": "thinking", "thinking": "hm"}])]), "thinking alone is not")
        for atoms in ([user("a real ask")], [asst([{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}])],
                      [asst([{"type": "text", "text": "overloaded"}], isApiError=True)], [user("<!-- romp-injected -->")]):
            self.assertEqual(jd._unit_nonempty(atoms), bool(jd._unit_text(atoms)), "%r" % atoms)

    def test_lazy_units_match_the_eager_ones_and_read_no_assistant_body(self):
        jd = kernel_module().jd
        records, sent = G.SINGLE_FILE["compaction_atom"]
        path = self.write("lazy", records(), sent=sent)
        self.fresh(); self.parse(path); self.assertTrue(self.doc(path))
        self.fresh(); modes = []; tree = self.parse(path, modes); self.assertEqual(modes, ["restore"])
        store = {"rompUuid": SID, "seq": 0, "nodes": {}, "placements": {}, "status": {}, "placementsV": jd.PLACEMENTS_V}
        em._ASM_CKPT_STATS.update(hydratedAtoms=0, hydratedBytes=0, hydratedBy={})
        lazy = jd.plan_units(tree, store, lazy_text=True)
        by = dict(em.asm_checkpoint_stats()["hydratedBy"])
        self.assertFalse([k for k in by if k.startswith("_unit_text")], "no unit text read for the lazy units: %s" % by)
        eager = jd.plan_units(tree, store)
        self.assertEqual([(u[0], u[1]) for u in lazy], [(u[0], u[1]) for u in eager], "the same units, in order")
        self.assertTrue(any(u[1] != "prompt" for u in lazy), "the fixture has work units")
        for u in lazy:
            if u[1] != "prompt":
                self.assertIsNone(u[3], "a lazy unit carries no text: %r" % (u[:2],)); self.assertIsNone(u[7])
        for lu, eu in zip(lazy, eager):
            seg = next(s for s in _segments(tree) if s["id"] == lu[0])
            self.assertEqual(jd.unit_text_for(seg, lu[1]), eu[3], "the consumer's late read equals the eager text")

    def test_the_production_callers_take_the_units_lazily(self):
        km = kernel_module(); jd = km.jd
        src = inspect.getsource(jd._plan_session)
        self.assertEqual(src.count("plan_units(session, store, floor=floor, lazy_text=True)"), 2, "the migration pre-pass and the plan loop")
        self.assertIn("if text is None:", src, "the consumer reads the text after its filters (T377's road)")
        self.assertIn("lazy_text=True", inspect.getsource(km._auto_nudge_unplanned) if hasattr(km, "_auto_nudge_unplanned") else
                      open(km.__file__).read().split('jd.plan_units({"turns": turns}, store')[1][:40], "the nudge gate reads keys alone")


if __name__ == "__main__":
    unittest.main()
