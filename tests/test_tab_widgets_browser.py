#!/usr/bin/env python3
"""The tab-title WIDGETS and the settings panel in TABS (T379, the user 2026-09-12), on the served dashboard: a hermetic kernel
serves the landing with two synthetic notes-api sessions (web and api, idle, TESTHOST); the chat frame's strip carries the
widgets (the dot slot on every tab, the hot-key keycap on the tab whose hot key the pinned-tabs store names) and the
tab-widgets gear glyph at the strip's right end; the glyph opens the settings frame on its Tabs tab (through the shell's
relay), where each registered widget is a row with a live demo drawn by the strip's own render, a sliding switch and its
options; a switch or an option written there reaches the chat frame's strip live (the storage event) and the store's
tabCtx mirror; the last tab is remembered; the pills hide every other pane.

TAB_WIDGETS_DIST=<dir> serves another tree's UI bundle (the red run's before); TAB_WIDGETS_SHOTS=<prefix> writes
<prefix>-strip-<theme>.png and <prefix>-tabs-<theme>.png; TAB_WIDGETS_DUMP=<path> writes the whole measurement. Skips LOUDLY
without the extension deps or a Playwright browser (CI sets ROMP_SERVED_TESTS_REQUIRE=1 and installs both, so a skip
there is a failure). Synthetic throughout: placeholder sids, TESTHOST, invented text.
"""
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

