#!/usr/bin/env python3
"""The tab menu's Billing flyout opens on HOVER over its row, as the Tags flyout does (one gesture, wireFlyout), and
carries "Default for this machine" below the session's choices (T380; the user 2026-09-12): the same choices as a radio
group, the current default marked, a pick writing the seed every new session and every session with no pick of its own
launches on, touching no session that carries its own pick.

This lab drives the real /chat page of a hermetic kernel whose machine offers BOTH sides (a staged apiKeyHelper in the
kernel's Claude config dir, a synthetic Claude account in the kernel's own home), with two synthetic sessions: web with
no pick of its own, api with an explicit key pick. It right-clicks web's tab, HOVERS the Billing row without clicking
and reads whether the flyout opened and when; reads the flyout (the choices, the Default group's head and radios, the
marked default); leaves the row and the flyout and reads that the flyout closed with the menu still up; opens again and
presses Escape; then opens once more and clicks the Login default radio, after which the kernel's sdk-defaults.json
must read auth login with authExplicit true while api's reg keeps its key pick and web's reg has no pick.
BILLING_FLYOUT_DIST=<dir> serves another tree's UI bundle (the red run's before; the driver falls back to a click when
the hover opens nothing, so the rest is still read); BILLING_FLYOUT_SHOTS=<prefix> writes <prefix>-dark.png and
<prefix>-light.png of the open flyout. Skips LOUDLY without the extension deps or a Playwright browser, and never
otherwise (CI turns a skip in a served module into a failure). SYNTHETIC fixtures only."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tests.dist_copy import copy_dist

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
EXT = os.path.join(ROOT, "vscode-extension")
sys.path.insert(0, HERE)
import test_ship_reship as _lab   # noqa: E402  the lab kernel's environment: a list of names, never a copy of the runner's

# the notes-api demo world: twenty sessions, enough to wrap the strip onto several rows at a narrow width
NAMES = ["web", "api"]
SIDS = {n: "%s-1111-2222-3333-444444444444" % (chr(ord("a") + i) * 8) for i, n in enumerate(NAMES)}
PALETTE = [("#9cd2ff", "#0c1a2e"), ("#1EA1EB", "#ffffff"), ("#54B204", "#ffffff"), ("#c98cff", "#1a0c2e"),
           ("#e5a50a", "#1a1200"), ("#4EC9B0", "#00201a")]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


DRIVER = r"""
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.EXT_PKG);
const { chromium } = require("playwright");
const cfg = JSON.parse(fs.readFileSync(process.env.CFG, "utf8"));
let browser;
try { browser = await chromium.launch(); }
catch (e) { console.error("browser-launch-failed: " + e); process.exit(3); }
const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
await page.goto(cfg.chat);
await page.waitForSelector("#tabs .tab[data-id]", { timeout: 30000 });
await page.waitForFunction((n) => document.querySelectorAll("#tabs .tab[data-id]").length >= n, cfg.count, { timeout: 30000 });
await page.waitForTimeout(600);
const menuOpen = async () => {
  const tab = await page.$('#tabs .tab[data-id="' + cfg.sidWeb + '"]');
  await tab.click({ button: "right" });
  await page.waitForSelector(".ctx-menu .ctx-item-billing", { timeout: 5000 });
};
const billingRow = () => page.$(".ctx-menu .ctx-item-billing");
const readFly = () => page.evaluate(() => {
  const fly = document.querySelector(".ctx-sub-billing");
  if (!fly) return null;
  const items = Array.from(fly.querySelectorAll(".ctx-item"));
  const choices = items.filter((i) => !i.classList.contains("ctx-radio") && !i.classList.contains("ctx-sub-head")).map((i) => ({ text: i.textContent.trim(), current: i.classList.contains("current"), disabled: i.classList.contains("disabled") }));
  const head = fly.querySelector(".ctx-sub-head");
  const radios = Array.from(fly.querySelectorAll(".ctx-radio")).map((i) => ({ text: i.textContent.trim(), current: i.classList.contains("current"), disabled: i.classList.contains("disabled"), scope: i.dataset.scope }));
  const r = fly.getBoundingClientRect();
  const row = document.querySelector(".ctx-menu .ctx-item-billing .ctx-item-sub");
  return { choices, head: head ? head.querySelector(".ctx-item-label").textContent : null, note: head ? head.querySelector(".ctx-item-sub").textContent : null, radios, sep: !!fly.querySelector(".ctx-sep"), rect: { left: r.left, top: r.top, w: r.width, h: r.height }, subLine: row ? row.textContent : null };
});
const out = {};
out.tabs = await page.evaluate(() => Array.from(document.querySelectorAll("#tabs .tab[data-id]")).map((t) => ({ id: t.dataset.id, name: (t.querySelector(".tab-label") || t).textContent.trim(), active: t.classList.contains("active") })));
try {
await menuOpen();
let row = await billingRow(); let bb = await row.boundingBox();
const t0 = Date.now();
await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
let byHover = true;
try { await page.waitForSelector(".ctx-sub-billing", { timeout: 1500 }); } catch (e) { byHover = false; }
out.hover = { opened: byHover, ms: Date.now() - t0 };
if (!byHover) { await row.click(); await page.waitForSelector(".ctx-sub-billing", { timeout: 5000 }).catch(() => {}); }
out.fly = await readFly();
// leave both the row and the flyout: the flyout closes after the tolerance window, the menu stays
await page.mouse.move(5, 690);
await page.waitForTimeout(450);
out.afterLeave = await page.evaluate(() => ({ fly: !!document.querySelector(".ctx-sub-billing"), menu: !!document.querySelector(".ctx-menu") }));
// hover again, then Escape closes the menu (and the flyout with it)
row = await billingRow(); if (row) { bb = await row.boundingBox(); await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await page.waitForSelector(".ctx-sub-billing", { timeout: 1500 }).catch(() => {}); }
await page.keyboard.press("Escape"); await page.waitForTimeout(150);
out.afterEscape = await page.evaluate(() => ({ fly: !!document.querySelector(".ctx-sub-billing"), menu: !!document.querySelector(".ctx-menu") }));
// the screenshots: the open flyout, dark and light
for (const theme of ["dark", "light"]) {
  await page.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await page.mouse.move(5, 690); await page.waitForTimeout(100);
  await menuOpen(); row = await billingRow(); bb = await row.boundingBox();
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.waitForSelector(".ctx-sub-billing", { timeout: 1500 }).catch(async () => { await row.click(); });
  await page.waitForTimeout(150);
  if (cfg.shots) await page.screenshot({ path: cfg.shots + "-" + theme + ".png", clip: { x: 0, y: 0, width: 1100, height: 520 } });
  await page.keyboard.press("Escape"); await page.waitForTimeout(100);
}
await page.evaluate(() => document.body.classList.remove("theme-light"));
// the default pick: the Login radio (the seed reads key: the helper is the box's default), posting setAuth with scope machine
await menuOpen(); row = await billingRow(); bb = await row.boundingBox();
await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
await page.waitForSelector(".ctx-sub-billing", { timeout: 1500 }).catch(async () => { await row.click(); });
out.pick = await page.evaluate(() => {
  const r = Array.from(document.querySelectorAll(".ctx-sub-billing .ctx-radio")).find((i) => i.textContent.trim().startsWith("Login"));
  if (!r) return { found: false };
  const disabled = r.classList.contains("disabled");
  if (!disabled) r.click();
  return { found: true, disabled, menuGone: !document.querySelector(".ctx-menu") };
});
await page.waitForTimeout(1200);   // the op reaches the kernel over the socket and the seed is written
await page.waitForFunction(() => { const s = document.querySelector('#tabs .tab.active'); return !!s; }, null, { timeout: 5000 });
await page.waitForTimeout(800);     // the next push carries web's new effective side
await menuOpen(); row = await billingRow(); bb = await row.boundingBox();
await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
await page.waitForSelector(".ctx-sub-billing", { timeout: 1500 }).catch(async () => { await row.click(); });
await page.waitForTimeout(150);
out.afterPick = await readFly();
await page.keyboard.press("Escape");
} catch (e) { out.error = String(e && e.stack || e); }
fs.writeFileSync(cfg.out, JSON.stringify(out));
await browser.close();
console.log("RESULT: ok");
"""


class ServedTabTipTones(unittest.TestCase):
    maxDiff = None
    result = None

    @classmethod
    def setUpClass(cls):
        try:
            cls._boot()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def _boot(cls):
        if not os.path.isdir(os.path.join(EXT, "node_modules", "playwright")):
            raise unittest.SkipTest("extension deps absent (npm ci not run here) — the served guard needs them")
        probe = subprocess.run(["node", "-e", "const p=require(process.argv[1]);process.stdout.write(p.chromium.executablePath())",
                                os.path.join(EXT, "node_modules", "playwright")], capture_output=True, text=True)
        if probe.returncode != 0 or not os.path.exists(probe.stdout.strip()):
            raise unittest.SkipTest("no playwright browser on this box — the served guard needs one (CI installs none)")
        cls.lab = tempfile.mkdtemp(prefix="billing-fly-")
        before = os.environ.get("BILLING_FLYOUT_DIST", "")
        if before:
            src = before
        else:
            b = subprocess.run(["node", "esbuild.js"], cwd=EXT, capture_output=True, text=True)
            if b.returncode != 0:
                raise unittest.SkipTest("esbuild failed here: " + (b.stderr or b.stdout)[-200:])
            src = os.path.join(EXT, "dist")
        dist = os.path.join(cls.lab, "dist")
        copy_dist(src, dist)
        state = os.path.join(cls.lab, "xdg", "romp")
        claude = os.path.join(cls.lab, "claude")
        cwd = os.path.join(cls.lab, "proj")
        for d in ("names", "sdk", "states"):
            os.makedirs(os.path.join(state, d), exist_ok=True)
        # a lab root writes its own session-hosts off (the conftest rule): hosts are on by default, and a kernel-side boot
        # attach for twenty alive sessions would otherwise spawn twenty real session hosts on a developer's machine
        Path(state, "session-hosts").write_text("off\n")
        os.makedirs(cwd, exist_ok=True)
        proj = os.path.join(claude, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd)))
        os.makedirs(proj, exist_ok=True)
        t0 = int(time.time()) - 900
        for i, name in enumerate(NAMES):
            sid = SIDS[name]
            bg, fg = PALETTE[i % len(PALETTE)]
            Path(state, "names", sid).write_text("%s\t%s\t%s\t%s\n" % (name, cwd, bg, fg))
            reg = {"sid": sid, "name": name, "cwd": cwd, "mode": "auto", "effort": "high", "lastSid": sid, "alive": True,
                   "model": "claude-opus-5", "liveModel": "Opus 5"}
            if name == "api":
                reg["auth"] = "key"          # api carries its OWN pick; web follows the machine default
            Path(state, "sdk", sid + ".json").write_text(json.dumps(reg))
            recs = [{"type": "user", "timestamp": iso(t0 + i), "uuid": "u1", "parentUuid": None, "promptSource": "typed", "sessionId": sid,
                     "message": {"role": "user", "content": "what does the %s session do in notes-api?" % name}},
                    {"type": "assistant", "timestamp": iso(t0 + i + 5), "uuid": "a1", "parentUuid": "u1", "sessionId": sid,
                     "message": {"role": "assistant", "model": "claude-opus-5", "stop_reason": "end_turn",
                                 "content": [{"type": "text", "text": "It keeps the %s side of the notes-api tidy." % name}]}}]
            Path(proj, sid + ".jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        # BOTH sides on this machine: a staged apiKeyHelper (read, never run) in the kernel's Claude config dir, and a
        # synthetic Claude account in the kernel's OWN home (the kernel probes the login side from ~/.claude.json)
        helper = Path(claude, "helper.sh"); helper.write_text("#!/bin/sh\necho not-a-real-key\n"); helper.chmod(0o700)
        Path(claude, "settings.json").write_text(json.dumps({"apiKeyHelper": str(helper)}))
        home = os.path.join(cls.lab, "home"); os.makedirs(home, exist_ok=True)
        Path(home, ".claude.json").write_text(json.dumps({"oauthAccount": {"accountUuid": "11111111-2222-3333-4444-555555555555",
                                                                             "emailAddress": "user@example.com", "organizationName": "Example"}}))
        cls.home = home
        Path(state, "usage.json").write_text(json.dumps({"five_hour": {"pct": 10}, "seven_day": {"pct": 10}}))
        cls.port, cls.token = _free_port(), "testtok-billing"
        env = _lab.kernel_env(cls.lab, claude, dist, cls.port, cls.token, ROMP_HOST_NAME="TESTHOST", HOME=cls.home)
        cls.state = state
        cls.klog = os.path.join(cls.lab, "kernel.log")
        cls.kernel = subprocess.Popen([os.path.join(BIN, "romp-kernel")], stdout=open(cls.klog, "w"), stderr=subprocess.STDOUT, env=env)
        for _ in range(120):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/healthz" % cls.port, timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise unittest.SkipTest("hermetic kernel never served /healthz here")

    @classmethod
    def tearDownClass(cls):
        k = getattr(cls, "kernel", None)
        if k:
            k.terminate()
            try:
                k.wait(timeout=10)
            except subprocess.TimeoutExpired:
                k.kill(); k.wait()
            time.sleep(0.5)                # a kernel child still writing into the lab's config dir finishes (review: stray dirs)
        lab = getattr(cls, "lab", "")
        shutil.rmtree(lab, ignore_errors=True)
        time.sleep(0.3)
        shutil.rmtree(lab, ignore_errors=True)   # …and whatever landed between the two

    @classmethod
    def _run(cls):
        if cls.result is not None:
            if isinstance(cls.result, BaseException):
                raise cls.result
            return cls.result
        try:
            cls.result = cls._drive()
        except BaseException as e:
            cls.result = e
            raise
        return cls.result

    @classmethod
    def _drive(cls):
        cfg = os.path.join(cls.lab, "cfg.json")
        out = os.path.join(cls.lab, "result.json")
        with open(cfg, "w") as f:
            json.dump({"chat": "http://127.0.0.1:%d/chat?token=%s" % (cls.port, cls.token), "count": len(NAMES), "out": out, "sidWeb": SIDS["web"],
                       "shots": os.environ.get("BILLING_FLYOUT_SHOTS", "")}, f)
        driver = os.path.join(cls.lab, "driver.mjs")
        with open(driver, "w") as f:
            f.write(DRIVER)
        p = subprocess.run(["node", driver], capture_output=True, text=True, timeout=240,
                           env=dict(os.environ, EXT_PKG=os.path.join(EXT, "package.json"), CFG=cfg))
        if p.returncode == 3:
            raise unittest.SkipTest("no playwright browser on this box — the served guard needs one (CI installs none)")
        if p.returncode != 0:
            raise AssertionError("driver failed:\n" + p.stdout[-3000:] + p.stderr[-3000:] + "\nkernel:\n" + open(cls.klog).read()[-1500:])
        if not os.path.exists(out):
            raise AssertionError("driver printed no result:\n" + p.stdout[-3000:])
        result = json.loads(Path(out).read_text())
        if os.environ.get("BILLING_FLYOUT_DUMP"):
            Path(os.environ["BILLING_FLYOUT_DUMP"]).write_text(json.dumps(result, indent=1) + "\n")
        if result.get("error"):
            raise AssertionError("the driver threw: " + result["error"] + "\n  tabs: " + json.dumps(result.get("tabs")) + "\nkernel:\n" + open(cls.klog).read()[-1200:])
        return result

    def test_hovering_the_billing_row_opens_the_flyout_without_a_click(self):
        r = self._run()
        self.assertTrue(r["hover"]["opened"], "the flyout opened on hover, no click (the Tags flyout's gesture, T380): " + json.dumps(r["hover"]))
        self.assertLess(r["hover"]["ms"], 1200, "within the intent window: " + json.dumps(r["hover"]))

    def test_leaving_closes_the_flyout_and_keeps_the_menu_and_escape_closes_both(self):
        r = self._run()
        self.assertEqual(r["afterLeave"], {"fly": False, "menu": True}, "leaving the row and the flyout closes the flyout, the menu stays: " + json.dumps(r["afterLeave"]))
        self.assertEqual(r["afterEscape"], {"fly": False, "menu": False}, "Escape closes the menu and the flyout with it: " + json.dumps(r["afterEscape"]))

    def test_the_default_group_lists_the_same_choices_with_the_machine_default_marked(self):
        r = self._run()
        f = r["fly"]
        self.assertIsNotNone(f, "the flyout was read")
        table = "\n  " + json.dumps(f)
        self.assertEqual([c["text"].split(" (")[0] for c in f["choices"]], ["Login", "API key"], table)
        self.assertTrue(f["sep"], "a divider before the group" + table)
        self.assertEqual(f["head"], "Default for this machine", table)
        self.assertIn("sessions with no pick of their own", f["note"] or "", "the note says which sessions it affects (the automatic rule before any explicit default)" + table)
        self.assertEqual([x["text"].split(" (")[0] for x in f["radios"]], ["Login", "API key", "Automatic"], "the same choices as radios, then Automatic (the helper rule)" + table)
        self.assertTrue(all(x["scope"] == "machine" for x in f["radios"]), table)
        self.assertEqual([x["current"] for x in f["radios"]], [False, False, True], "no explicit default yet: Automatic is marked" + table)
        self.assertIn("automatic:", f["note"], "the sub-line says the helper rule holds" + table)
        self.assertEqual(f["radios"][2]["text"], "Automatic (API key here)", "and what it resolves to on this machine" + table)
        self.assertFalse(any(x["disabled"] for x in f["radios"]), "both sides are available on this machine" + table)
        self.assertEqual(f["subLine"], "API key", "web follows the automatic default: the key (the helper)" + table)

    def test_a_default_pick_writes_the_seed_and_touches_no_session(self):
        r = self._run()
        self.assertTrue(r["pick"]["found"] and not r["pick"]["disabled"], json.dumps(r["pick"]))
        self.assertTrue(r["pick"]["menuGone"], "the pick dismisses the menu")
        d = json.loads(Path(self.state, "sdk-defaults.json").read_text())
        self.assertEqual((d.get("auth"), d.get("authExplicit")), ("login", True), "the machine default, explicit: " + json.dumps(d))
        api = json.loads(Path(self.state, "sdk", SIDS["api"] + ".json").read_text())
        self.assertEqual(api.get("auth"), "key", "a session with its own pick is untouched")
        web = json.loads(Path(self.state, "sdk", SIDS["web"] + ".json").read_text())
        self.assertNotIn("auth", web, "a session that follows the default carries no pick of its own; it takes the new side at its next launch")
        # the review's shape: an unpicked session FOLLOWS the default at once, in its status and the flyout's marks
        a = r["afterPick"]
        self.assertIsNotNone(a, "the flyout was read again after the pick")
        table = "\n  " + json.dumps(a)
        # the review's medium first: an unpicked session FOLLOWS the default at once (its status, the flyout's marks)
        self.assertTrue((a["subLine"] or "").startswith("Login"), "web (no pick of its own) now reads the login, at once" + table)
        self.assertEqual([c["current"] for c in a["choices"]], [True, False], "…and its own choice marks the login it follows" + table)
        self.assertEqual([x["current"] for x in a["radios"]], [True, False, False], "the Login default is marked, Automatic no longer" + table)
        self.assertIn("set here:", a["note"], "the sub-line says the default is explicit" + table)
        self.assertIn("own pick keeps it", a["note"], table)


if __name__ == "__main__":
    unittest.main()
