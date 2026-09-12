// The settings panel in TABS (T379, the user 2026-09-12): the settings grouped by the surface they belong to, seven pills
// under the title, one pane each, every existing key kept; the tab-widgets gear on the chat strip opens the Tabs tab,
// whose rows are the registered widgets (a live demo, a sliding switch, the widget's options); the last tab used is
// remembered per browser. gear.js builds its DOM from a markup string, so the inventory is read off that string (each
// control's id inside exactly one pane) and the behaviour pinned at the source; tests/test_tab_widgets_browser.py drives
// the served page.
import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";

const UI = path.resolve(process.cwd(), "..", "ui", "webview");
const GEAR = fs.readFileSync(path.join(UI, "gear.js"), "utf8");
const GEAR_CSS = fs.readFileSync(path.join(UI, "gear.css"), "utf8");
const RENDER = fs.readFileSync(path.join(UI, "render.ts"), "utf8");
const KERNEL = fs.readFileSync(path.resolve(process.cwd(), "..", "kernel", "kernel.py"), "utf8");

const TABS = ["chat", "tabs", "feed", "sessions", "automatic", "appearance", "system"];
// the panes, cut from the markup string by their openers (each pane opens with the literal below and the next pane's opener ends it)
function panes(): Record<string, string> {
  const out: Record<string, string> = {};
  const opener = (k: string) => `'<div class=rs-pane data-pane=${k} hidden>' +`;
  for (let i = 0; i < TABS.length; i++) {
    const a = GEAR.indexOf(opener(TABS[i]));
    const b = i + 1 < TABS.length ? GEAR.indexOf(opener(TABS[i + 1])) : GEAR.indexOf("'<div id=rs-login-modal hidden>' +");
    assert.ok(a > 0 && b > a, "pane markers for " + TABS[i]);
    out[TABS[i]] = GEAR.slice(a, b);
  }
  return out;
}

test("seven tabs, in the approved order, from ONE list the pills, the panes and selectTab read", () => {
  assert.match(GEAR, /^var RS_TABS = \[\['chat', 'Chat'\], \['tabs', 'Tabs'\], \['feed', 'Feed'\], \['sessions', 'Sessions'\], \['automatic', 'Automatic'\], \['appearance', 'Appearance'\], \['system', 'System'\]\];/m);
  assert.match(GEAR, /'<div class=rs-tabs id=rs-tabs role=tablist>' \+ RS_TABS\.map\(function \(t\) \{ return '<button class=rs-tab type=button role=tab data-tab=' \+ t\[0\] \+ ' aria-selected=false>' \+ t\[1\] \+ '<\/button>'; \}\)\.join\(''\) \+ '<\/div>' \+/);
  const ps = panes();
  assert.deepEqual(Object.keys(ps), TABS, "one pane per tab, in the tab order");
  assert.ok(GEAR.indexOf("id=rs-tabs") < GEAR.indexOf("data-pane=chat"), "the pills come before the first pane");
});

