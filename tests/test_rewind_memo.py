#!/usr/bin/env python3
"""T391 (2026-09-12): the judges' incident scan walked every dead episode file of a lineage whole at every boot (`_per_file_rewound`
through `em.file_rewound` with no rompuuid: 542 MB in four reads on one devbox boot). The verdict set per FROZEN file is now the
fold `rewoundUuids` of that file's fold document: written from the walk's own read at the quiescence drop, restored at the next
process, retired by an append or rewrite, capped like every fold state, falling to the walk on a corrupt document. Synthetic
transcripts only (the golden builders)."""
import gzip
import inspect
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_asm_checkpoint import em, G, SID, NOW, Harness, kernel_module   # noqa: E402  the harness and the golden builders


class RewoundMemo(Harness):
    def setUp(self):
        super().setUp()
        em._REWOUND_CACHE.clear()
        with em._CKPT_LOCK:
            for k in em._REWOUND_STATS:
                em._REWOUND_STATS[k] = 0
            em._FOLD_DIRTY.clear()
        with em._JSONL_CACHE_LOCK:
            em._RECORD_CACHE_STATS["wholeReads"] = {}
        self.saved_drop = em._DROP_AFTER_QUIESCENT_S

    def tearDown(self):
        em._DROP_AFTER_QUIESCENT_S = self.saved_drop
        super().tearDown()

    def frozen(self, name="dead", scenario="rewind_off_path", age=600):
        """A dead episode's transcript: a scenario with a rewound branch, idle past the reader's quiescence window."""
        records, sent = G.SINGLE_FILE[scenario]
        path = self.write(name, records(), sent=sent)
        old = time.time() - age; os.utime(path, (old, old))
        return path

    def fresh_process(self):
        self.fresh(); em.set_checkpoint_dir(lambda: self.ck)
        for c in list(em._FOLD_REG.values()):
            c.clear()
        em._REWOUND_CACHE.clear()
        with em._CKPT_LOCK:
            for k in em._REWOUND_STATS:
                em._REWOUND_STATS[k] = 0

    def whole_reads(self, path):
        return sum(v["bytes"] for k, v in em.record_cache_stats()["wholeReads"].items())

    def test_a_frozen_file_is_walked_once_and_served_from_its_document_at_the_next_process(self):
        path = self.frozen()
        size = os.path.getsize(path)
        walked = em.file_rewound(path)                                # the verdicts the plain walk gives (the equivalence reference)
        self.assertTrue(walked, "the fixture has a rewound branch")
        self.fresh_process()
        got = em.rewound_uuids(path)
        self.assertEqual(got, walked, "the first call walks and answers the walk's verdicts")
        self.assertGreaterEqual(self.whole_reads(path), size, "the first process read the file whole, once")
        d = json.loads(em._ckpt_file(path).read_text())
        self.assertEqual(sorted(d["folds"]["rewoundUuids"]["state"]["uuids"]), sorted(walked), "the memo rides the fold document, written at the drop")
        st = em.rewound_memo_stats(); self.assertEqual((st["walked"], st["served"]), (1, 0))
        self.fresh_process()
        with em._JSONL_CACHE_LOCK:
            em._RECORD_CACHE_STATS["wholeReads"] = {}
        read0 = em.read_bytes_report().get(path, 0)
        got2 = em.rewound_uuids(path)
        self.assertEqual(got2, walked, "served from the document: the same verdicts")
        self.assertEqual(self.whole_reads(path), 0, "no whole read at the next process")
        self.assertLess(em.read_bytes_report().get(path, 0) - read0, 512, "a tail read of nothing plus the guard: %d" % (em.read_bytes_report().get(path, 0) - read0))
        st = em.rewound_memo_stats(); self.assertEqual((st["walked"], st["served"]), (0, 1))

    def test_a_file_that_grows_after_the_memo_is_walked_again_and_the_memo_rewritten(self):
        path = self.frozen("grows")
        self.fresh_process(); first = em.rewound_uuids(path)
        seq = json.loads(em._ckpt_file(path).read_text())["seq"]
        records, _sent = G.SINGLE_FILE["rewind_off_path"]
        recs = records(); last = next(r for r in reversed(recs) if r.get("uuid"))
        t1 = max((em.parse_z(r.get("timestamp")) or 0) for r in recs if r.get("timestamp")) + 60
        with open(path, "a") as fh:
            fh.write(json.dumps(G.uline(t1, "one more question after the fact", "u_more", last["uuid"])) + "\n")
        old = time.time() - 600; os.utime(path, (old, old))            # frozen again, larger
        self.fresh_process()
        got = em.rewound_uuids(path)
        self.assertEqual(got, em.file_rewound(path), "the walk ran again over the grown file")
        st = em.rewound_memo_stats(); self.assertEqual((st["walked"], st["served"]), (1, 0), "%s" % st)
        d = json.loads(em._ckpt_file(path).read_text())
        self.assertGreater(d["seq"], seq, "the memo was rewritten")
        self.assertEqual(sorted(d["folds"]["rewoundUuids"]["state"]["uuids"]), sorted(got))

    def test_the_scan_takes_the_leaf_road_for_the_leaf_and_the_memo_for_a_dead_file(self):
        km = kernel_module(); jd = km.jd
        src = inspect.getsource(jd._per_file_rewound)
        self.assertIn("em.file_rewound(fp, rompuuid=fsid", src, "the leaf: the document's pre-cut verdicts and the tail")
        self.assertIn("em.rewound_uuids(fp)", src, "a dead file: the memo")
        self.assertLess(src.index("if fp == leaf:"), src.index("em.rewound_uuids(fp)"), "the leaf road decided first")

    def test_an_over_cap_set_is_recorded_as_such_and_walked_again(self):
        path = self.frozen("over")
        saved = em._CKPT_FOLD_CAP; em._CKPT_FOLD_CAP = 8                # a cap below any set: the memo is over it
        self.addCleanup(setattr, em, "_CKPT_FOLD_CAP", saved)
        self.fresh_process(); first = em.rewound_uuids(path)
        d = json.loads(em._ckpt_file(path).read_text())
        self.assertIn("over", d["folds"]["rewoundUuids"], "the cursor without its state, with the reason: %s" % d["folds"]["rewoundUuids"])
        self.fresh_process()
        got = em.rewound_uuids(path)
        self.assertEqual(got, first); self.assertEqual(em.rewound_memo_stats()["walked"], 1, "walked again: nothing to serve")

    def test_a_corrupt_document_falls_to_the_walk_with_a_counted_fallback(self):
        path = self.frozen("corrupt")
        self.fresh_process(); first = em.rewound_uuids(path)
        em._ckpt_file(path).write_text("{not json")
        self.fresh_process()
        em._CKPT_STATS["fallbacks"] = {}
        got = em.rewound_uuids(path)
        self.assertEqual(got, first, "the walk's verdicts, never a raise")
        self.assertEqual(em.rewound_memo_stats()["walked"], 1)
        self.assertTrue(em.checkpoint_stats()["fallbacks"], "the fallback counted: %s" % em.checkpoint_stats()["fallbacks"])


if __name__ == "__main__":
    unittest.main()
