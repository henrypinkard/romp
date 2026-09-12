#!/usr/bin/env python3
"""T386 stage 1 (the user 2026-09-12): a card click deep into history did not land the first time; a second click
was needed. The landing audit (the kernel serving the session files one row per landing attempt) showed the shape
three times: the click asks for a window around the anchor (ok false, pointer-fetch-window, the anchor's time on the
row), the window lands two seconds later and files ok true pointer-exact with the time NULL, and a second click
seconds later lands the same anchor for real. pointer-exact asserted only that the anchor's turn was found and one
scroll write issued (landOn re-aligned for 1.2 s on the tab bar and the ledger box resizing, never on the transcript's
own moves), so the row could call a landing good that the reader never saw. This lab's first run on upstream/main
named the mover in the page's own scroll-write ledger: the window's REPLACE of the run shrank the transcript and the
follow-mode snap (tail-shrink) wrote the reader back to the bottom, because the landing had left follow mode on.

The served lab drives the real /chat page over a transcript longer than the wire tail (the T366 lab's boot) and
NAVIGATES into history the page does not hold, as a card's focus frame does, with the anchor and its time. It reads
what the page itself records: the landing row (locateDiag), the target's offset from the viewport top at the row and
over the next 1.5 s, and the scroll-write ledger (every programmatic write of #content names its writer, T262j), and
lets a LIVE turn land in the tail while the reader is on the landed message. A second road (the manager's datum of the
same day) clicks a card anchored on a turn's FIRST atom, a tool call inside a collapsed group of four, quoting words
that sit atoms later: the landing must align on the words, not the group. Three claims over one drive:

  1. the landing row keeps the click's time (red before the fix: the window's adoption reset it) and says whether the
     landing SETTLED, with the target's distance from the viewport top at settle time (red before: no such fields);
  2. the view holds: the target stays within its own row of the viewport top through the settle window and through
     the live turn's arrival, and no write but the landing's own follows it (red before: tail-shrink);
  3. the card anchored on a tool call lands the reader on the quoted words (red before: on the tool group).

Skips LOUDLY without the extension deps or a Playwright browser (CI installs none). All fixtures synthetic.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from test_live_paused_window_browser import DRIVER_HEAD, WindowLab, SID, TURNS   # noqa: E402  the shared boot and the page's state probe

LIVE_U = "33333333-4444-5555-6666-000000000001"   # the live turn appended mid-landing: synthetic uuids
LIVE_A = "33333333-4444-5555-6666-000000000002"

DRIVER = DRIVER_HEAD + r"""
const deep = cfg.deepUuid;
const ledger = () => page.evaluate(() => window.__sent.filter((m) => m.type === "clientDiag" && m.what === "scrollwrite")
  .map((m) => ({ writer: m.data.writer, before: m.data.before, after: m.data.after })));
const rows = () => page.evaluate(() => window.__sent.filter((m) => m.type === "locateDiag")
  .map((m) => ({ ok: m.ok, trail: m.trail, anchor: m.anchor || null, anchorT: m.anchorT === undefined ? null : m.anchorT, dist: m.dist === undefined ? null : m.dist,
                 settled: m.settled === undefined ? null : m.settled, superseded: m.superseded === undefined ? null : m.superseded, clamp: m.clamp === undefined ? null : m.clamp })));
