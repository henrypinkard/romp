// A deep-link landing SETTLES before it is called good (T386 stage 1, the user 2026-09-12: a card click deep into
// history did not land the first time; the landing audit had filed the first landing as exact). The landing write puts
// the target's top at the viewport top; what follows in the next second can move it (the transcript's own boxes
// sizing in, a rewindow write of the virtualiser, a rebuild's placement), and until now nothing measured where the
// target ended up. This module is the rule; render.ts feeds it the target's distance from the viewport top as the
// page's own events arrive (the target or the view resizing, another writer moving #content, two bounded timers) and
// acts on the step: re-land, or finish and file the landing row with the measured distance. Pure, so node executes it.

/** The settle window: the span landOn already re-aligned within for the boxes above the transcript. */
export const SETTLE_MS = 1200;
/** Consecutive samples within the row before the landing counts as settled ahead of the window's end. */
export const SETTLE_QUIET = 2;

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
 *  - SETTLE_QUIET consecutive samples within the row settle the landing early ("settled");
 *  - the window's end settles on the last sample ("settled" within the row, else "unsettled"), so a landing that never
 *    quietens is still filed, with its distance, rather than held forever;
 *  - otherwise "wait". */
export function settleStep(samples: readonly SettleSample[], rowH: number, gesture: boolean, now: number): SettleStep {
  if (gesture) return "gave-up";
  const last = samples.length ? samples[samples.length - 1] : null;
  if (last && !withinRow(last.dist, rowH) && now < SETTLE_MS) return "realign";
  if (samples.length >= SETTLE_QUIET) {
    let quiet = true;
    for (let i = samples.length - SETTLE_QUIET; i < samples.length; i++) if (!withinRow(samples[i].dist, rowH)) quiet = false;
    if (quiet) return "settled";
  }
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