test("every existing control keeps its id and sits in exactly one pane, by the approved grouping", () => {
  const ps = panes();
  const where: Record<string, string[]> = {
    chat: ["rs-compact", "rs-dense", "rs-badge", "rs-branch", "rs-filelink", "rs-filesctl", "rs-chatscheme", "rs-cmtmodel", "rs-cmteffort", "rs-cmtfast"],
    tabs: ["rs-widgets", "rs-striprows"],
    feed: ["rs-feedcollapsed", "rs-judges-index", "rs-judges-triage"],
    sessions: ["rs-defaultdir", "rs-backend", "rs-fileedit", "rs-panes-sec", "rs-pane-timeline", "rs-pane-fleet", "rs-pane-feed", "rs-activeonly", "rs-collapsegaps"],
    automatic: ["rs-autonudge", "rs-suggestcompact", "rs-conserve", "rs-thinksum", "rs-judgemodel", "rs-judgefast", "rs-judgeeffort", "rs-distillmodel", "rs-distillfast", "rs-distilleffort", "rs-indexmodel", "rs-indexfast", "rs-indexeffort", "rs-judgeconc"],
    appearance: ["rs-theme", "rs-cmap", "rs-pal"],
    system: ["rs-billing", "rs-login-acct", "rs-updates", "ra-open", "rs-log-open", "rsver"],
  };
  for (const [pane, ids] of Object.entries(where)) {
    for (const id of ids) {
      const homes = TABS.filter((t) => new RegExp("id=" + id + "\\b").test(ps[t]));
      assert.deepEqual(homes, [pane], id + " lives in " + pane + " and nowhere else (found in: " + homes.join(",") + ")");
    }
  }
  // the keyboard-shortcuts rows ride the SHORTCUT_ROWS variable, concatenated into the System pane
  assert.match(ps.system, /\+ SHORTCUT_ROWS \+/);
  assert.match(GEAR, /^var SHORTCUT_ROWS =\s*\n\s*'<div class=rs-key id=rs-keys-web hidden>/m);
  for (const t of TABS.filter((x) => x !== "system")) assert.doesNotMatch(ps[t], /SHORTCUT_ROWS/, t + " holds no shortcut rows");
  // the old Context gauge row is gone: its WHEN is the Context bar widget's option on the Tabs tab
  assert.doesNotMatch(GEAR, /id=rs-tabctx\b/);
  assert.doesNotMatch(GEAR, /Context gauge in tabs/);
  // section sub-heads: the first of each pane wears rs-sec-first (no rule above it), and every pane has one
  for (const t of TABS) assert.match(ps[t], /<div class='rs-sec rs-sec-first'>/, t + " opens with a first section head");
});

test("selectTab shows one pane, marks its pill, remembers it per browser; openSettings takes a tab and an open panel switches", () => {
  assert.match(GEAR, /var TAB_KEY = 'romp:settingsTab';/);
  assert.match(GEAR, /function selectTab\(t\) \{\s*\n\s*t = knownTab\(t\) \|\| knownTab\(\(function \(\) \{ try \{ return localStorage\.getItem\(TAB_KEY\); \} catch \(e\) \{ return null; \} \}\)\(\)\) \|\| 'chat';/,
    "the named tab, else the remembered one, else Chat");
  assert.match(GEAR, /b\.classList\.toggle\('on', on\); b\.setAttribute\('aria-selected', on \? 'true' : 'false'\);/);
  assert.match(GEAR, /pn\.hidden = pn\.getAttribute\('data-pane'\) !== t;/);
  assert.match(GEAR, /try \{ localStorage\.setItem\(TAB_KEY, t\); \} catch \(e\) \{\}/);
  assert.match(GEAR, /function openSettings\(tab\) \{\s*\n\s*if \(!p\.hidden\) \{ if \(knownTab\(tab\)\) \{ selectTab\(tab\); return; \} closeSettings\(\); return; \}/,
    "a named tab on an open panel switches to it; a bare ask still toggles");
  assert.match(GEAR, /if \(e\.data && e\.data\.romp === 'openSettings'\) openSettings\(typeof e\.data\.tab === 'string' \? e\.data\.tab : undefined\);/, "the tab rides the message");
  assert.match(GEAR_CSS, /#rsettings \.rs-pane\[hidden\] \{ display: none; \}/, "a hidden pane is out of the flow (the [hidden] rule the author display would beat)");
  assert.match(GEAR_CSS, /#rsettings \.rs-tab\.on \{ color: var\(--accent, #9cd2ff\); border-color: var\(--accent, #9cd2ff\); background: var\(--accent-wash, rgba\(156, 210, 255, 0\.12\)\); font-weight: 600; \}/);
});

test("the Tabs tab's widget rows come from the strip's own module: built once, painted in place, a sliding switch, house pickers for the options", () => {
  assert.match(GEAR, /var TW = require\('\.\/tab-widgets\.ts'\);/);
  assert.match(GEAR, /function buildWidgets\(\) \{\s*\n\s*if \(!wHost \|\| wHost\.children\.length\) return;\s*\n\s*TW\.tabWidgets\(\)\.forEach\(function \(w\) \{/, "one row per registered widget, built once");
  assert.match(GEAR, /sw\.className = 'rs-switch'; sw\.setAttribute\('role', 'switch'\);/, "the sliding toggle (the user's pick), a switch to the accessibility tree");
  assert.match(GEAR, /prefs\.on\[w\.id\] = !TW\.widgetOn\(prefs, w\); saveWidgets\(prefs\);/, "the switch flips the widget's own flag");
  assert.match(GEAR, /var drop = housePick\(wrap, 'wopt-' \+ w\.id \+ '-' \+ o\.key, widgetOptRowHTML,/, "an option is the panel's house picker");
  assert.match(GEAR, /var node = TW\.renderWidgetDemo\(w, prefs\);/, "the live demo is the widget's OWN render over the demo status");
  assert.match(GEAR, /if \(w\.slot === 'before'\) \{ if \(node\) tab\.appendChild\(node\); tab\.appendChild\(label\); \}\s*\n\s*else if \(w\.slot === 'after'\) \{ tab\.appendChild\(label\); if \(node\) tab\.appendChild\(node\); \}/, "placed where the strip puts it");
  assert.match(GEAR, /r\.sw\.classList\.toggle\('on', on\); r\.sw\.setAttribute\('aria-checked', on \? 'true' : 'false'\);/);
  assert.match(GEAR, /r\.demo\.replaceChildren\(tab\);/, "the demo is re-filled in place: the row's controls are never rebuilt (click-safe)");
  assert.match(GEAR, /function saveWidgets\(prefs\) \{ var s = load\(\); s\.tabWidgets = prefs; s\.tabCtx = TW\.tabCtxOfPrefs\(prefs\); save\(s\); paintWidgets\(\); \}/, "the prefs and the tabCtx mirror, through the one save()");
  assert.equal((GEAR.match(/tabWidgets: \{ on: \{\}, order: \[\], opts: \{\} \}/g) || []).length, 2, "the gear's load() defaults carry the key in both literals, so a whole-object save never drops it");
  assert.match(GEAR_CSS, /#rsettings \.rs-switch\.on::after \{ left: 18px;/, "the knob slides");
  assert.match(GEAR_CSS, /#rsettings \.rs-widget \{ display: grid; grid-template-columns: 96px 1fr auto auto;/);
  assert.match(GEAR_CSS, /#rsettings \.rs-widget-demo \.tab-dot \{ flex: 0 0 auto; width: 7px; height: 7px; border-radius: 50%; background: var\(--st-working-bg, #e0b020\); \}/, "the demo wears the strip's vocabulary in this sheet's fallbacks");
});

test("the strip's gear glyph opens the Tabs tab through the shell (or this window's own gear), and the shell relays the tab", () => {
  assert.match(RENDER, /function openSettingsOn\(tab: string\): void \{\s*\n\s*const m = \{ romp: "openSettings", tab \};\s*\n\s*if \(inRompShell\(\)\) \{ try \{ window\.parent\.postMessage\(m, "\*"\); \} catch \{[^}]*\} return; \}\s*\n\s*window\.postMessage\(m, "\*"\);/);
  assert.match(RENDER, /if \(\(window as any\)\.__rompShowStrip \|\| inRompShell\(\)\) \{\s*\n\s*const gear = el\("button", "tab-widgets-gear"\) as HTMLButtonElement;/, "the glyph only where a gear can be reached: an honest absence elsewhere");
  assert.match(RENDER, /gear\.addEventListener\("click", \(e\) => \{ e\.stopPropagation\(\); openSettingsOn\("tabs"\); \}\);/);
  assert.ok(RENDER.indexOf('el("button", "tab-widgets-gear")') > RENDER.indexOf("tagBox.appendChild(tagChipsHost);") && RENDER.indexOf('el("button", "tab-widgets-gear")') < RENDER.indexOf("bar.appendChild(tagBox);"), "inside the tag box, so it takes no extra height");
  assert.match(KERNEL, /window\.__rompOpenSettings=function\(tab\)\{var f=document\.getElementById\('f-settings'\);if\(!f\)return;/);
  assert.match(KERNEL, /f\.contentWindow\.postMessage\(typeof tab==='string'&&tab\?\{romp:'openSettings',tab:tab\}:\{romp:'openSettings'\},'\*'\);/, "the shell forwards the tab into the settings iframe; a bare ask stays bare");
  assert.match(KERNEL, /if\(m\.romp==='openSettings'\)window\.__rompOpenSettings\(m\.tab\);/, "a pane's ask carries its tab through");
});
