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
        """All three call sites, by source: the plan pass (its migration pre-pass and its loop), the fast-forward on unmute,
        and the kernel's nudge placement gate (round three, low 4: the pin missed the fast-forward and rode a hasattr)."""
        km = kernel_module(); jd = km.jd
        src = inspect.getsource(jd._plan_session)
        self.assertEqual(src.count("plan_units(session, store, floor=floor, lazy_text=True)"), 2, "the migration pre-pass and the plan loop")
        self.assertIn("if text is None:", src, "the consumer reads the text after its filters (T377's road)")
        self.assertIn("plan_units(session, store, lazy_text=True)", inspect.getsource(jd.fast_forward_placements), "the fast-forward reads keys alone")
        self.assertIn('jd.plan_units({"turns": turns}, store, lazy_text=True)', inspect.getsource(km._nudge_placement_gate), "the nudge gate reads keys alone")

    def test_lazy_units_resolve_to_the_eager_units_in_every_field_over_every_golden_scenario(self):
        """The whole-unit comparison: over every golden scenario, whole and restored, the lazy units equal the eager ones in
        every field once the lazy text and quote are resolved as the plan pass resolves them (unit_text_for, _mint_quote)."""
        jd = kernel_module().jd
        store = {"rompUuid": SID, "seq": 0, "nodes": {}, "placements": {}, "status": {}, "placementsV": jd.PLACEMENTS_V}
        n = 0
        for name in G.SINGLE_FILE:
            records, sent = G.SINGLE_FILE[name]
            path = self.write("units-" + name, records(), sent=sent)
            for shape in ("whole", "restored"):
                self.fresh()
                if shape == "whole":
                    em._CKPT_DIR_FN = None
                    try:
                        tree = self.parse(path)
                    finally:
                        em.set_checkpoint_dir(lambda: self.ck)
                else:
                    self.parse(path); self.doc(path); self.fresh(); tree = self.parse(path)
                segs = {seg["id"]: seg for seg in _segments(tree)}
                eager = jd.plan_units(tree, store)
                lazy = jd.plan_units(tree, store, lazy_text=True)
                self.assertEqual(len(lazy), len(eager), "%s/%s" % (name, shape))
                for lu, eu in zip(lazy, eager):
                    with self.subTest(scenario=name, shape=shape, unit=(lu[0], lu[1])):
                        seg = segs[lu[0]]
                        text = lu[3] if lu[3] is not None else jd.unit_text_for(seg, lu[1])
                        quote = lu[7] if lu[7] is not None else jd._mint_quote(seg)
                        self.assertEqual((lu[0], lu[1], lu[2], text, lu[4], lu[5], lu[6], quote), tuple(eu))
                        n += 1
        self.assertGreater(n, 40, "units compared: %d" % n)

    def test_the_gates_blind_spots_and_the_consumers_retire(self):
        """Round three, low 1: a tool call without a name is not a unit (as _unit_text frames it); an assistant message whose
        content is a bare string is a blind spot the scalars cannot see (nt is computed from the normalized content), so the
        gate says non-empty while the text reads empty, and the plan pass RETIRES such a unit instead of skipping it, so the
        nudge placement gate never reads its key as unplanned forever."""
        km = kernel_module(); jd = km.jd
        nameless = {"type": "assistant", "uuid": "a", "t": 2.0, "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "", "input": {}}]}}
        self.assertFalse(jd._unit_nonempty([nameless]), "a nameless tool call is not framed")
        self.assertEqual(jd._unit_text([nameless]), "")
        bare = {"type": "assistant", "uuid": "a", "t": 2.0, "message": {"role": "assistant", "content": "a bare string the CLI never writes"}}
        self.assertTrue(jd._unit_nonempty([bare]), "the blind spot: the scalar sees text")
        self.assertEqual(jd._unit_text([bare]), "", "the framing sees no block")
        src = inspect.getsource(jd._plan_session)
        i = src.index("text = unit_text_for(seg, phase)")
        tail = src[i:i + 900]
        self.assertIn("if not text:", tail)
        self.assertIn('store["placements"][key] = None', tail, "an empty late read retires the unit")
        self.assertLess(tail.index('store["placements"][key] = None'), tail.index("continue"), "retired before the continue")

    def test_the_nudge_gates_except_leg_is_counted_and_not_entered_by_a_widened_stub(self):
        """Round three, low 3: six test modules stubbed plan_units without the keyword; the gate's except swallowed the TypeError
        into a stderr trace and answered not unplanned, and those modules stayed green by accident. The leg is counted now
        (memos.nudgeGate.failed), a widened stub never enters it, and a narrow one does."""
        km = kernel_module(); jd = km.jd
        saved = jd.plan_units
        self.addCleanup(setattr, jd, "plan_units", saved)
        km._NUDGE_GATE_STATS["failed"] = 0
        turns = [{"id": "t1", "t": 1.0, "end": 2.0, "ended": True, "atoms": [], "trigger": None}]
        jd.plan_units = lambda session, store, **kw: []
        km._nudge_placement_gate(SID, turns, {"placements": {}})
        self.assertEqual(km._NUDGE_GATE_STATS["failed"], 0, "a widened stub: the leg not entered")
        jd.plan_units = lambda session, store: []
        import io
        err = io.StringIO(); saved_err = sys.stderr; sys.stderr = err
        try:
            self.assertFalse(km._nudge_placement_gate(SID, turns, {"placements": {}}))
        finally:
            sys.stderr = saved_err
        self.assertEqual(km._NUDGE_GATE_STATS["failed"], 1, "a narrow stub: the leg entered and counted")
        self.assertIn("lazy_text", err.getvalue())


if __name__ == "__main__":
    unittest.main()
