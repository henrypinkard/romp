// The settle rule for a deep-link landing (landing-settle.ts), executed; and the render.ts wiring pins (T386 stage 1).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { SETTLE_MS, SETTLE_QUIET, settleStep, settleRowFields, withinRow } from "./landing-settle";

const RENDER = fs.readFileSync(path.resolve(process.cwd(), "..", "ui", "webview", "render.ts"), "utf8");

test("within its own row: a row's height, never under a few pixels", () => {
  assert.equal(withinRow(0, 40), true);
  assert.equal(withinRow(-40, 40), true);
  assert.equal(withinRow(41, 40), false);
  assert.equal(withinRow(7, 0), true, "a zero-height row still tolerates rounding");
  assert.equal(withinRow(9, 0), false);
});

test("two quiet samples settle the landing early; a sample off the row asks for a re-land; the reader's gesture ends it", () => {
  assert.equal(settleStep([], 40, false, 0), "wait", "nothing measured yet");
  assert.equal(settleStep([{ at: 0, dist: 0 }], 40, false, 10), "wait", "one sample is not quiet yet");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 250, dist: 2 }], 40, false, 260), "settled");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 250, dist: 190 }], 40, false, 260), "realign", "the page moved the target: put it back");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 250, dist: 190 }, { at: 300, dist: 1 }], 40, false, 320), "wait", "one quiet sample after a re-land");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 250, dist: 190 }, { at: 300, dist: 1 }, { at: 700, dist: 0 }], 40, false, 720), "settled");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 250, dist: 190 }], 40, true, 260), "gave-up", "the reader scrolled: theirs now");
  assert.equal(SETTLE_QUIET, 2);
});

test("the window's end files the landing as it stands: settled within the row, else unsettled, never held forever", () => {
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 1200, dist: 3 }], 40, false, SETTLE_MS), "settled");
  assert.equal(settleStep([{ at: 0, dist: 0 }, { at: 1200, dist: 300 }], 40, false, SETTLE_MS), "unsettled", "off the row at the end: a miss, on the record");
  assert.equal(settleStep([{ at: 0, dist: 300 }], 40, false, SETTLE_MS + 50), "unsettled");
  assert.equal(SETTLE_MS, 1200, "the span landOn already re-aligned within");
});

test("the row's fields: the last distance rounded, settled by the step; a gave-up landing within the row is not a miss", () => {
  assert.deepEqual(settleRowFields("settled", [{ at: 0, dist: 0 }, { at: 250, dist: 2.4 }], 40), { dist: 2, settled: true });
  assert.deepEqual(settleRowFields("unsettled", [{ at: 0, dist: 0 }, { at: 1200, dist: 300.6 }], 40), { dist: 301, settled: false });
  assert.deepEqual(settleRowFields("gave-up", [{ at: 0, dist: 0 }, { at: 100, dist: 5 }], 40), { dist: 5, settled: true });
  assert.deepEqual(settleRowFields("gave-up", [{ at: 0, dist: 0 }, { at: 100, dist: 500 }], 40), { dist: 500, settled: false });
  assert.deepEqual(settleRowFields("wait", [], 40), { dist: null, settled: false }, "never measured");
});

