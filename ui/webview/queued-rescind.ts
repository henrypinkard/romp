// A queued message RESCINDED to the composer (T373, the user 2026-09-12): the queued bubble's edit does not edit in
// place; it pulls the message back into the message box, where it can be changed and sent again, and takes it out of
// the queue. What comes back is what went out: the typed words, the quote citations as chips again (the outgoing body
// wrote them as quote sections ahead of the text, quoteReplyBody), and the attachments as chips again (the outgoing
// text carried their paths as a trailing line, quoted when they contain spaces). Pure: the DOM half lives in
// render.ts and executes this.

export interface RescindCite { quote: string; src?: string }
export interface RescindedState { text: string; cites: RescindCite[]; files: string[] }

const LEAD_CONVERSATION = "Replying to this part of the conversation:";
const LEAD_CODE = /^Replying to this highlighted code \((.+)\):$/;
const MAX_SECTIONS = 64;   // a body carries at most a strip's worth of citations; the parse is bounded by it

/** The inverse of quoteReplyBody: leading quote sections back into citations, the rest is the text. A body that
 *  starts with no quote section is text alone. */
export function splitQuoteReplyBody(body: string): { cites: RescindCite[]; text: string } {
  const cites: RescindCite[] = [];
  let rest = body;
  for (let n = 0; n < MAX_SECTIONS; n++) {
    const lines = rest.split("\n");
    const lead = lines[0] || "";
    const code = LEAD_CODE.exec(lead);
    if (lead !== LEAD_CONVERSATION && !code) break;
    let i = 1;
    const q: string[] = [];
    while (i < lines.length && (lines[i].startsWith("> ") || lines[i] === ">")) { q.push(lines[i] === ">" ? "" : lines[i].slice(2)); i++; }
    if (!q.length) break;
    const cite: RescindCite = { quote: q.join("\n") };
    if (code) cite.src = code[1];
    cites.push(cite);
    while (i < lines.length && lines[i] === "") i++;   // the blank line between sections, or before the text
    rest = lines.slice(i).join("\n");
  }
  return { cites, text: rest };
}

/** Whether a token of the trailing line reads as a path: a slash inside it, or a dotted extension at its end. */
function pathLike(tok: string): boolean {
  return tok.includes("/") || /\.[A-Za-z0-9]{1,8}$/.test(tok);
}

/** The trailing paths line off the text when the send wrote one: `known` (the page's own pending entry's attachment
 *  paths) names them exactly; without it the last line is taken only when EVERY token of it reads as a path (quoted
 *  when it contains spaces), so a last line of prose stays prose; a message that is one bare name alone is words. */
export function splitTrailingPaths(text: string, known?: readonly string[] | null): { text: string; files: string[] } {
  const lines = text.split("\n");
  const last = lines[lines.length - 1] || "";
  if (known && known.length) {
    const want = known.map((p) => (/\s/.test(p) ? '"' + p + '"' : p)).join(" ");
    if (last === want) return { text: lines.slice(0, -1).join("\n"), files: [...known] };
    return { text, files: [] };
  }
  const toks = last.match(/"[^"]+"|\S+/g) || [];
  if (!toks.length) return { text, files: [] };
  const paths = toks.map((tk) => (tk.startsWith('"') && tk.endsWith('"') ? tk.slice(1, -1) : tk));
  if (!paths.every(pathLike)) return { text, files: [] };
  if (lines.length < 2 && !paths.every((p) => p.includes("/"))) return { text, files: [] };
  return { text: lines.slice(0, -1).join("\n"), files: paths };
}

/** The composer state a rescinded message comes back as: text, quote citations, attachment paths. */
export function rescindedComposerState(md: string, known?: readonly string[] | null): RescindedState {
  const { text: body, files } = splitTrailingPaths(md, known);
  const { cites, text } = splitQuoteReplyBody(body);
  return { text, cites, files };
}
