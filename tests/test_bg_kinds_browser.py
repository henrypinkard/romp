#!/usr/bin/env python3
"""T394 (the user 2026-09-12, from a screenshot of the chat's background fold): every row of the box sits in its KIND's section
(Agents, Commands, Watches) with one hue per kind for its dot and caption word, and a tracked task nobody waits on (the judge
audited its launch without a wait) lists in its kind's section, dimmed, with the verdict as a muted suffix, instead of under a
section of its own whose title said nothing of why.

The served lab drives the real /chat page over a hermetic kernel (the rescind lab's boot: a synthetic idle session) and sends the
page one session frame by the shim's own door (window.postMessage, the T357 route): the session working, the kernel's rows (an
agent, a command, a watch) and the tracked tasks (those two plus a service the rows do not name). It opens the box and reads every
row as the browser computes it, in the dark theme and then the cream one:

  1. the sections and the rows in them, the header's words, the suffix on the kept row, the Stop, Cancel, arrow and caret;
  2. the dot and caption colours against the theme's tokens, and each caption's contrast on the box it sits on.

Skips LOUDLY without the extension deps or a Playwright browser (CI installs none). All fixtures synthetic.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_queued_rescind_browser import BIN, EXT, SID, _free_port, _lab, copy_dist, iso   # noqa: E402  the shared boot's pieces (never its TestCase)

AGENT_ID, CMD_ID, WATCH_ID, SVC_ID = "tu_agent_1", "tu_cmd_1", "watch-1", "tu_svc_1"
KEPT_WORD = "· kept running, not waited on"

DRIVER = r"""
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.EXT_PKG);
const { chromium } = require("playwright");
const cfg = JSON.parse(fs.readFileSync(process.env.CFG, "utf8"));
let browser;
try { browser = await chromium.launch(); }
catch (e) { console.error("browser-launch-failed: " + e); process.exit(3); }
const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
await page.goto(cfg.chat);
await page.waitForSelector("#tabs .tab, #tabs [data-sid]", { timeout: 20000 });
await page.waitForSelector("#composer-input", { timeout: 20000 });
await page.waitForTimeout(500);
// the frame: the session working, the kernel's rows and the tracked tasks; the shim hands it to the page like a kernel push
await page.evaluate((f) => window.postMessage(f, "*"), cfg.frame);
await page.waitForSelector("#bg-tasks .bg-fold-head", { timeout: 15000 });
await page.click("#bg-tasks .bg-fold-head");   // collapsed by default: open the list
await page.waitForFunction(() => document.querySelectorAll("#bg-tasks .bg-list .bg-task").length >= 4, null, { timeout: 15000 });
await page.waitForTimeout(200);
const probe = () => page.evaluate(() => {
  const tok = (v) => { const d = document.createElement("div"); d.style.background = v; document.body.appendChild(d); const c = getComputedStyle(d).backgroundColor; d.remove(); return c; };
  // an oklch() relative colour comes back as oklch(...) from getComputedStyle; a 1x1 canvas resolves it to rgb
  const asRGB = (css) => { if (!/^(oklch|oklab|color)\(/.test(css) || /\//.test(css)) return css;
    const cv = document.createElement("canvas"); cv.width = cv.height = 1; const ctx = cv.getContext("2d");
    ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1); const d = ctx.getImageData(0, 0, 1, 1).data;
    return "rgb(" + d[0] + ", " + d[1] + ", " + d[2] + ")"; };
  const tokens = { working: tok("var(--st-working-bg)"), await: tok("var(--st-awaitbg-bg)"), command: tok("var(--kind-command)"), dim: tok("var(--dim)"),
                   page: tok("var(--bg)"), box: tok("var(--box-bg)") };
  const rows = []; let section = null;
  for (const el of document.querySelectorAll("#bg-tasks .bg-list > *")) {
    if (el.classList.contains("bg-group-head")) { section = (el.textContent || "").trim(); continue; }
    if (!el.classList.contains("bg-task")) continue;
    const dot = el.querySelector(".bg-dot"), sum = el.querySelector(".bg-sum"), cap = el.querySelector(".bg-status"), kw = el.querySelector(".bg-kept-word");
    rows.push({ section, label: (sum.textContent || "").trim(), cls: el.className,
                dot: getComputedStyle(dot).backgroundColor, dotOpacity: getComputedStyle(dot).opacity,
                caption: cap ? (cap.textContent || "").trim() : null, captionColor: cap ? asRGB(getComputedStyle(cap).color) : null,
                kept: kw ? (kw.textContent || "").trim() : null, keptColor: kw ? getComputedStyle(kw).color : null, labelColor: getComputedStyle(sum).color,
                stop: !!el.querySelector(".bg-stop:not(.bg-cancel)"), cancel: !!el.querySelector(".bg-cancel"),
                arrow: !!el.querySelector(".bg-open-agent"), caret: !!el.querySelector(".bg-head .bg-caret") });
  }
  const head = document.querySelector("#bg-tasks .bg-fold-label");
  return { header: head ? (head.textContent || "").trim() : null, sections: Array.from(document.querySelectorAll("#bg-tasks .bg-group-head")).map((e) => (e.textContent || "").trim()),
           rows, tokens, theme: document.body.classList.contains("theme-light") ? "light" : "dark" };
});
const dark = await probe();
await page.evaluate(() => document.body.classList.add("theme-light"));
await page.waitForTimeout(250);
const light = await probe();
if (cfg.shots) { fs.mkdirSync(cfg.shots, { recursive: true }); await page.screenshot({ path: cfg.shots + "/romp_chat-T394-bg-kinds-light-served.png" }); }
await browser.close();
process.stdout.write("RESULT:" + JSON.stringify({ dark, light }) + "\n", () => process.exit(0));
"""


def _nums(css):
    m = re.search(r"color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)(?: / ([\d.]+))?\)", css or "")
    if m:
        return [255 * float(m.group(1)), 255 * float(m.group(2)), 255 * float(m.group(3)), 1.0 if m.group(4) is None else float(m.group(4))]
    n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", css or "")]
    return [n[0], n[1], n[2], n[3] if len(n) > 3 else 1.0]


def composite(wash, page):
    w, p = _nums(wash), _nums(page)
    a = w[3]
    return "rgb(%d, %d, %d)" % tuple(round(w[i] * a + p[i] * (1 - a)) for i in range(3))


def contrast(a, b):
    def lum(css):
        ch = [v / 255 for v in _nums(css)[:3]]
        ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class ServedBgKinds(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(os.path.join(EXT, "node_modules", "playwright")):
            raise unittest.SkipTest("extension deps absent (npm ci not run here) — the served guard needs them")
        cls.lab = tempfile.mkdtemp(prefix="bg-kinds-")
        b = subprocess.run(["node", "esbuild.js"], cwd=EXT, capture_output=True, text=True)
        if b.returncode != 0:
            raise unittest.SkipTest("esbuild failed here: " + (b.stderr or b.stdout)[-200:])
        dist = os.path.join(cls.lab, "dist")
        copy_dist(os.path.join(EXT, "dist"), dist)
        state = os.path.join(cls.lab, "xdg", "romp")
        cwd = os.path.join(cls.lab, "proj")
        for d in ("names", "sdk", "states"):
            os.makedirs(os.path.join(state, d), exist_ok=True)
        Path(state, "session-hosts").write_text("off")     # a state root of our own: no real host for the session (the Testing rule)
        os.makedirs(cwd, exist_ok=True)
        Path(state, "names", SID).write_text("web\t%s\t\t\n" % cwd)
        Path(state, "sdk", SID + ".json").write_text(json.dumps(
            {"sid": SID, "name": "web", "cwd": cwd, "mode": "auto", "effort": "high",
             "lastSid": SID, "alive": True, "model": "claude-fable-5-1", "liveModel": "Fable 5.1"}))
        Path(state, "usage.json").write_text(json.dumps({"five_hour": {"pct": 10}, "seven_day": {"pct": 10}}))
        claude = os.path.join(cls.lab, "claude")
        proj = os.path.join(claude, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd)))   # jd._proj_dir's munge
        os.makedirs(proj, exist_ok=True)
        t0 = int(time.time()) - 900
        recs = [   # an idle session: one exchange, the turn closed
            {"type": "user", "timestamp": iso(t0), "uuid": "u1", "parentUuid": None, "promptSource": "sdk", "sessionId": SID,
             "message": {"role": "user", "content": "map the notes-api parser"}},
            {"type": "assistant", "timestamp": iso(t0 + 10), "uuid": "a1", "parentUuid": "u1", "sessionId": SID,
             "message": {"role": "assistant", "model": "claude-fable-5-1", "stop_reason": "end_turn",
                         "content": [{"type": "text", "text": "Starting on the parser map."}]}},
        ]
        Path(proj, SID + ".jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        cls.port = _free_port()
        cls.token = "testtok-bgkinds"
        env = _lab.kernel_env(cls.lab, claude, dist, cls.port, cls.token)
        cls.klog = os.path.join(cls.lab, "kernel.log")
        cls.kernel = subprocess.Popen([os.path.join(BIN, "romp-kernel")], stdout=open(cls.klog, "w"), stderr=subprocess.STDOUT, env=env)
        import urllib.request
        for _ in range(120):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/healthz" % cls.port, timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            cls.kernel.kill()
            raise unittest.SkipTest("hermetic kernel never served /healthz here")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "kernel", None):
            cls.kernel.kill()
            cls.kernel.wait()

    _r = None

    def _result(self):
        cls = type(self)
        if cls._r is None:
            now = int(time.time())
            frame = {"type": "session", "id": SID, "name": "web", "color": {"bg": "#9cd2ff", "fg": "#0c1a2e"},
                     "status": {"state": "working", "sinceEpoch": now - 300, "awaitingTaskIds": [],
                                "awaitingItems": [
                                    {"kind": "agents", "id": AGENT_ID, "agentId": "agent-1", "label": "Map the notes-api parser", "since": now - 240},
                                    {"kind": "commands", "id": CMD_ID, "label": "Build the docs site", "since": now - 540},
                                    {"kind": "watches", "id": WATCH_ID, "watchId": WATCH_ID, "label": "the CI run on web", "detail": "gh run watch 1", "since": now - 1860}]},
                     "bgTasks": {"count": 3, "tasks": [
                         {"id": AGENT_ID, "status": "running", "summary": "Map the notes-api parser", "agentId": "agent-1", "command": "Map the parser module by module"},
                         {"id": CMD_ID, "status": "running", "summary": "Build the docs site", "command": "mkdocs build", "output": "building…"},
                         {"id": SVC_ID, "status": "running", "summary": "Serve the docs preview", "command": "mkdocs serve", "output": "serving on 8000"}]}}
            cfg = os.path.join(self.lab, "cfg.json")
            with open(cfg, "w") as f:
                json.dump({"chat": "http://127.0.0.1:%d/chat?token=%s" % (self.port, self.token), "frame": frame, "shots": os.environ.get("BG_KINDS_SHOTS", "")}, f)
            driver = os.path.join(self.lab, "driver.mjs")
            with open(driver, "w") as f:
                f.write(DRIVER)
            p = subprocess.run(["node", driver], capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, EXT_PKG=os.path.join(EXT, "package.json"), CFG=cfg))
            if p.returncode == 3:
                raise unittest.SkipTest("no playwright browser on this box — the served guard needs one (CI installs none)")
            self.assertEqual(p.returncode, 0, "driver failed:\n" + p.stdout[-3000:] + p.stderr[-3000:] + "\nkernel:\n" + open(self.klog).read()[-1500:])
            line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT:")), None)
            self.assertIsNotNone(line, "driver printed no result:\n" + p.stdout[-3000:])
            cls._r = json.loads(line[len("RESULT:"):])
        print("RESULT:" + json.dumps(cls._r), file=sys.stderr)   # the whole measurement rides every test's captured stderr (-rA shows it for a pass)
        return cls._r

    def test_every_row_sits_in_its_kinds_section_and_the_kept_task_wears_the_verdict_as_a_suffix(self):
        r = self._result()
        d = r["dark"]
        self.assertEqual(d["sections"], ["Agents", "Commands", "Watches"], "the kinds, in display order, and no section of any other name: %r" % d["sections"])
        self.assertEqual([(x["section"], x["label"]) for x in d["rows"]],
                         [("Agents", "Map the notes-api parser"), ("Commands", "Build the docs site"), ("Commands", "Serve the docs preview"), ("Watches", "the CI run on web")],
                         "each row under its kind; the service after the awaited command: %r" % d["rows"])
        agent, cmd, svc, watch = d["rows"]
        self.assertEqual(d["header"], "In the background · 1 agent · 1 command · 1 watch · 1 kept running", "the header counts every row it lists, the kept one apart")
        for x, kind in ((agent, "agents"), (cmd, "commands"), (svc, "commands"), (watch, "watches")):
            self.assertIn("bg-kind-" + kind, x["cls"].split(), "%s wears its kind: %r" % (x["label"], x["cls"]))
        self.assertIn("bg-kept", svc["cls"].split(), "the service is the kept row: %r" % svc["cls"])
        self.assertEqual(svc["kept"], KEPT_WORD, "the judge's verdict beside the label")
        for x in (agent, cmd, watch):
            self.assertNotIn("bg-kept", x["cls"].split(), "%s is awaited, not kept: %r" % (x["label"], x["cls"]))
            self.assertIsNone(x["kept"], "no suffix on an awaited row: %r" % x)
        self.assertEqual([x["caption"] for x in d["rows"]], ["running", "running", "running", "armed"])
        # the affordances stay: the agent's arrow and Stop, the command's Stop and fold caret, the service's Stop, the watch's Cancel
        self.assertTrue(agent["arrow"] and agent["stop"], "agent: arrow and Stop: %r" % agent)
        self.assertTrue(cmd["stop"] and cmd["caret"], "command: Stop and the fold caret: %r" % cmd)
        self.assertTrue(svc["stop"] and svc["caret"], "service: Stop and the fold caret: %r" % svc)
        self.assertTrue(watch["cancel"] and not watch["stop"], "watch: Cancel, no Stop: %r" % watch)
        self.assertEqual(r["light"]["sections"], d["sections"], "the cream theme changes no words")
        self.assertEqual(r["light"]["header"], d["header"])

    def test_one_hue_per_kind_for_the_dot_and_the_caption_in_both_themes_and_every_caption_reads_on_the_box(self):
        r = self._result()
        for name in ("dark", "light"):
            m = r[name]
            t = m["tokens"]
            agent, cmd, svc, watch = m["rows"]
            ground = composite(t["box"], t["page"])
            self.assertEqual(agent["dot"], t["working"], "%s: the agent's dot is the working gold: %r" % (name, agent))
            self.assertEqual(cmd["dot"], t["command"], "%s: the command's dot is the command blue: %r" % (name, cmd))
            self.assertEqual(svc["dot"], t["command"], "%s: the service is a command too: %r" % (name, svc))
            self.assertEqual(watch["dot"], t["await"], "%s: the watch's dot is the awaiting green: %r" % (name, watch))
            self.assertNotEqual(t["command"], t["working"], "%s: the command hue is not the agents': %r" % (name, t))
            self.assertEqual(float(svc["dotOpacity"]), 0.55, "%s: the kept row's dot is dimmed: %r" % (name, svc))
            for x in (agent, cmd, watch):
                self.assertEqual(float(x["dotOpacity"]), 1.0, "%s: an awaited row's dot is full: %r" % (name, x))
            self.assertEqual(svc["labelColor"], t["dim"], "%s: the kept row's label is the dim ink: %r" % (name, svc))
            self.assertEqual(svc["keptColor"], t["dim"], "%s: …and so is the verdict: %r" % (name, svc))
            self.assertGreaterEqual(contrast(t["dim"], ground), 4.5, "%s: the dim ink reads on the box: %r" % (name, t))
            for x in m["rows"]:
                self.assertGreaterEqual(contrast(x["captionColor"], ground), 4.5, "%s: the caption word reads on the box: %r" % (name, x))
            if name == "dark":
                for x, tokname in ((agent, "working"), (cmd, "command"), (svc, "command"), (watch, "await")):
                    self.assertEqual(x["captionColor"], t[tokname], "dark: the caption word is the kind hue itself: %r" % x)
            else:
                for x, tokname in ((agent, "working"), (cmd, "command"), (watch, "await")):
                    self.assertNotEqual(x["captionColor"], t[tokname], "cream: the caption word is the hue deepened, not the dot's colour: %r" % x)
        self.assertNotEqual(r["dark"]["tokens"]["command"], r["light"]["tokens"]["command"], "the command blue is a per-theme token")


if __name__ == "__main__":
    unittest.main()
