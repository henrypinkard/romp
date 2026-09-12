#!/usr/bin/env python3
"""T389 (the user 2026-09-12): with a provisional message showing (a send not yet landed, or one queued behind a running
turn), a follow-up they send was not shown, above or below it, until it fully landed. Both must be visible the whole
time as their own rows, in send order, and the only thing that changes when a message lands is that message's row
(provisional to real); nothing else moves or appears.

The served lab drives the real /chat page over the T373 lab's boot: a session whose transcript ends inside a running
tool call, so every send the kernel receives waits behind the turn (its queued copy is the kernel's word for it, the
page's own bubble the reader's). It sends A, then B while A is provisional, then C, reading the tail's rows (a queued
bubble or a landed user turn, each with its words) right after each press and again after the kernel's pushes. The claim:
a second send shows at once as its own row after the first, and stays through the pushes; a third the same.

The landing (one message's row turning from provisional to real while the others hold) is NOT driven here: no CLI runs
in this lab, and a copy the kernel holds leaves its queue only when the kernel feeds it to one, so a record written into
the transcript by hand lands nothing (the kernel keeps the copy, and the page rightly keeps the send provisional by its
id). That transition is executed on the rule itself in ui/webview/send-pending-overlay.test.ts.

Skips LOUDLY without the extension deps or a Playwright browser (CI installs none). All fixtures synthetic.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_queued_rescind_browser import QueuedLab, SID   # noqa: E402  the shared boot: a session mid-turn that parks every send

TEXT_A = "first, tighten the search index"
TEXT_B = "second, add the missing test"
TEXT_C = "third, run the formatter once more"

DRIVER = r"""
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.EXT_PKG);
const { chromium } = require("playwright");
const cfg = JSON.parse(fs.readFileSync(process.env.CFG, "utf8"));
let browser;
try { browser = await chromium.launch(); }
catch (e) { console.error("browser-launch-failed: " + e); process.exit(3); }
const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
await page.addInitScript(() => {
  const send = WebSocket.prototype.send;
  window.__sent = [];
  WebSocket.prototype.send = function (d) { try { const m = JSON.parse(d); if (m && m.type) window.__sent.push(m); } catch (e) { /* not a frame */ } return send.call(this, d); };
});
await page.goto(cfg.chat);
await page.waitForSelector("#tabs .tab, #tabs [data-sid]", { timeout: 20000 });
await page.waitForSelector("#composer-input", { timeout: 20000 });
await page.waitForTimeout(600);
// the tail's rows as the reader sees them: a queued bubble (the kernel's copy or the page's own) is a row with its words, a
// landed user turn is a row with its words; hidden units and hidden copies are no rows
const rows = () => page.evaluate(() => {
  const out = [];
  for (const t of Array.from(document.querySelectorAll("#content .turn"))) {
    if (!(t instanceof HTMLElement)) continue;
    if (t.classList.contains("turn-queued-hidden") || getComputedStyle(t).display === "none") continue;
    if (t.classList.contains("turn-queued")) {
      // the group's header names what the group is: the page's own bare group ("sending…"), a held card ("landing…"), or the
      // kernel's queue ("N queued messages"); a bubble's row carries its group's word so a duplicate names its source
      const head = ((t.querySelector(".queued-count") || {}).textContent || "").trim().slice(0, 30);
      for (const b of Array.from(t.querySelectorAll(".queued-bubble"))) { if (getComputedStyle(b).display !== "none") out.push({ kind: "queued", text: (b.textContent || "").trim().slice(0, 40), group: head }); }
    } else if (t.classList.contains("turn-user")) out.push({ kind: "user", text: (t.textContent || "").trim().slice(0, 40) });
    else out.push({ kind: t.className.split(" ").filter((c) => c.startsWith("turn-"))[0] || "turn", text: (t.textContent || "").trim().slice(0, 40) });
  }
  return out.slice(-6);
});
const rowWith = (t) => page.waitForFunction((x) => Array.from(document.querySelectorAll("#content .turn-queued:not(.turn-queued-hidden) .queued-bubble, #content .turn-user")).some((b) => (b.textContent || "").includes(x)), t, { timeout: 15000 });
const sendText = async (t) => { await page.fill("#composer-input", t); await page.press("#composer-input", "Enter"); };
// A: the first send, provisional behind the running turn
await sendText(cfg.textA);
await rowWith(cfg.textA); await page.waitForTimeout(700);
const afterA = await rows();
// B: sent while A is provisional; read at once, then after the kernel's pushes
await sendText(cfg.textB);
let bAtOnce = true;
try { await page.waitForFunction((x) => Array.from(document.querySelectorAll("#content .turn-queued:not(.turn-queued-hidden) .queued-bubble")).some((b) => (b.textContent || "").includes(x)), cfg.textB, { timeout: 1500 }); }
catch (e) { bAtOnce = false; }
const afterB0 = await rows();
await page.waitForTimeout(1000); const afterB1 = await rows();
await page.waitForTimeout(2500); const afterB2 = await rows();
// C: a third
await sendText(cfg.textC);
let cAtOnce = true;
try { await page.waitForFunction((x) => Array.from(document.querySelectorAll("#content .turn-queued:not(.turn-queued-hidden) .queued-bubble")).some((b) => (b.textContent || "").includes(x)), cfg.textC, { timeout: 1500 }); }
catch (e) { cAtOnce = false; }
const afterC0 = await rows();
await page.waitForTimeout(2000); const afterC1 = await rows();
const sends = await page.evaluate(() => window.__sent.filter((m) => m.type === "sendMessage").map((m) => m.text));
await browser.close();
// through the stream, drained before the exit: a single synchronous write past the pipe's 64 KiB buffer comes out truncated
process.stdout.write("RESULT:" + JSON.stringify({ afterA, bAtOnce, afterB0, afterB1, afterB2, cAtOnce, afterC0, afterC1, sends }) + "\n", () => process.exit(0));
"""


def _tail(rows, texts):
    """The rows carrying the lab's own texts, in order: (kind, which)."""
    out = []
    for r in rows:
        for name, t in texts.items():
            if t[:40] in r["text"] or r["text"] in t:
                out.append((r["kind"], name))
                break
    return out


