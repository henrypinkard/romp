// The lightbox's controls sit at the TOP, in the file viewer's bar (T385, the user 2026-09-12: after opening an image the
// controls should sit above it, consistent with how a file opens). preview.ts has import-time DOM side effects, so
// openLightbox is LIFTED (esbuild's ts loader, the browse-route precedent) and run on a tiny DOM: the order of the
// column's children is read, never inferred from source order.
import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { createRequire } from "node:module";

const requireCjs = createRequire(__filename);
const PREVIEW = fs.readFileSync(path.resolve(process.cwd(), "..", "ui", "webview", "preview.ts"), "utf8");
const CSS = fs.readFileSync(path.resolve(process.cwd(), "..", "ui", "webview", "styles.css"), "utf8");
const ts = (code: string): string => requireCjs("esbuild").transformSync(code, { loader: "ts" }).code;

type El = {
  tag: string; className: string; id: string; children: El[]; parent: El | null; textContent: string; innerHTML: string;
  title: string; attrs: Record<string, string>; dataset: Record<string, string>; type: string; href: string; download: string; src: string; alt: string;
  classList: { add: (...c: string[]) => void; remove: (...c: string[]) => void; contains: (c: string) => boolean };
  appendChild: (c: El) => El; append: (...c: El[]) => void; prepend: (...c: El[]) => void; replaceWith: (n: El) => void; remove: () => void;
  setAttribute: (k: string, v: string) => void; getAttribute: (k: string) => string | null; addEventListener: () => void; querySelector: () => null;
};
function mkEl(tag: string): El {
  const e: El = {
    tag, className: "", id: "", children: [], parent: null, textContent: "", innerHTML: "", title: "", attrs: {}, dataset: {}, type: "", href: "", download: "", src: "", alt: "",
    classList: {
      add: (...c) => { const s = new Set(e.className.split(/\s+/).filter(Boolean)); c.forEach((x) => s.add(x)); e.className = [...s].join(" "); },
      remove: (...c) => { e.className = e.className.split(/\s+/).filter((x) => x && !c.includes(x)).join(" "); },
      contains: (c) => e.className.split(/\s+/).includes(c),
    },
    appendChild: (c) => { e.children.push(c); c.parent = e; return c; },
    append: (...cs) => { cs.forEach((c) => e.appendChild(c)); },
    prepend: (...cs) => { cs.forEach((c) => { c.parent = e; }); e.children.unshift(...cs); },
    replaceWith: (n) => { const p = e.parent!; p.children[p.children.indexOf(e)] = n; n.parent = p; },
    remove: () => { const p = e.parent; if (p) p.children.splice(p.children.indexOf(e), 1); },
    setAttribute: (k, v) => { e.attrs[k] = v; }, getAttribute: (k) => (k in e.attrs ? e.attrs[k] : null),
    addEventListener: () => {}, querySelector: () => null,
  };
  return e;
}
function classes(e: El): string[] { return e.className.split(/\s+/).filter(Boolean); }

type Nav = Array<{ path: string; sid?: string | null; pin?: string }>;
function lift(kind: "img" | "pdf", nav: Nav = [], clipboard = false): { body: El; open: (p: string, sid?: string | null, pin?: string) => void; keys: Array<(ev: { key: string; stopPropagation: () => void; preventDefault: () => void }) => void> } {
  const a = PREVIEW.indexOf("export function openLightbox(path: string, sid?: string | null, pin?: string): void {");
  const b = PREVIEW.indexOf("\n}\n", a);
  assert.ok(a > 0 && b > a, "openLightbox: anchors not found; re-anchor");
  const code = ts(PREVIEW.slice(a, b + 2).replace(/^export /, ""));
  const body = mkEl("body");
  const keys: Array<(ev: { key: string; stopPropagation: () => void; preventDefault: () => void }) => void> = [];
  const document = { createElement: mkEl, getElementById: () => null, body, addEventListener: (_t: string, fn: (ev: unknown) => void) => { keys.push(fn as never); }, removeEventListener: () => {} };
  const H = { kind, nav, clipboard };
  const prelude = `
    const previewKind = (p) => H.kind;
    const fileUrl = (p, sid) => "/file?path=" + encodeURIComponent(p) + "&sid=" + (sid || "");
    const wirePinchZoom = (stage, img) => ({ retarget: () => {} });
    const lightboxNav = H.nav.length ? (() => H.nav) : null;
    const ICON_DOWNLOAD = '<svg data-icon="download"/>', ICON_COPY = '<svg data-icon="copy"/>', ICON_CHECK = '<svg data-icon="check"/>', ICON_CROSS = '<svg data-icon="cross"/>';
    const navigator = H.clipboard ? { clipboard: { write: () => Promise.resolve() } } : {};
    const ClipboardItem = H.clipboard ? function ClipboardItem() {} : undefined;
    const window = { setTimeout: () => 0 };
  `;
  const open = (new Function("H", "document", prelude + code + "\nreturn openLightbox;") as (h: unknown, d: unknown) => (p: string, sid?: string | null, pin?: string) => void)(H, document);
  return { body, open, keys };
}
function column(body: El): El {
  const wrap = body.children[0];
  assert.equal(wrap.id, "romp-lightbox");
  const inner = wrap.children[0];
  assert.ok(classes(inner).includes("romp-lightbox-inner"));
  return inner;
}

