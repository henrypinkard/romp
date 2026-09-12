#!/usr/bin/env python3
"""T396 (2026-09-12): a continuously active session never got an assembly document while its kernel lived. The settle's
document write compared the reader entry's record offsets against the tree's records by count, and a live leaf grows between
the settle's parse and the write (the CLI appends while the settle runs), so every write met an entry one record longer than
its tree and skipped ("offsets"); at every boot the leaf was read whole by whichever reader came first (120 MB through the
interrupt tick's judge parse on the boot after the T384 follow-up). The write takes the entry's prefix under the tree's own
generation. Synthetic transcripts only (the golden builders)."""
import json
import os
import sys
import unittest
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_asm_checkpoint import em, G, SID, NOW, Harness, kernel_module   # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