// an element's box against the viewport top, and its own height (the row it must stay within)
const boxOf = (sel) => page.evaluate((s) => {
  const c = document.getElementById("content"); const t = document.querySelector(s);
  if (!t) return null; const r = t.getBoundingClientRect(); return { top: Math.round(r.top - c.getBoundingClientRect().top), h: Math.round(r.height) };
}, sel);
const offset = () => boxOf('#content .turn[data-uuid="' + deep + '"]');
const writesBefore = (await ledger()).length;
const q = (k) => "11111111-2222-3333-4444-" + pad(2 * k);   // the k-th question's uuid (the boot's formula; `pad` is the driver head's)
// ROAD 6 (round one, medium 3; run first, see below): a landing within a viewport of the tail: the scroll clamp stops the target short of the top,
// and the row says so (settled, with the clamp) instead of a miss
const rowsBefore6 = (await rows()).length;
const tailQ = q(cfg.turns - 1);
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: tailQ, anchorT: cfg.base + 2 * (cfg.turns - 1) });
// run FIRST, while the page is still attached to the tail run it booted with: a landing on a turn the page holds is exact;
// after a window road the page is detached and the same focus asks the kernel for a window instead. The exact landing's
// row goes out when its settle ends, so wait for THAT row, bounded, not a fixed pause
try { await page.waitForFunction((u) => window.__sent.some((m) => m.type === "locateDiag" && m.anchor === u && Array.isArray(m.trail) && m.trail[m.trail.length - 1] === "pointer-exact"), tailQ, { timeout: 15000 }); }
catch (e) { /* rows6 says what happened */ }
await page.waitForTimeout(200);
const tail6 = await boxOf('#content .turn[data-uuid="' + tailQ + '"]');
const rows6 = (await rows()).slice(rowsBefore6);
const scroll6 = await page.evaluate(() => { const c = document.getElementById("content"); return { top: c.scrollTop, max: c.scrollHeight - c.clientHeight }; });
const rowsBefore1 = (await rows()).length;   // road 6 ran first: its rows are not road 1's
// ROAD 1: the reader NAVIGATES into history the page does not hold: a card's focus frame, the anchor and its time
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: deep, anchorT: cfg.deepT });
try { await page.waitForFunction((u) => !!document.querySelector('#content .turn[data-uuid="' + u + '"]'), deep, { timeout: 20000 }); }
catch (e) { const st = await state(); console.error("the deep link never landed: " + JSON.stringify(st)); process.exit(1); }
const o0 = await offset();
await page.waitForTimeout(300); const o300 = await offset();
await page.waitForTimeout(400); const o700 = await offset();
const rowsAtLand = (await rows()).slice(rowsBefore1);
// a LIVE turn lands in the tail while the reader is on the landed message: the transcript grows, the event the pusher
// wakes on, exactly as a live session's does under a reader deep in its history
const now = new Date();
fs.appendFileSync(cfg.transcript,
  JSON.stringify({ type: "user", uuid: cfg.liveU, parentUuid: null, timestamp: now.toISOString(), sessionId: cfg.sid,
                   message: { role: "user", content: "and one more question, live, about the notes api" } }) + "\n" +
  JSON.stringify({ type: "assistant", uuid: cfg.liveA, parentUuid: cfg.liveU, timestamp: new Date(now.getTime() + 1000).toISOString(), sessionId: cfg.sid,
                   message: { role: "assistant", model: "claude-fable-5-1", stop_reason: "end_turn", content: [{ type: "text", text: "Live answer: the handler reads the note by id and returns it." }] } }) + "\n");