test("the bar PRECEDES the picture in the column: controls at the top, the way a file opens", () => {
  const { body, open } = lift("img");
  open("plots/run1.png", "s1");
  const inner = column(body);
  assert.equal(inner.children.length, 2, "the column holds the bar and the picture");
  assert.ok(classes(inner.children[0]).includes("romp-lightbox-bar"), "first child is the bar, got: " + inner.children[0].className);
  assert.ok(classes(inner.children[1]).includes("romp-lightbox-img"), "the picture follows it");
});

test("the pdf kind puts the same bar above its frame", () => {
  const { body, open } = lift("pdf");
  open("notes/spec.pdf", "s1");
  const inner = column(body);
  assert.ok(classes(inner).includes("pdf"));
  assert.ok(classes(inner.children[0]).includes("romp-lightbox-bar"), "first child is the bar");
  assert.ok(classes(inner.children[1]).includes("romp-lightbox-frame"), "the frame follows it");
});

test("the bar wears the file viewer's vocabulary: its row class, a dimmed-directory + basename title, the actions grouped, the close cross alone at the end", () => {
  const { body, open } = lift("img", [], true);
  open("plots/run1.png", "s1");
  const bar = column(body).children[0];
  assert.deepEqual(classes(bar).sort(), ["fileview-bar", "romp-lightbox-bar"], "the row IS the viewer's bar, the lightbox class a hook for placement and the stage's tap rule");
  const [name, acts] = bar.children;
  assert.equal(bar.children.length, 2, "name then actions (no cue for a single picture)");
  assert.ok(classes(name).includes("fileview-name"));
  assert.deepEqual(name.children.map((c) => c.className), ["fileview-dir", "fileview-base"]);
  assert.deepEqual([name.children[0].textContent, name.children[1].textContent], ["plots/", "run1.png"], "only the directory may truncate; the basename identifies the picture");
  assert.equal(name.title, "plots/run1.png");
  assert.ok(classes(acts).includes("fileview-acts"));
  assert.equal(acts.children.length, 2, "one group, then the close");
  const [group, close] = acts.children;
  assert.deepEqual(classes(group).sort(), ["fileview-group", "fileview-group-file"]);
  assert.deepEqual(group.children.map((c) => c.tag), ["a", "button"], "download (an anchor) then copy, in the file group");
  const [dl, cp] = group.children;
  assert.ok(classes(dl).includes("fileview-btn") && classes(dl).includes("fileview-icon") && classes(dl).includes("romp-lightbox-dl"), dl.className);
  assert.ok(dl.innerHTML.includes('data-icon="download"'), "the tray glyph, not a text chip");
  assert.equal(dl.title, "Download");
  assert.ok(classes(cp).includes("fileview-btn") && classes(cp).includes("fileview-icon") && classes(cp).includes("romp-lightbox-copy"), cp.className);
  assert.ok(cp.innerHTML.includes('data-icon="copy"'));
  assert.equal(cp.title, "Copy image");
  assert.deepEqual(classes(close).sort(), ["fileview-btn", "fileview-close", "romp-lightbox-close"]);
  assert.equal(close.textContent, "✕");
  assert.equal(close.title, "Close (Esc)");
});

