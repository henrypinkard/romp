#!/usr/bin/env python3
"""A hermetic kernel never runs the update check (2026-09-13). The check reads the release remote's tags over the
network (git ls-remote), and when the checkout's release is older than the newest tag it raises the shell's update
banner, a fixed alert at the top of the window. On CI that banner sat over the settings panel's pills and took every
click of the tab widgets lab (main red at the tab widgets merge), while the same lab passed on a machine whose
checkout read newer. So: ROMP_UPDATE_CHECK=off stands the check down before any read, every lab kernel runs with it
(tests/test_ship_reship.py kernel_env), and the driver's relaunch keeps it. Synthetic; hermetic state; no network."""
import os
import tempfile
import unittest
from unittest import mock

from romp_load import load_source

HERE = os.path.dirname(os.path.realpath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp()
os.environ.pop("ROMP_STATE_DIR", None)
os.environ["ROMP_KERNEL_NO_OPEN"] = "1"
os.environ.setdefault("ROMP_SERVE_TOKEN", "test-token-DO-NOT-USE")
os.environ["ROMP_MANAGER_PORT"] = "1"
load_source("romp_event_model", os.path.join(BIN, "romp-event-model"))
load_source("romp_judge", os.path.join(BIN, "romp-judge"))
km = load_source("romp_kernel_update_check_hermetic", os.path.join(BIN, "romp-kernel"))

import sys  # noqa: E402
sys.path.insert(0, HERE)
import test_ship_reship as lab  # noqa: E402  the lab kernel environment under test


class UpdateCheckSeam(unittest.TestCase):
    def _run_check(self, env_value):
        """_update_check with a checkout that reads as a release (so the tag read is reached) and a tag reader that
        records whether it was asked; returns that record."""
        asked = []

        def reader():
            asked.append(True)
            raise RuntimeError("the release remote is not for a hermetic kernel to read")
        env = dict(os.environ)
        env.pop("ROMP_UPDATE_CHECK", None)
        if env_value is not None:
            env["ROMP_UPDATE_CHECK"] = env_value
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(km, "_kernel_ver", return_value="v0.1.0"), \
             mock.patch.object(km, "_latest_release_tag", reader), \
             mock.patch.object(km, "_update_mode", return_value="ask"):
            km._update_check()
        return asked

    def test_off_stands_the_check_down_before_the_release_remote_is_read(self):
        self.assertEqual(self._run_check("off"), [], "no tag read under ROMP_UPDATE_CHECK=off")

    def test_without_the_seam_the_check_reads_the_release_remote_as_before(self):
        self.assertEqual(self._run_check(None), [True], "the control: the read happens (and its failure is swallowed loudly)")
        self.assertEqual(self._run_check("on"), [True], "only the literal off stands it down")


class LabKernelsRunWithIt(unittest.TestCase):
    def test_every_lab_kernel_environment_carries_the_seam_and_the_relaunch_keeps_it(self):
        d = tempfile.mkdtemp()
        env = lab.kernel_env(d, os.path.join(d, "claude"), os.path.join(d, "dist"), 1, "test-token-DO-NOT-USE")
        self.assertEqual(env.get("ROMP_UPDATE_CHECK"), "off")
        self.assertEqual(lab.relaunch_env(env).get("ROMP_UPDATE_CHECK"), "off", "the driver's relaunch of the lab kernel stays hermetic too")


if __name__ == "__main__":
    unittest.main()
