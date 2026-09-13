#!/usr/bin/env python3
"""T397 (2026-09-12): a boot's first pusher cycle took 59 s against 25 to 33 s all day, and /perf kept only cumulative stage
totals and a ring of whole-cycle durations, so nothing named the stage. The pusher keeps each cycle's stage split (wall, the
reader's bytes, the hydrated bytes), the boot's first for the process under `pusher.firstCycle`, the last cycles in a ring
sized as a fraction of memory under `pusher.stageRing`, and the restart ledger's boot-health row carries the first split."""
import os
import sys
import time
import unittest
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_asm_checkpoint import em, kernel_module   # noqa: E402


class StageSplitUnit(unittest.TestCase):
    def setUp(self):
        self.km = kernel_module()

    def test_the_ring_is_a_fraction_of_memory_never_a_literal(self):
        km = self.km
        self.assertEqual(km._stage_ring_len(64 * 1024 ** 3), 1024, "one cycle per 64 MiB: a 64 GB box keeps 1024")
        self.assertEqual(km._stage_ring_len(4 * 1024 ** 3), 64)
        self.assertEqual(km._stage_ring_len(512 * 1024 ** 2), 16, "the floor")
        self.assertEqual(km._stage_ring_len(0), 16)
        self.assertGreaterEqual(km._stage_ring_len(), 16, "the machine's reading")

    def test_the_first_cycle_is_kept_and_every_cycle_rides_the_ring(self):
        km = self.km
        ps = km._PerfStats()
        ps.cycle_begin()
        ps.stage("push.chat", 0.010); ps.stage("push", 0.010); ps.stage("jobs", 0.005)
        ps.cycle(0.020)
        ps.cycle_begin()
        ps.stage("jobs", 0.001)
        ps.cycle(0.002)
        snap = ps.snapshot()["pusher"]
        first = snap["firstCycle"]
        self.assertEqual(first["s"], 0.02)
        self.assertEqual(sorted(first["stages"]), ["jobs", "push", "push.chat"])
        self.assertAlmostEqual(first["stages"]["push.chat"]["ms"], 10.0)
        self.assertEqual(set(first["stages"]["jobs"]), {"ms", "bytes", "hydrated"})
        self.assertEqual(len(snap["stageRing"]), 2, "both cycles in the ring")
        self.assertEqual(snap["stageRing"][1]["stages"], {"jobs": {"ms": 1.0, "bytes": 0, "hydrated": 0}})
        self.assertEqual(snap["stageRingMax"], km._stage_ring_len())
        self.assertIsNone(km._PerfStats().snapshot()["pusher"]["firstCycle"], "no cycle yet: no split")

    def test_a_stages_bytes_are_the_readers_bytes_since_the_previous_boundary(self):
        km = self.km
        ps = km._PerfStats()
        ps.cycle_begin()
        em._count_read("/lab/a.jsonl", 1000)                 # a read during the jobs before the push
        ps.stage_boundary()                                  # the push begins: those bytes are the jobs'
        em._count_read("/lab/b.jsonl", 250)                  # a read during the chat build
        ps.stage("push.chat", 0.001)
        ps.stage("push", 0.001)
        em._count_read("/lab/c.jsonl", 50)                   # a read during the jobs after the push
        ps.stage("jobs", 0.001)
        ps.cycle(0.003)
        st = ps.snapshot()["pusher"]["firstCycle"]["stages"]
        self.assertEqual(st["push.chat"]["bytes"], 250)
        self.assertEqual(st["push"]["bytes"], 250, "the container carries its sub-stages' bytes")
        self.assertEqual(st["jobs"]["bytes"], 1050, "the jobs before and after the push")


class LabBootFirstCycle(unittest.TestCase):
    """A lab boot whose first cycle runs at least two stages: the real pusher cycle with every tick job a no-op and the push a
    short sleep, over a hermetic kernel module; the split names both stages, and the boot-health row carries it."""
    JOBS = ("_judge_tick", "_nudge_tick", "_reconcile_tick")

    def setUp(self):
        self.km = km = kernel_module()
        self.saved = (km.NAMES, km._live_map, km._push_all, km._append_restart_cut, km._BOOT_HEALTH_DONE[0])
        km.NAMES = {}
        km._live_map = lambda: {}
        self.rows = []
        km._append_restart_cut = lambda row: self.rows.append(row)
        km._BOOT_HEALTH_DONE[0] = False
        km._PERF_STATS.reset()

    def tearDown(self):
        km = self.km
        km.NAMES, km._live_map, km._push_all, km._append_restart_cut, km._BOOT_HEALTH_DONE[0] = self.saved
        km._PERF_STATS.reset()

    def test_the_boots_first_cycle_names_its_stages(self):
        km = self.km
        km._push_all = lambda live_map=None: time.sleep(0.005)
        t0 = time.monotonic()
        km._pusher_cycle_jobs(int(time.time()), {}, True)
        dt = time.monotonic() - t0
        km._PERF_STATS.cycle(dt)
        km._boot_health_first_cycle(dt)
        snap = km._PERF_STATS.snapshot()["pusher"]
        first = snap["firstCycle"]
        self.assertIsNotNone(first, "the first cycle's split is kept")
        self.assertTrue({"jobs", "push"} <= set(first["stages"]), "both stages named: %r" % sorted(first["stages"]))
        self.assertGreaterEqual(first["stages"]["push"]["ms"], 5.0)
        self.assertLessEqual(sum(v["ms"] for k, v in first["stages"].items() if k in ("jobs", "push")), first["s"] * 1000.0 + 5.0,
                             "the stages fit the cycle's wall")
        self.assertEqual(len(self.rows), 1, "one boot-health row")
        self.assertEqual(sorted(self.rows[0]["stages"]), sorted(first["stages"]), "the row carries the split")
        self.assertEqual(self.rows[0]["firstCycleS"], round(dt, 2))


if __name__ == "__main__":
    unittest.main()