class ServedProvisionalRows(QueuedLab):
    _r = None

    def _result(self):
        cls = type(self)
        if cls._r is None:
            cfg = os.path.join(self.lab, "cfg.json")
            with open(cfg, "w") as f:
                json.dump({"chat": "http://127.0.0.1:%d/chat?token=%s" % (self.port, self.token), "sid": SID,
                           "textA": TEXT_A, "textB": TEXT_B, "textC": TEXT_C}, f)
            driver = os.path.join(self.lab, "driver.mjs")
            with open(driver, "w") as f:
                f.write(DRIVER)
            import subprocess
            p = subprocess.run(["node", driver], capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, EXT_PKG=os.path.join(self.EXT, "package.json"), CFG=cfg))
            if p.returncode == 3:
                raise unittest.SkipTest("no playwright browser on this box — the served guard needs one (CI installs none)")
            self.assertEqual(p.returncode, 0, "driver failed:\n" + p.stdout[-3000:] + p.stderr[-3000:] + "\nkernel:\n" + open(self.klog).read()[-1500:])
            line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT:")), None)
            self.assertIsNotNone(line, "driver printed no result:\n" + p.stdout[-3000:])
            cls._r = json.loads(line[len("RESULT:"):])
        print("RESULT:" + json.dumps(cls._r), file=sys.stderr)   # the whole measurement rides EVERY test's captured stderr: a failing test shows it
        return cls._r

    TEXTS = {"A": TEXT_A, "B": TEXT_B, "C": TEXT_C}

    def test_a_second_send_shows_at_once_as_its_own_row_after_the_first_and_a_third_after_that(self):
        r = self._result()
        self.assertEqual(_tail(r["afterA"], self.TEXTS), [("queued", "A")], "A alone, provisional: %r" % r["afterA"])
        self.assertTrue(r["bAtOnce"], "B's row did not appear within 1.5 s of the press: %r" % r["afterB0"])
        for k in ("afterB0", "afterB1", "afterB2"):
            self.assertEqual(_tail(r[k], self.TEXTS), [("queued", "A"), ("queued", "B")], "%s: two rows, A then B, each provisional: %r" % (k, r[k]))
        self.assertTrue(r["cAtOnce"], "C's row did not appear within 1.5 s of the press: %r" % r["afterC0"])
        for k in ("afterC0", "afterC1"):
            self.assertEqual(_tail(r[k], self.TEXTS), [("queued", "A"), ("queued", "B"), ("queued", "C")], "%s: three rows in send order: %r" % (k, r[k]))
        self.assertEqual(r["sends"], [TEXT_A, TEXT_B, TEXT_C], "three send frames, in order")



if __name__ == "__main__":
    unittest.main()