test("render.ts wiring: landOn ends follow mode, feeds the rule from the page's own events, files the row at settle time, and the walk-forward waits", () => {
  assert.match(RENDER, /import \{ SETTLE_MS, settleStep, settleRowFields, type SettleSample \} from "\.\/landing-settle";/);
  assert.match(RENDER, /if \(c && v\) v\.stick = atBottom\(c\); \}/, "a landing ends follow mode unless it put the reader at the bottom (the tail-shrink snap otherwise undoes it)");
  assert.match(RENDER, /const landSettle = \{ turn: target, at, uuid: flashKey \?\? null, quote: quote \?\? null, rowH: Math\.max\(8, at\.getBoundingClientRect\(\)\.height\), samples: \[\] as SettleSample\[\],/, "one settle in flight per landing, with what re-finds its target");
  assert.match(RENDER, /ro\.observe\(at\); if \(at !== target\) ro\.observe\(target\);/, "the aligned element's box, and the turn's");
  assert.match(RENDER, /for \(const sp of Array\.from\(v\.el\.querySelectorAll\("\.tx-spacer"\)\)\) ro\.observe\(sp\);/, "the view's spacers: their size from estimate to measurement");
  assert.match(RENDER, /function settleTick\(\): void \{/);
  assert.match(RENDER, /const step = settleStep\(s\.samples, s\.rowH, s\.gesture, Date\.now\(\) - s\.start\);/);
  assert.match(RENDER, /if \(step === "realign"\) \{ settleLand\(s, "land-realign"\); return; \}/, "a re-land is a write of the landing's own, attributed");
  assert.match(RENDER, /settleFinish\(s, settleRowFields\(step, s\.samples, s\.rowH\)\);/);
  assert.match(RENDER, /if \(s\.row\) vscodeApi\?\.postMessage\(\{ \.\.\.s\.row, \.\.\.fields \}\);/, "the deferred row goes out with the measurement");
  assert.match(RENDER, /if \(after !== before && landSettling && !landSettling\.done && writer !== "land-on" && writer !== "land-realign"\) settleSample\(\);/, "another writer's move during the settle is a sample, so the rule re-lands");
  assert.match(RENDER, /if \(scrolled && landSettling && !landSettling\.done && landTrail\[landTrail\.length - 1\] === "pointer-exact"\) landSettling\.row = row;\s*\n\s*else vscodeApi\?\.postMessage\(row\);/, "an exact landing's row waits for the settle; every other outcome files at once");
  assert.match(RENDER, /if \(landSettling && !landSettling\.done\) \{ afterSettle\.push\(\(\) => edgeCheckAfterWindow\(sid\)\); return; \}/, "the walk-forward of a detached window that fits waits for the landing to settle");
  assert.match(RENDER, /pendingAnchorT = ask\?\.t \?\? null; pendingAnchorKind = ask\?\.kind \?\? null;/, "the click's time and kind ride through the window's adoption");
});

test("render.ts wiring: the settle re-finds its target by uuid after a rebuild replaced the DOM, and gives up honestly when the turn is gone", () => {
  assert.match(RENDER, /function settleResolve\(s: NonNullable<typeof landSettling>\): HTMLElement \| null \{\s*\n\s*if \(s\.at\.isConnected\) return s\.at;\s*\n\s*const turn = s\.uuid \? findTurnEl\(s\.uuid\) : null;/, "a detached box measures as zeros: re-find, never measure it");
  assert.match(RENDER, /s\.at = \(s\.quote \? highlightCiteSpan\(turn, s\.quote\) : null\) \?\? firstTextAtomBelow\(turn\) \?\? turn;/, "the same alignment as the landing's, re-derived");
  assert.match(RENDER, /if \(!at\) \{ settleFinish\(s, \{ dist: null, settled: false \}\); return; \}/, "the turn left the view: the row says so");
  assert.match(RENDER, /function findTurnEl\(uuid: string\): HTMLElement \| null \{/);
});

test("render.ts wiring: a card anchored on a turn's first atom lands on the quoted words, or the turn's text atom, not the tool group", () => {
  assert.match(RENDER, /const quote = pendingAnchorQuote; pendingAnchorQuote = null;\s*\n\s*const quoteEl = quote \? highlightCiteSpan\(target, quote\) : null;\s*\n\s*landOn\(target, uuid, quoteEl \?\? firstTextAtomBelow\(target\), quote\);/);
  assert.match(RENDER, /function highlightCiteSpan\(target: HTMLElement, quote: string\): HTMLElement \| null \{/, "the highlight returns the element the sentence starts in");
  assert.match(RENDER, /for \(const atom of turnAtomsOf\(target\)\) \{\s*\n\s*const walker = document\.createTreeWalker\(atom, NodeFilter\.SHOW_TEXT\);/, "the quote is searched across the turn's atoms");
  assert.match(RENDER, /return range\.startContainer\.parentElement;/);
  assert.match(RENDER, /function firstTextAtomBelow\(target: HTMLElement\): HTMLElement \| null \{\s*\n\s*if \(!target\.classList\.contains\("turn-tool"\) && !target\.classList\.contains\("turn-thinking"\)\) return null;/);
  assert.match(RENDER, /function turnAtomsOf\(target: HTMLElement\): HTMLElement\[\] \{/);
  assert.match(RENDER, /if \(!\(n instanceof HTMLElement\) \|\| !n\.classList\.contains\("turn"\) \|\| n\.classList\.contains\("turn-user"\)\) break;/, "the turn ends at the next user turn");
  assert.match(RENDER, /function landOn\(target: HTMLElement, flashKey\?: string, alignOn\?: HTMLElement \| null, quote\?: string \| null\) \{/);
  assert.match(RENDER, /const at = alignOn \?\? target;/);
});