NAMES = ["web", "api"]
SIDS = {n: "%s-1111-2222-3333-444444444444" % (chr(ord("a") + i) * 8) for i, n in enumerate(NAMES)}
PALETTE = [("#9cd2ff", "#0c1a2e"), ("#1EA1EB", "#ffffff")]


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
const ctx = await browser.newContext({ viewport: { width: 1200, height: 800 } });
// the pinned-tabs store shape (the hot key widget reads it): web is in the set, its chord Ctrl+Shift+1
await ctx.addInitScript(([sid]) => {
  try { localStorage.setItem("romp:tabkeys", JSON.stringify({ [sid]: "web" })); localStorage.setItem("romp:keys", JSON.stringify({ ["session.hotkey." + sid]: "Ctrl+Shift+1" })); } catch (e) {}
}, [cfg.sidWeb]);
const page = await ctx.newPage();
await page.goto(cfg.url);
await page.waitForSelector("#rail-gear", { timeout: 20000 });
const chat = () => page.frames().find((f) => f.url().includes("/chat"));
await page.waitForFunction(() => true);
let chatF = chat();
for (let i = 0; i < 100 && !chatF; i++) { await page.waitForTimeout(100); chatF = chat(); }
if (!chatF) { console.error("no chat frame"); process.exit(1); }
await chatF.waitForSelector("#tabs .tab[data-id]", { timeout: 30000 });
await chatF.waitForFunction((n) => document.querySelectorAll("#tabs .tab[data-id]").length >= n, cfg.count, { timeout: 30000 });
await chatF.waitForTimeout(500);
const readStrip = () => chatF.evaluate(([sidWeb]) => {
  const rect = (e) => { const b = e.getBoundingClientRect(); return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, w: b.width, h: b.height }; };
  const tabs = Array.from(document.querySelectorAll("#tabs .tab[data-id]")).map((t) => ({
    id: t.dataset.id, name: (t.querySelector(".tab-label") || {}).textContent || "",
    children: Array.from(t.children).map((c) => c.className),
    dot: (() => { const d = t.querySelector(".tab-dot"); if (!d) return null; const cs = getComputedStyle(d); return { cls: d.className, visibility: cs.visibility, opacity: cs.opacity, bg: cs.backgroundColor, w: d.getBoundingClientRect().width }; })(),
    key: (() => { const k = t.querySelector(".tab-key"); return k ? { text: k.textContent, title: k.title, w: k.getBoundingClientRect().width } : null; })(),
    ctx: !!t.querySelector(".tab-ctx"),
  }));
  const gear = document.querySelector("#tabs .tab-tagbox .tab-widgets-gear");
  const box = document.querySelector("#tabs .tab-tagbox");
  const s = JSON.parse(localStorage.getItem("romp:settings") || "{}");
  return { tabs, web: tabs.find((t) => t.id === sidWeb), gear: gear ? { title: gear.title, aria: gear.getAttribute("aria-label"), svg: !!gear.querySelector("svg"), rect: rect(gear), inBox: gear.parentElement === box, boxH: box.getBoundingClientRect().height } : null,
           store: { tabWidgets: s.tabWidgets || null, tabCtx: s.tabCtx || null } };
}, [cfg.sidWeb]);
const out = {};
out.strip0 = await readStrip();
// the glyph opens the settings frame on the Tabs tab, through the shell
const settingsOpen = () => page.evaluate(() => document.body.classList.contains("settings-open"));
if (out.strip0.gear) await chatF.click("#tabs .tab-tagbox .tab-widgets-gear");
await page.waitForFunction(() => document.body.classList.contains("settings-open"), null, { timeout: 20000 }).catch(() => {});
out.shellOpen = await settingsOpen();
let setF = page.frames().find((f) => f.url().includes("/settings"));
for (let i = 0; i < 50 && !setF; i++) { await page.waitForTimeout(100); setF = page.frames().find((f) => f.url().includes("/settings")); }
if (!setF) {   // no settings frame opened (the red run's before: no glyph, no ask): every later reading is an honest empty, so each test fails on its own assertion
  const none = { open: false, pills: [], panes: [], rows: [], remembered: null };
  Object.assign(out, { panel0: none, afterCtxOff: { panel: none, strip: out.strip0 }, dotOpt: { present: false, picked: false, labels: [] }, afterGrey: { panel: none, strip: out.strip0 },
                       afterKeyOff: { strip: out.strip0 }, chatPane: none, afterEscape: { shellOpen: false, panel: none }, reopen: none });
  fs.writeFileSync(cfg.out, JSON.stringify(out)); console.log("RESULT: ok"); await browser.close(); process.exit(0);
}
await setF.waitForSelector("#rsettings:not([hidden])", { timeout: 15000 }).catch(() => {});
await setF.waitForTimeout(300);
const readPanel = () => setF.evaluate(() => {
  const p = document.getElementById("rsettings");
  if (!p || p.hidden) return { open: false };
  const pills = Array.from(document.querySelectorAll("#rsettings .rs-tab")).map((b) => ({ tab: b.dataset.tab, text: b.textContent, on: b.classList.contains("on"), selected: b.getAttribute("aria-selected") }));
  const panes = Array.from(document.querySelectorAll("#rsettings .rs-pane")).map((pn) => ({ pane: pn.dataset.pane, hidden: pn.hidden, display: getComputedStyle(pn).display, rows: pn.querySelectorAll(".rs-row, .rs-widget").length }));
  const rows = Array.from(document.querySelectorAll("#rs-widgets .rs-widget")).map((r) => {
    const sw = r.querySelector(".rs-switch"); const cs = getComputedStyle(sw); const knob = getComputedStyle(sw, "::after");
    const demo = r.querySelector(".rs-widget-demo .tab");
    return { id: r.dataset.widget, label: r.querySelector(".rs-widget-name b").textContent, desc: r.querySelector(".rs-widget-name span").textContent,
             sw: { role: sw.getAttribute("role"), checked: sw.getAttribute("aria-checked"), on: sw.classList.contains("on"), w: sw.getBoundingClientRect().width, h: sw.getBoundingClientRect().height, radius: cs.borderRadius, knobLeft: knob.left, bg: cs.backgroundColor },
             demo: demo ? Array.from(demo.children).map((c) => ({ cls: c.className, text: c.textContent, title: c.title || "" })) : null,
             opts: Array.from(r.querySelectorAll(".rs-widget-opt")).map((o) => ({ key: o.dataset.opt, label: o.title, current: (o.querySelector("button") || {}).textContent || "" })) };
  });
  return { open: true, pills, panes, rows, remembered: localStorage.getItem("romp:settingsTab") };
});
out.panel0 = await readPanel();
// the Context bar's switch off: the store's prefs and mirror, the chat's strip on the storage event
const flip = async (id) => { await setF.click('#rs-widgets .rs-widget[data-widget="' + id + '"] .rs-switch'); await setF.waitForTimeout(400); };
await flip("ctx");
out.afterCtxOff = { panel: await readPanel(), strip: await readStrip() };
await flip("ctx");
// the dot's option: a grey dot when idle (the tabs are idle here), through the house picker
out.dotOpt = await setF.evaluate(async () => {
  const wrap = document.querySelector('#rs-widgets .rs-widget[data-widget="dot"] .rs-widget-opt[data-opt="idle"]');
  if (!wrap) return { present: false };
  wrap.querySelector("button").click();
  await new Promise((r) => setTimeout(r, 100));
  const row = Array.from(wrap.querySelectorAll("[data-wopt-dot-idle]")).find((r) => r.getAttribute("data-wopt-dot-idle") === "grey");
  const labels = Array.from(wrap.querySelectorAll("[data-wopt-dot-idle]")).map((r) => r.textContent.replace(/\u2713/g, "").trim());   // the current row carries the house picker's check glyph
  if (row) row.click();
  await new Promise((r) => setTimeout(r, 400));
  return { present: true, labels, picked: !!row };
});
out.afterGrey = { panel: await readPanel(), strip: await readStrip() };
// the hot key widget off: the keycap leaves web's tab
await flip("hotkey");
out.afterKeyOff = { strip: await readStrip() };
await flip("hotkey");
// the pills: Chat hides Tabs; Escape closes; the next open remembers the tab
await setF.click('#rsettings .rs-tab[data-tab="chat"]'); await setF.waitForTimeout(150);
out.chatPane = await readPanel();
await setF.click('#rsettings .rs-tab[data-tab="tabs"]'); await setF.waitForTimeout(150);
// the screenshots: the strip with the glyph and the Tabs tab, dark then light
const shot = async (theme) => {
  await page.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await chatF.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await setF.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await page.waitForTimeout(200);
  if (!cfg.shots) return;
  const card = await setF.evaluate(() => { const b = document.querySelector("#rsettings .rs-card").getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: Math.min(b.height, 520) }; });
  const fr = await page.evaluate(() => { const f = document.getElementById("f-settings").getBoundingClientRect(); return { x: f.left, y: f.top }; });
  await page.screenshot({ path: cfg.shots + "-tabs-" + theme + ".png", clip: { x: fr.x + card.x, y: fr.y + card.y, width: card.width, height: card.height } });
};
await shot("dark"); await shot("light");
await page.evaluate(() => document.body.classList.remove("theme-light")); await setF.evaluate(() => document.body.classList.remove("theme-light")); await chatF.evaluate(() => document.body.classList.remove("theme-light"));
await page.keyboard.press("Escape"); await page.waitForTimeout(300);
out.afterEscape = { shellOpen: await settingsOpen(), panel: await readPanel() };
// the strip shot with the panel closed
for (const theme of ["dark", "light"]) {
  await chatF.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await page.evaluate((t) => document.body.classList.toggle("theme-light", t === "light"), theme);
  await page.waitForTimeout(150);
  if (cfg.shots) {
    const bar = await chatF.evaluate(() => { const b = document.getElementById("tabbar").getBoundingClientRect(); return { x: 0, y: Math.max(0, b.top - 4), width: Math.min(window.innerWidth, 900), height: b.height + 8 }; });
    const fr = await page.evaluate(() => { const f = document.getElementById("f-chat").getBoundingClientRect(); return { x: f.left, y: f.top }; });
    await page.screenshot({ path: cfg.shots + "-strip-" + theme + ".png", clip: { x: fr.x + bar.x, y: fr.y + bar.y, width: bar.width, height: bar.height } });
  }
}
await chatF.evaluate(() => document.body.classList.remove("theme-light")); await page.evaluate(() => document.body.classList.remove("theme-light"));
// reopen from the rail's gear: the remembered tab (Tabs) comes up
await page.click("#rail-gear");
await page.waitForFunction(() => document.body.classList.contains("settings-open"), null, { timeout: 10000 }).catch(() => {});
await setF.waitForTimeout(300);
out.reopen = await readPanel();
fs.writeFileSync(cfg.out, JSON.stringify(out));
await browser.close();
console.log("RESULT: ok");
"""


class ServedTabWidgets(unittest.TestCase):
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
        cls.lab = tempfile.mkdtemp(prefix="tab-widgets-")
        before = os.environ.get("TAB_WIDGETS_DIST", "")
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
        cwd = os.path.join(cls.lab, "notes-api")
        for d in ("names", "sdk", "states"):
            os.makedirs(os.path.join(state, d), exist_ok=True)
        Path(state, "session-hosts").write_text("off\n")   # a lab root writes its own session-hosts off (the conftest rule)
        os.makedirs(cwd, exist_ok=True)
        proj = os.path.join(claude, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd)))
        os.makedirs(proj, exist_ok=True)
        t0 = int(time.time()) - 900
        for i, name in enumerate(NAMES):
            sid = SIDS[name]
            bg, fg = PALETTE[i]
            Path(state, "names", sid).write_text("%s\t%s\t%s\t%s\n" % (name, cwd, bg, fg))
            Path(state, "sdk", sid + ".json").write_text(json.dumps(
                {"sid": sid, "name": name, "cwd": cwd, "mode": "auto", "effort": "high", "lastSid": sid, "alive": True,
                 "model": "claude-opus-5", "liveModel": "Opus 5"}))
            recs = [{"type": "user", "timestamp": iso(t0 + i), "uuid": "u1", "parentUuid": None, "promptSource": "typed", "sessionId": sid,
                     "message": {"role": "user", "content": "what does the %s session do in notes-api?" % name}},
                    {"type": "assistant", "timestamp": iso(t0 + i + 5), "uuid": "a1", "parentUuid": "u1", "sessionId": sid,
                     "message": {"role": "assistant", "model": "claude-opus-5", "stop_reason": "end_turn",
                                 "content": [{"type": "text", "text": "It keeps the %s side of the notes-api tidy." % name}]}}]
            Path(proj, sid + ".jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        Path(state, "usage.json").write_text(json.dumps({"five_hour": {"pct": 10}, "seven_day": {"pct": 10}}))
        cls.port, cls.token = _free_port(), "testtok-tabwidgets"
        env = _lab.kernel_env(cls.lab, claude, dist, cls.port, cls.token, ROMP_HOST_NAME="TESTHOST")
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
            time.sleep(0.5)
        lab = getattr(cls, "lab", "")
        shutil.rmtree(lab, ignore_errors=True)
        time.sleep(0.3)
        shutil.rmtree(lab, ignore_errors=True)

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
            json.dump({"url": "http://127.0.0.1:%d/?token=%s" % (cls.port, cls.token), "count": len(NAMES), "out": out, "sidWeb": SIDS["web"],
                       "shots": os.environ.get("TAB_WIDGETS_SHOTS", "")}, f)
        driver = os.path.join(cls.lab, "driver.mjs")
        with open(driver, "w") as f:
            f.write(DRIVER)
        p = subprocess.run(["node", driver], capture_output=True, text=True, timeout=300,
                           env=dict(os.environ, EXT_PKG=os.path.join(EXT, "package.json"), CFG=cfg))
        if p.returncode == 3:
            raise unittest.SkipTest("no playwright browser on this box — the served guard needs one (CI installs none)")
        if p.returncode != 0:
            raise AssertionError("driver failed:\n" + p.stdout[-3000:] + p.stderr[-3000:] + "\nkernel:\n" + open(cls.klog).read()[-1500:])
        if not os.path.exists(out):
            raise AssertionError("driver printed no result:\n" + p.stdout[-3000:])
        result = json.loads(Path(out).read_text())
        if os.environ.get("TAB_WIDGETS_DUMP"):
            Path(os.environ["TAB_WIDGETS_DUMP"]).write_text(json.dumps(result, indent=1) + "\n")
        return result

    def test_the_strip_carries_the_widgets_and_the_gear_glyph_in_the_tag_box(self):
        s = self._run()["strip0"]
        table = "\n  " + json.dumps(s)[:1200]
        self.assertEqual(len(s["tabs"]), 2, table)
        for t in s["tabs"]:
            self.assertIsNotNone(t["dot"], "every tab carries the dot slot (T262g)" + table)
            self.assertEqual(t["dot"]["visibility"], "hidden", "idle: the slot is laid out and hidden" + table)
            self.assertEqual(t["children"][0], t["dot"]["cls"], "the dot is the tab's first child (the before-the-name slot)" + table)
        web = s["web"]
        self.assertIsNotNone(web["key"], "web's hot key (the pinned-tabs store) renders as a keycap" + table)
        self.assertEqual(web["key"]["text"], "⌃⇧1", table)
        self.assertGreater(web["key"]["w"], 10, table)
        self.assertEqual(web["children"].index("tab-key"), web["children"].index("tab-label") + 1, "the keycap follows the name" + table)
        api = next(t for t in s["tabs"] if t["name"].endswith("api"))
        self.assertIsNone(api["key"], "no hot key assigned: no keycap" + table)
        self.assertIsNotNone(s["gear"], "the glyph is in the strip (the chat sits in the shell, so a gear can be reached)" + table)
        self.assertEqual((s["gear"]["title"], s["gear"]["aria"], s["gear"]["svg"], s["gear"]["inBox"]), ("Tab widgets…", "Tab widgets", True, True), table)
        self.assertLessEqual(s["gear"]["rect"]["h"], s["gear"]["boxH"] + 0.5, "it takes no extra height beyond the tag box" + table)

    def test_the_glyph_opens_the_settings_on_the_tabs_tab_with_the_other_panes_hidden(self):
        r = self._run()
        self.assertTrue(r["shellOpen"], "the shell lifted the settings frame")
        p = r["panel0"]
        table = "\n  " + json.dumps(p)[:1500]
        self.assertTrue(p["open"], table)
        self.assertEqual([x["tab"] for x in p["pills"]], ["chat", "tabs", "feed", "sessions", "automatic", "appearance", "system"], table)
        self.assertEqual([x["text"] for x in p["pills"]], ["Chat", "Tabs", "Feed", "Sessions", "Automatic", "Appearance", "System"], table)
        self.assertEqual([x["on"] for x in p["pills"]], [False, True, False, False, False, False, False], "the Tabs pill is on" + table)
        self.assertEqual([x["selected"] for x in p["pills"]], ["false", "true", "false", "false", "false", "false", "false"], table)
        shown = [x for x in p["panes"] if x["display"] != "none"]
        self.assertEqual([x["pane"] for x in shown], ["tabs"], "one pane painted" + table)
        self.assertTrue(all(x["rows"] > 0 for x in p["panes"]), "every pane holds rows" + table)
        self.assertEqual(p["remembered"], "tabs", table)

    def test_each_widget_row_shows_a_live_demo_drawn_by_the_strips_render_a_sliding_switch_and_its_options(self):
        p = self._run()["panel0"]
        self.assertTrue(p["open"], "the panel opened: " + json.dumps(p)[:300])
        rows = p["rows"]
        table = "\n  " + json.dumps(rows)[:2000]
        self.assertEqual([r["id"] for r in rows], ["dot", "ctx", "hotkey"], "registration order: the dot, the bar, the hot key" + table)
        self.assertEqual([r["label"] for r in rows], ["Status dot", "Context bar", "Hot key"], table)
        for r in rows:
            self.assertEqual((r["sw"]["role"], r["sw"]["checked"], r["sw"]["on"]), ("switch", "true", True), r["id"] + " is on by default" + table)
            self.assertEqual(r["sw"]["radius"], "999px", "the sliding toggle, a pill" + table)
            self.assertGreater(r["sw"]["w"], r["sw"]["h"], table)
            self.assertEqual(r["sw"]["knobLeft"], "18px", "on: the knob sits right" + table)
            self.assertTrue(r["desc"], "a one-line description" + table)
        dot, ctx, key = rows
        self.assertEqual([c["cls"] for c in dot["demo"]], ["tab-dot", "tab-label"], "the demo: a working session's gold dot before the name" + table)
        self.assertEqual(dot["demo"][0]["title"], "working — a turn is running right now", table)
        self.assertEqual([c["cls"] for c in ctx["demo"]], ["tab-label", "tab-ctx"], "the bar after the name" + table)
        self.assertEqual([c["cls"] for c in key["demo"]], ["tab-label", "tab-key"], table)
        self.assertEqual(key["demo"][1]["text"], "⌃⇧1", "the demo keycap" + table)
        self.assertEqual([[o["key"] for o in r["opts"]] for r in rows], [["idle"], ["show"], []], "the dot's idle option, the bar's show option, the hot key none" + table)
        self.assertEqual(dot["opts"][0]["current"].replace("▾", "").strip(), "Hide when idle", table)
        self.assertEqual(ctx["opts"][0]["current"].replace("▾", "").strip(), "From 50% full", table)

    def test_a_switch_writes_the_prefs_and_the_mirror_and_the_strip_follows_live(self):
        r = self._run()
        a = r["afterCtxOff"]
        self.assertTrue(a["panel"]["open"], "the panel opened: " + json.dumps(a["panel"])[:300])
        table = "\n  " + json.dumps(a["strip"]["store"]) + " " + json.dumps([x["sw"]["checked"] for x in a["panel"]["rows"]])
        self.assertEqual([x["sw"]["checked"] for x in a["panel"]["rows"]], ["true", "false", "true"], "the Context bar's switch is off" + table)
        self.assertEqual(a["strip"]["store"]["tabWidgets"]["on"], {"ctx": False}, "the store's prefs" + table)
        self.assertEqual(a["strip"]["store"]["tabCtx"], "never", "…and the older key mirrors it, for older readers" + table)
        k = r["afterKeyOff"]["strip"]
        self.assertIsNone(k["web"]["key"], "the hot key widget off: the keycap left web's tab, live, through the storage event: " + json.dumps(k["web"]))
        self.assertEqual(k["store"]["tabWidgets"]["on"], {"ctx": True, "hotkey": False}, "the bar's flag was written back on, the hot key's off: " + json.dumps(k["store"]))
        g = r["afterGrey"]
        self.assertTrue(r["dotOpt"]["present"] and r["dotOpt"]["picked"], json.dumps(r["dotOpt"]))
        self.assertEqual(r["dotOpt"]["labels"], ["Hide when idle", "Grey dot when idle"], "the option's two choices as a house picker")
        self.assertEqual(g["strip"]["store"]["tabWidgets"]["opts"], {"dot": {"idle": "grey"}}, json.dumps(g["strip"]["store"]))
        for t in g["strip"]["tabs"]:
            self.assertEqual(t["dot"]["cls"], "tab-dot idle", "the idle tabs wear the quiet grey dot now: " + json.dumps(t["dot"]))
            self.assertEqual(t["dot"]["visibility"], "visible", json.dumps(t["dot"]))
            self.assertLess(float(t["dot"]["opacity"]), 0.6, "quiet" + json.dumps(t["dot"]))
        self.assertEqual(g["panel"]["rows"][0]["demo"][0]["cls"], "tab-dot", "the demo is a working session: its dot stays gold whatever the idle option")
        self.assertEqual(g["panel"]["rows"][0]["opts"][0]["current"].replace("▾", "").strip(), "Grey dot when idle")

    def test_the_pills_switch_panes_escape_closes_and_the_next_open_remembers_the_tab(self):
        r = self._run()
        c = r["chatPane"]
        self.assertTrue(c["open"], "the panel opened: " + json.dumps(c)[:300])
        shown = [x["pane"] for x in c["panes"] if x["display"] != "none"]
        self.assertEqual(shown, ["chat"], json.dumps(c["panes"]))
        self.assertEqual(c["remembered"], "chat")
        self.assertFalse(r["afterEscape"]["shellOpen"], "Escape closed the settings (the shell's chain)")
        self.assertFalse(r["afterEscape"]["panel"]["open"])
        ro = r["reopen"]
        self.assertTrue(ro["open"], "the rail's gear reopened it")
        self.assertEqual([x["pane"] for x in ro["panes"] if x["display"] != "none"], ["tabs"], "…on the remembered tab (Tabs was picked last)")


if __name__ == "__main__":
    unittest.main()
