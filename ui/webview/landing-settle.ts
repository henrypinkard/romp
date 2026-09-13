// A deep-link landing SETTLES before it is called good (T386 stage 1, the user 2026-09-12: a card click deep into
// history did not land the first time; the landing audit had filed the first landing as exact). The landing write puts
// the target's top at the viewport top; what follows in the next second can move it (the transcript's own boxes
// sizing in, a rewindow write of the virtualiser, a rebuild's placement), and until now nothing measured where the
// target ended up. This module is the rule; render.ts feeds it the target's distance from the viewport top as the
// page's own events arrive (the target or the view resizing, another writer moving #content, two bounded timers) and
// acts on the step: re-land, or finish and file the landing row with the measured distance. Pure, so node executes it.

/** The settle window: the span landOn already re-aligned within for the boxes above the transcript. */
export const SETTLE_MS = 1200;
/** A reader's gesture needs its own evidence (round two, medium): an input event on the scroller (a pointer down or a drag,
 *  a touch, a wheel, a key) at most this many ms before the scroll event it caused. The browser's own scroll anchoring moves
 *  scrollTop with no write and no input (a node inserted or a spacer re-estimated above the viewport), and the classifier
 *  reads that as a gesture too; without evidence such a scroll is a SAMPLE for the settle, never a takeover. A scroll follows
 *  its input within a frame or two; the window only bounds staleness. */
export const SETTLE_INPUT_MS = 120;
/** The one early backstop sample beside the event samples: the first paint after the landing's own render, where a page
 *  that moves nothing settles on its two quiet samples instead of waiting for the window's end (round one, low 5). */
export const SETTLE_FIRST_PAINT_MS = 250;
/** The row a landing must sit within is the aligned element's own height, capped at this fraction of the viewport: a
 *  600 px miss on a 900 px message is a miss (round one, low 1). */
export const SETTLE_ROW_VIEWPORT_CAP = 0.25;

/** How far short of the viewport top the scroll clamp stops a target: with the target `targetY` px into the scroll space
 *  and the scroller able to scroll at most scrollHeight − clientHeight, the target's top can come no closer to the viewport
 *  top than this many px. 0 when the target can reach the top. A landing near the tail is judged against this spot, not the
 *  top (round one, medium 3: a correct landing within a viewport of the tail read as a 93 px miss and re-landed no-op writes). */
export function reachableOffset(targetY: number, scrollHeight: number, clientHeight: number): number {
  const maxScroll = Math.max(0, scrollHeight - clientHeight);
  return Math.max(0, Math.round(targetY - maxScroll));
}

/** Whether a scroll at `scrollAt` (ms) has a reader's input behind it: one at `lastInputAt` within SETTLE_INPUT_MS before it.
 *  0 or null = no input seen. */
export function gestureEvidence(lastInputAt: number | null | undefined, scrollAt: number): boolean {
  return !!lastInputAt && scrollAt - lastInputAt >= 0 && scrollAt - lastInputAt <= SETTLE_INPUT_MS;
}

export interface SettleSample { at: number; dist: number }   // at: ms since the landing write; dist: the target's top vs the viewport top, px

export type SettleStep = "wait" | "realign" | "settled" | "unsettled" | "gave-up";

/** Within its own row: the target's top sits inside [−rowH, rowH] of the viewport top (a row's height, never less than a
 *  few px, so a sub-pixel or border rounding never reads as a miss). */
export function withinRow(dist: number, rowH: number): boolean {
  return Math.abs(dist) <= Math.max(8, rowH);
}

/** The rule, over the samples taken so far (oldest first), the target's row height, whether the reader has taken over
 *  (a wheel or key of their own), and the clock:
 *  - the reader's gesture ends the settle: the landing gave up its place to them ("gave-up"; the row records the last
 *    distance as it stood, settled false when it was off);
 *  - a sample outside the row before the window's end asks for a re-land ("realign"): the page moved the target, the
 *    landing puts it back;
 *  - the window's end settles on the last sample ("settled" within the row, else "unsettled"), so a landing that never
 *    quietens is still filed, with its distance, rather than held forever. Nothing settles EARLY (round two, low 1): two
 *    adjacent quiet samples used to end the settle about 60 ms in, and a displacement later in the window (the tab bar
 *    wrapping to a second row) was neither sampled nor corrected; quiet means the window ran out with the target on its row;
 *  - otherwise "wait". */
export function settleStep(samples: readonly SettleSample[], rowH: number, gesture: boolean, now: number): SettleStep {
  if (gesture) return "gave-up";
  const last = samples.length ? samples[samples.length - 1] : null;
  if (last && !withinRow(last.dist, rowH) && now < SETTLE_MS) return "realign";
  if (now >= SETTLE_MS) return last && withinRow(last.dist, rowH) ? "settled" : "unsettled";
  return "wait";
}

/** The fields the landing row gains when the settle ends: the last measured distance (px, the target's top vs the
 *  viewport top; null when the target was never measured) and whether the landing settled. A landing the reader
 *  took over ("gave-up") is settled when its last distance was within the row: the reader's own move is not a miss. */
export function settleRowFields(step: SettleStep, samples: readonly SettleSample[], rowH: number): { dist: number | null; settled: boolean } {
  const last = samples.length ? samples[samples.length - 1] : null;
  if (!last) return { dist: null, settled: false };
  return { dist: Math.round(last.dist), settled: step === "settled" || (step === "gave-up" && withinRow(last.dist, rowH)) };
}