// the live turn reaches the page only if the kernel sends this client a tail; either way the reader's view is measured
let liveArrived = true;
try { await page.waitForFunction((u) => !!document.querySelector('#content .turn[data-uuid="' + u + '"]'), cfg.liveA, { timeout: 8000 }); }
catch (e) { liveArrived = false; }
await page.waitForTimeout(500);
const oLive = await offset();
await page.waitForTimeout(800);
const oLate = await offset();
const rowsAll = (await rows()).slice(rowsBefore1);
const writes = (await ledger()).slice(writesBefore);
// ROAD 2 (the manager's datum, T386): a card anchored on a turn's FIRST atom, a tool call inside a collapsed group of four,
// quoting words that sit atoms later: the landing aligns on the quoted words, not on the tool group
const rowsBefore2 = (await rows()).length;
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: cfg.toolUuid, anchorT: cfg.toolT, anchorQuote: cfg.toolQuote });
try { await page.waitForFunction((q) => Array.from(document.querySelectorAll("#content .turn-assistant .assistant.md p")).some((e) => (e.textContent || "").includes(q)), cfg.toolQuote, { timeout: 20000 }); }
catch (e) { const st = await state(); console.error("the tool-turn card never landed: " + JSON.stringify(st)); process.exit(1); }
await page.waitForTimeout(1500);
const quoted = await page.evaluate((q) => {
  const c = document.getElementById("content");
  const e = Array.from(document.querySelectorAll("#content .turn-assistant .assistant.md p")).find((x) => (x.textContent || "").includes(q));
  if (!e) return null; const r = e.getBoundingClientRect(); return { top: Math.round(r.top - c.getBoundingClientRect().top), h: Math.round(r.height) };
}, cfg.toolQuote);
const anchorBox = await boxOf('#content .turn[data-uuid="' + cfg.toolUuid + '"]');
const rows2 = (await rows()).slice(rowsBefore2);
// ROAD 3 (round one, medium 5): the same tool-anchored card with NO quote: the landing aligns on the turn's first text atom
// below the group head, never on the group
const rowsBefore3 = (await rows()).length;
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: q(10), anchorT: cfg.base + 20 });   // step away first (a resident turn)
await page.waitForTimeout(1500);
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: cfg.toolUuid, anchorT: cfg.toolT });
await page.waitForTimeout(1500);
const words3 = await page.evaluate((qt) => {
  const c = document.getElementById("content");
  const e = Array.from(document.querySelectorAll("#content .turn-assistant .assistant.md")).find((x) => (x.textContent || "").includes(qt));
  if (!e) return null; const r = e.getBoundingClientRect(); return { top: Math.round(r.top - c.getBoundingClientRect().top), h: Math.round(r.height) };
}, cfg.toolQuote);
const anchor3 = await boxOf('#content .turn[data-uuid="' + cfg.toolUuid + '"]');
const anchor3cls = await page.evaluate((u) => { const t = document.querySelector('#content .turn[data-uuid="' + u + '"]'); return t ? t.className : null; }, cfg.toolUuid);
const rows3 = (await rows()).slice(rowsBefore3);
// ROAD 4 (round one, medium 1): the reader takes over during the settle by a move the scroll classifier reads as a gesture
// (a scrollbar drag or a touch swipe write no wheel event): the landing yields, the view stays where the reader put it
const rowsBefore4 = (await rows()).length;
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: q(30), anchorT: cfg.base + 60 });
try { await page.waitForFunction((u) => { const t = document.querySelector('#content .turn[data-uuid="' + u + '"]'); if (!t) return false; const c = document.getElementById("content"); return Math.abs(t.getBoundingClientRect().top - c.getBoundingClientRect().top) < 40; }, q(30), { timeout: 20000 }); }
catch (e) { const st = await state(); console.error("the gesture road's landing never arrived: " + JSON.stringify(st)); process.exit(1); }
await page.waitForTimeout(300);
const moved4 = await page.evaluate(() => { const c = document.getElementById("content"); c.scrollTop = c.scrollTop + 900; return c.scrollTop; });
await page.waitForTimeout(1400);
const after4 = await page.evaluate(() => document.getElementById("content").scrollTop);
const writes4 = (await ledger()).filter((w) => w.before === moved4 || w.after === moved4 || (Math.abs(w.before - moved4) < 4));
const rows4 = (await rows()).slice(rowsBefore4);
// ROAD 5 (round one, medium 2): two clicks 120 ms apart file TWO rows, the first superseded
const rowsBefore5 = (await rows()).length;
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: q(50), anchorT: cfg.base + 100 });
await page.waitForTimeout(120);
await page.evaluate((frame) => window.postMessage(frame, "*"), { type: "focus", id: cfg.sid, anchor: q(52), anchorT: cfg.base + 104 });
await page.waitForTimeout(2500);
const rows5 = (await rows()).slice(rowsBefore5);
// the anchor's place in the DOM: its ancestors up to #content and the siblings that follow it (the turn's atoms as rendered),
// and whether the page can highlight at all; the diagnosis when the words are not at the top
const dom2 = await page.evaluate((u) => {
  const t = document.querySelector('#content .turn[data-uuid="' + u + '"]'); if (!t) return null;
  const chain = []; for (let n = t.parentElement; n && n.id !== "content"; n = n.parentElement) chain.push(n.className || n.tagName.toLowerCase());
  const sibs = []; for (let n = t.nextElementSibling, i = 0; n && i < 7; n = n.nextElementSibling, i++) sibs.push((n.className || n.tagName.toLowerCase()) + " | " + (n.textContent || "").trim().slice(0, 40));
  const c = document.getElementById("content"); const cr = c.getBoundingClientRect();
  const atTop = document.elementFromPoint(cr.left + cr.width / 2, cr.top + 4);
  return { chain, sibs, highlights: !!(CSS && CSS.highlights) && typeof Highlight !== "undefined", atTop: atTop ? (atTop.className || atTop.tagName.toLowerCase()) + " | " + (atTop.textContent || "").trim().slice(0, 40) : null,
           writesAfter: window.__sent.filter((m) => m.type === "clientDiag" && m.what === "scrollwrite").slice(-6).map((m) => m.data.writer + ":" + m.data.before + ">" + m.data.after) };
}, cfg.toolUuid);
const st = await state();
if (cfg.shots) await page.screenshot({ path: cfg.shots + "-settled.png" });
await browser.close();
process.stdout.write("RESULT:" + JSON.stringify({ o0, o300, o700, oLive, oLate, liveArrived, rowsAtLand, rowsAll, writes, quoted, anchorBox, rows2, dom2,
  words3, anchor3, anchor3cls, rows3, moved4, after4, writes4, rows4, rows5, tail6, rows6, scroll6, after: st }) + "\n", () => process.exit(0));
