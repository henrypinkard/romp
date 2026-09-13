#!/usr/bin/env python3
"""T396 (2026-09-12): a continuously active session never got an assembly document while its kernel lived. The settle's
document write compared the reader entry's record offsets against the tree's records by count, and a live leaf grows between
the settle's parse and the write (the CLI appends while the settle runs), so every write met an entry one record longer than
its tree and skipped ("offsets"); at every boot the leaf was read whole by whichever reader came first (120 MB through the
interrupt tick's judge parse on the boot after the T384 follow-up). The write takes the entry's prefix under the tree's own
generation. Synthetic transcripts only (the golden builders)."""
import gzip
import json
import os
import sys
import unittest
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_asm_checkpoint import em, G, SID, NOW, Harness, kernel_module, compacting_variant, _strip   # noqa: E402


class WriteOverGrownEntry(Harness):
    def _whole(self):
        return {k: v["bytes"] for k, v in em.record_cache_stats()["wholeReads"].items()}

    def _reset(self):
        with em._JSONL_CACHE_LOCK:
            em._RECORD_CACHE_STATS["wholeReads"] = {}

    def _parsed_then_grown(self, name):
        """A whole parse of a leaf, then one record appended and the reader's entry extended past the tree's records."""
        records, sent = G.SINGLE_FILE["compaction_atom"]
        path = self.write(name, records(), sent=sent)
        self.fresh()
        tree = self.parse(path)
        recs = records(); last = next(r for r in reversed(recs) if r.get("uuid"))
        t1 = max((em.parse_z(r.get("timestamp")) or 0) for r in recs if r.get("timestamp")) + 60
        with open(path, "a") as fh:
            fh.write(json.dumps(G.uline(t1, "one more line while the settle ran", "u_race", last["uuid"])) + "\n")
        em._read_jsonl_entry(path, tail_ok=True)                        # another reader extends the entry: same generation, one more record
        em._ASM_CKPT_STATS["skipped"] = {}
        return path, tree

    def test_a_leaf_that_grew_after_the_settles_parse_still_gets_its_document(self):
        path, tree = self._parsed_then_grown("grown")
        reasons = []
        self.assertTrue(em.asm_checkpoint_write(path, SID, False, tree=tree, reason_out=reasons), "written: %r %r" % (reasons, em._ASM_CKPT_STATS["skipped"]))
        self.assertTrue(em._asm_ckpt_file(path).exists(), "the document is on disk")
        self.fresh(); modes = []; self._reset()
        restored = self.parse(path, modes)
        self.assertEqual(modes, ["restore"], "the next process restores from it")
        self.assertEqual(self._whole(), {}, "and reads nothing whole")
        uuids = {a.get("uuid") for t in restored["turns"] for a in t["atoms"]}
        self.assertIn("u_race", uuids, "the record appended after the parse is in the restored tree's tail")
        self.fresh(); whole = self.parse(path)
        self.assertEqual([len(t["atoms"]) for t in restored["turns"]], [len(t["atoms"]) for t in whole["turns"]], "restored equals whole")

    def test_an_entry_under_another_generation_is_still_refused(self):
        """A longer entry whose generation is not the tree's (a refold from zero after the append) does not lend its offsets."""
        path, tree = self._parsed_then_grown("regen")
        with em._JSONL_CACHE_LOCK:
            em._JSONL_CACHE.pop(str(path), None)
        em._read_jsonl_entry(path, tail_ok=False)                        # a fresh generation over the grown file
        reasons = []
        self.assertFalse(em.asm_checkpoint_write(path, SID, False, tree=tree, reason_out=reasons))
        self.assertEqual(reasons, ["offsets"], "%r" % reasons)

    def test_the_judges_parse_over_a_restored_tree_reads_nothing_whole(self):
        """The interrupt tick's road (jd.parsed_session): over a leaf with a document it restores, whether or not the display
        parsed first; the boot's whole read was the missing document, not a reader rule."""
        km = kernel_module(); jd = km.jd
        records, sent = G.SINGLE_FILE["compaction_atom"]
        path = self.write("tick", records(), sent=sent)
        self.fresh(); self.parse(path); self.assertTrue(self.doc(path))
        for display_first in (False, True):
            self.fresh(); jd._PARSE_CACHE.clear(); jd._CHAIN_MEMO.clear()
            if display_first:
                self.parse(path)
            self._reset(); modes = []
            turns = jd.parsed_session(SID, [str(path)], NOW, asm_mode_out=modes)["turns"]
            self.assertEqual(modes, ["serve" if display_first else "restore"])
            self.assertEqual(self._whole(), {}, "display first %r" % display_first)
            km._interrupt_marks(turns, SID, family="judge")
            self.assertEqual(self._whole(), {})

    def _lineage(self, name):
        """The resume lineage (a prior file A wholly before the cut, the leaf B compacting), parsed whole once; returns
        (pa, pb, cands, states, parse, tree)."""
        d = self.td / name; d.mkdir()
        pa, pb = d / (G.FSID_A + ".jsonl"), d / (G.FSID_B + ".jsonl")
        pa.write_text("".join(json.dumps(r) + "\n" for r in G.scenario_resume_lineage_fileA()))
        pb.write_text("".join(json.dumps(r) + "\n" for r in compacting_variant(G.scenario_resume_lineage_fileB(), "lin")))
        states = getattr(G, "RESUME_STATES", None); cands = [str(pa), str(pb)]
        def parse(modes=None):
            return em.parse_session(str(pb), rompuuid=SID, name="impl", dir="/TESTDIR", candidate_files=cands, states=states,
                                    postal_log=[], now=NOW, asm_mode_out=modes)
        self.fresh()
        tree = parse()
        em._ASM_CKPT_STATS["skipped"] = {}
        return pa, pb, cands, states, parse, tree

    def _append_to_prior(self, pa):
        recs = G.scenario_resume_lineage_fileA(); last = next(r for r in reversed(recs) if r.get("uuid"))
        t1 = max((em.parse_z(r.get("timestamp")) or 0) for r in recs if r.get("timestamp")) + 60
        with open(pa, "a") as fh:                                       # the prior file's own session resumed in another pane
            fh.write(json.dumps(G.uline(t1, "the prior session speaks again", "u_prior_late", last["uuid"])) + "\n")

    def test_a_lineage_file_longer_than_the_tree_still_refuses_the_write(self):
        """Round one, medium, the half with a reader in between: the prefix rule is the LEAF's. A prior file that gained a
        record after the parse, its entry extended by a reader under the same generation, must not be stamped as wholly
        before the cut with the appended record missing from every restore."""
        pa, pb, cands, states, parse, tree = self._lineage("lin-grown")
        self._append_to_prior(pa)
        em._read_jsonl_entry(pa, tail_ok=True)
        reasons = []
        self.assertFalse(em.asm_checkpoint_write(str(pb), SID, False, tree=tree, reason_out=reasons), "refused: %r" % reasons)
        self.assertEqual(reasons, ["offsets"])

    def test_a_skip_rows_witness_is_the_stat_the_tree_was_parsed_from(self):
        """Round one, medium, the half with no reader in between: the skip row used to carry the WRITE-time stat, so a record
        the prior file gained between the parse and the write verified at the next boot and the restore served a tree
        missing it for the leaf's whole kernel life. The row carries the stat of the records the tree was parsed from, and
        the next boot's check fails (lineage) and parses whole."""
        pa, pb, cands, states, parse, tree = self._lineage("lin-stat")
        self._append_to_prior(pa)                                       # no reader extends A's entry: the tree is stale, unseen
        reasons = []
        self.assertTrue(em.asm_checkpoint_write(str(pb), SID, False, tree=tree, reason_out=reasons), "written: %r" % reasons)
        self.fresh(); modes = []
        restored = parse(modes)
        self.assertEqual(modes, ["full"], "the prior file's stat moved past the row's witness: no restore")
        self.assertIn("lineage", em.asm_checkpoint_stats()["fallbacks"])
        self.fresh(); saved = em._CKPT_DIR_FN; em._CKPT_DIR_FN = None
        try:
            whole = parse()
        finally:
            em._CKPT_DIR_FN = saved
        self.assertEqual(_strip(restored), _strip(whole))

    def test_a_restored_trees_adapter_carries_the_prior_files_witness_forward(self):
        """A tree restored from a document never read the prior file (its skip row's stat was verified at load); a rewrite
        from that tree needs the same witness for its own skip row, so the seed carries it and the adapter holds it."""
        pa, pb, cands, states, parse, tree = self._lineage("lin-carry")
        self.assertTrue(em.asm_checkpoint_write(str(pb), SID, False, tree=tree))
        doc = json.load(gzip.open(em._asm_ckpt_file(str(pb))))
        row = doc["files"][G.FSID_A]; self.assertTrue(row.get("skip"))
        st = os.stat(pa)
        self.assertEqual((row["size"], row["mtime"]), (st.st_size, st.st_mtime), "the first write's witness is the read's stat")
        seed, _landed = em._seed_from_doc(doc)
        self.assertEqual(seed["stat"][G.FSID_A], (row["size"], row["mtime"]), "the seed carries the skip row's witness")
        ad = em.FileAdapter(cands, str(pb), seed=seed)
        self.assertEqual(ad._src_stat[str(pa)], (row["size"], row["mtime"]), "the adapter holds it for the next write")
        self.assertEqual(ad._src_keys[str(pa)], ("skip",))


if __name__ == "__main__":
    unittest.main()