test("without a clipboard the group holds download alone; the close still ends the bar", () => {
  const { body, open } = lift("img", [], false);
  open("plots/run1.png", "s1");
  const acts = column(body).children[0].children[1];
  assert.deepEqual(acts.children[0].children.map((c) => c.tag), ["a"]);
  assert.ok(classes(acts.children[1]).includes("fileview-close"));
});

test("a sequence puts the position cue beside the title, and an arrow step re-titles the two elements and re-aims the download", () => {
  const nav: Nav = [{ path: "plots/a.png", sid: "s1", pin: "v1" }, { path: "figs/deep/b.jpg", sid: "s1" }, { path: "c.png", sid: "s1" }];
  const { body, open, keys } = lift("img", nav, true);
  open("plots/a.png", "s1", "v1");
  const bar = column(body).children[0];
  assert.equal(bar.children.length, 3, "name, cue, actions");
  const [name, cue, acts] = bar.children;
  assert.ok(classes(cue).includes("romp-lightbox-cue"));
  assert.equal(cue.textContent, "1/3");
  const dl = acts.children[0].children[0];
  assert.ok(dl.href.includes("pin=v1"), "the download aims at the pinned bytes on screen");
  assert.equal(keys.length, 1, "one capture keydown listener");
  keys[0]({ key: "ArrowRight", stopPropagation: () => {}, preventDefault: () => {} });
  assert.deepEqual([name.children[0].textContent, name.children[1].textContent], ["figs/deep/", "b.jpg"], "the step re-titles directory and basename");
  assert.equal(name.title, "figs/deep/b.jpg");
  assert.equal(cue.textContent, "2/3");
  assert.ok(dl.href.includes(encodeURIComponent("figs/deep/b.jpg")) && !dl.href.includes("pin="), "the download follows the step, unpinned when the entry carries no pin");
  assert.equal(dl.download, "b.jpg");
  keys[0]({ key: "ArrowRight", stopPropagation: () => {}, preventDefault: () => {} });
  assert.deepEqual([name.children[0].textContent, name.children[1].textContent], ["", "c.png"], "a bare basename has no directory half");
});

test("styles: the lightbox's own chip rules are gone, the shared bar rules stand, and the bar's tokens are the dark theme's inside the lightbox (the backdrop is dark in both themes)", () => {
  assert.doesNotMatch(CSS, /\.romp-lightbox-close \{/, "the close wears .fileview-btn.fileview-close now");
  assert.doesNotMatch(CSS, /\.romp-lightbox-dl, \.romp-lightbox-copy \{/, "download and copy wear .fileview-btn.fileview-icon now");
  assert.doesNotMatch(CSS, /\.romp-lightbox-name \{/, "the title wears .fileview-name (directory + basename) now");
  assert.match(CSS, /\.romp-lightbox-bar \{ padding: 0 2px 6px; \}/, "the bar's own placement over the backdrop: no side padding, the picture's edges are the column's");
  assert.match(CSS, /\.romp-lightbox-bar \.fileview-name \{ min-width: 0; \}/, "the title never forces the column wider than the picture; the directory truncates");
  assert.match(CSS, /\.romp-lightbox-img \{ [^}]*align-self: center;/, "a bar wider than a small picture never stretches it");
  assert.match(CSS, /#romp-lightbox \{ --fg: #e8e8e8; --dim: #b8b8b8; --accent: #9cd2ff; --accent-fg: #0c1a2e; --accent-wash: rgba\(156, 210, 255, 0\.12\);\s*\n\s*--err: #f48771; --card-border: rgba\(255, 255, 255, 0\.18\); --box-border: rgba\(255, 255, 255, 0\.18\); \}/);
  assert.match(CSS, /\.romp-lightbox-cue \{ flex: 0 0 auto; font-size: 0\.82em; color: var\(--dim\); font-variant-numeric: tabular-nums; \}/, "the cue keeps the house sub scale");
  // the shared rules the bar rides (file-view's, T367): present once, so a control added to one bar dresses in the other
  assert.equal((CSS.match(/^\.fileview-bar \{/gm) || []).length, 1);
  assert.match(CSS, /^\.fileview-btn\.fileview-icon \{/m);
  assert.match(CSS, /^a\.fileview-btn \{ text-decoration: none; display: inline-flex; align-items: center; \}/m, "the download anchor wears the button treatment");
});