"""


class ServedLandingSettles(WindowLab):
    _r = None

    def _result(self):
        """One drive per class: the tests read the same landings (a second drive would land on a page that holds the
        windows already, a different road)."""
        cls = type(self)
        if cls._r is None:
            cls._r = self._drive(DRIVER, "settles", extra={"liveU": LIVE_U, "liveA": LIVE_A, "turns": TURNS})
            print("RESULT:" + json.dumps(cls._r), file=sys.stderr)   # the whole measurement rides a failure's captured stderr
        return cls._r

    def test_the_landing_row_keeps_the_clicks_time_and_says_whether_the_landing_settled(self):
        r = self._result()
        land = [x for x in r["rowsAtLand"] if x["ok"] and x["trail"] and x["trail"][-1] == "pointer-exact"]
        self.assertEqual(len(land), 1, "one exact landing row for the navigation: %r" % r["rowsAtLand"])
        row = land[0]
        self.assertEqual(row["anchorT"], self.deep_t, "the row keeps the click's time through the window's adoption: %r" % row)
        self.assertIsNotNone(row["settled"], "the row says whether the landing settled: %r" % row)
        self.assertIsNotNone(row["dist"], "…and the target's distance from the viewport top at settle time: %r" % row)
        self.assertTrue(row["settled"], "the landing settled: %r" % row)
        self.assertLessEqual(abs(row["dist"]), max(8, r["oLate"]["h"] if r["oLate"] else 8), "the recorded distance is within the target's own row: %r" % row)

    def test_the_view_holds_on_the_landed_message_through_the_settle_window_and_a_live_turn(self):
        r = self._result()
        for k in ("o0", "o300", "o700", "oLive", "oLate"):
            self.assertIsNotNone(r[k], "the target stayed resident at %s: %r" % (k, r["after"]))
        h = r["o0"]["h"]
        moved = ", ".join("%s: %s → %s" % (w["writer"], w["before"], w["after"]) for w in r["writes"]) or "no write after the landing"
        for k in ("o300", "o700", "oLive", "oLate"):
            self.assertLessEqual(abs(r[k]["top"]), max(8, h), "the target left the viewport top by %s (%r); the writes after the landing: %s; live turn arrived: %s"
                                 % (k, r[k], moved, r["liveArrived"]))
        # the writes that followed the landing are the landing's own (its re-aligns), never a rebuild's placement
        strangers = [w["writer"] for w in r["writes"] if w["writer"] not in ("land-on", "land-realign")]
        self.assertEqual(strangers, [], "a write other than the landing's moved the view after it: %s" % moved)

    def test_a_card_anchored_on_a_tool_call_lands_on_the_words_it_quotes_not_on_the_tool_group(self):
        r = self._result()
        self.assertIsNotNone(r["quoted"], "the quoted words are rendered: %r" % r["after"])
        self.assertIsNotNone(r["anchorBox"], "the anchor's tool turn is rendered: %r" % r["after"])
        q, a = r["quoted"], r["anchorBox"]
        self.assertLessEqual(abs(q["top"]), max(8, q["h"]), "the quoted words sit at the viewport top, within their own row; the tool turn: %r, the words: %r" % (a, q))
        self.assertLess(a["top"], q["top"], "the tool group stands above the words, off the top: %r vs %r" % (a, q))
        land = [x for x in r["rows2"] if x["ok"] and x["trail"] and x["trail"][-1] == "pointer-exact"]
        self.assertEqual(len(land), 1, "one exact landing row for the card: %r" % r["rows2"])
        self.assertTrue(land[0]["settled"], "…settled on the words: %r" % land[0])

    def test_the_same_card_without_a_quote_lands_on_the_turns_first_text_atom_not_on_the_tool_group(self):
        # round one, medium 5: a grouped run of tool calls renders as ONE group head carrying the first tool's uuid, and the
        # no-quote fallback must walk from that head to the words
        r = self._result()
        self.assertIsNotNone(r["words3"], "the words are rendered: %r" % r["after"])
        self.assertIn("turn-toolgroup", r["anchor3cls"] or "", "the anchor resolves to the tool group's head: %r" % r["anchor3cls"])
        w, a = r["words3"], r["anchor3"]
        self.assertLessEqual(abs(w["top"]), max(8, w["h"]), "the words sit at the viewport top without a quote; the group: %r, the words: %r" % (a, w))
        self.assertLess(a["top"], w["top"], "the group stands above the words")

    def test_a_reader_taking_over_during_the_settle_by_any_gesture_keeps_the_view_and_two_quick_clicks_file_two_rows(self):
        r = self._result()
        # medium 1: the move the classifier reads as a gesture (no wheel event) is respected: no re-land undoes it
        self.assertLessEqual(abs(r["after4"] - r["moved4"]), 60, "the view stayed where the reader put it (moved to %s, now %s); writes near the move: %r" % (r["moved4"], r["after4"], r["writes4"]))
        realigns = [w for w in r["writes4"] if w["writer"] == "land-realign" and w["before"] == r["moved4"]]
        self.assertEqual(realigns, [], "no re-land wrote the reader's move back: %r" % r["writes4"])
        # medium 2: two landings inside one settle window are two rows, the first marked superseded
        exact = [x for x in r["rows5"] if x["ok"] and x["trail"] and x["trail"][-1] == "pointer-exact"]
        self.assertEqual(len(exact), 2, "two exact rows for two clicks: %r" % r["rows5"])
        self.assertTrue(exact[0]["superseded"], "the first row carries the superseded mark: %r" % exact[0])
        self.assertFalse(exact[0]["settled"], "…and is not settled: %r" % exact[0])
        self.assertFalse(exact[1]["superseded"], "the second is the landing that stood: %r" % exact[1])

    def test_a_landing_within_a_viewport_of_the_tail_settles_against_the_spot_the_clamp_allows(self):
        # round one, medium 3
        r = self._result()
        exact = [x for x in r["rows6"] if x["ok"] and x["trail"] and x["trail"][-1] == "pointer-exact"]
        self.assertEqual(len(exact), 1, "one exact row for the tail landing: %r" % r["rows6"])
        row = exact[0]
        self.assertGreaterEqual(r["scroll6"]["top"], r["scroll6"]["max"] - 2, "the view is at the bottom, where the clamp stops it: %r" % r["scroll6"])
        self.assertGreater(r["tail6"]["top"], 40, "the target sits below the viewport top, as it must near the tail: %r" % r["tail6"])
        self.assertTrue(row["settled"], "the landing is settled against the reachable spot: %r" % row)
        self.assertGreater(row["clamp"] or 0, 0, "…and the row names the clamp: %r" % row)
        self.assertLessEqual(abs(row["dist"] or 0), 24, "the distance from the reachable spot is within a row: %r" % row)


if __name__ == "__main__":
    unittest.main()
