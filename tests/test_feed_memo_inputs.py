#!/usr/bin/env python3
"""The feed memo's input census (T368).

build_feed serves each living session's cards from _feed_memo while _feed_session_key(s, ...) is unchanged, so the
key must contain every input _feed_session_entry reads that can change the entry. This module is the census that
argument rests on, in the shape of tests/test_chat_build_sig_inputs.py: HELPERS classifies every helper the body
calls by name (`_name(`, `jd.name(` and `em.name(` calls in the function's source, comments and strings excluded),
CTX every field the body reads from the build's context dict, and LOCAL the closures defined inside the body.
Each HELPERS or CTX entry is one of:

  sig    an input the key folds, under the named labels (_FEED_MEMO_LABELS; several when the helper reads
         under more than one component); the first label is the one its main read rides;
  pure   a function of inputs already classified (a store the key identifies, identities another helper
         resolved) and nothing else; the note says of what;
  clock  the build's clock, handed to helpers whose clock-derived outputs LEAVE the entry (a placeholder's
         `t` and every card's age tint are stamped per build by the fold): tests/test_feed_session_memo.py's
         clock case pins that two builds apart in time differ in those fields alone.

The test derives the call set from the function's source and requires it to EQUAL the tables' keys, so a helper
added to the body without a classification fails the suite by name (a future read must be labelled), and so does
a stale entry for one removed. Further pins: every `sig` label exists in the key's label tuple; every label in
the tuple is claimed by some read (no dead component); every LOCAL name is a def nested in the body; the label
tuple matches the list the key builder's docstring documents, in order; the miss attribution map covers the
labels plus `cold`. Names, not lines: the tables say what each read is, the key builder's docstring says how each
component is taken. The census enforces ONE level, the helpers the body calls directly; what each reads in turn
is the classification's claim, verified by the differential cases in tests/test_feed_session_memo.py.
"""
import ast
import inspect
import io
import os
import re
import tempfile
import tokenize
import unittest
from romp_load import load_source

HERE = os.path.dirname(os.path.realpath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
os.environ["ROMP_KERNEL_NO_OPEN"] = "1"
os.environ.setdefault("ROMP_SERVE_TOKEN", "test-token-DO-NOT-USE")
# Hermetic state BEFORE the load: the kernel resolves its state root at import time (a bare unittest run
# otherwise reads REAL state); this module only reads source, but the load is the same load.
os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp()
os.environ.pop("ROMP_STATE_DIR", None)
km = load_source("romp_kernel_feed_memo_inputs", os.path.join(BIN, "romp-kernel"))

# ── the helpers the body calls, helper -> (kind, labels or note) ──────────────────────────────────────────
HELPERS = {
    # the transcript (the cache-only parse, the anchors, the api-error tail, the background scans)
    "_api_error": ("sig", ("transcript",)),
    "_atom_prose_chars": ("sig", ("transcript",)),
    "_last_plain_user_turn_t": ("sig", ("transcript",)),
    "_open_turn_progress": ("sig", ("transcript",)),
    "_pure_delegation_top": ("sig", ("transcript",)),
    "_seg_anchors": ("sig", ("transcript",)),
    "_seg_jump": ("sig", ("transcript",)),
    "_seg_key": ("sig", ("transcript",)),
    "_seg_last_text": ("sig", ("transcript",)),
    "_segs_seam": ("sig", ("transcript",)),
    "em.turn_scalar": ("sig", ("transcript",)),
    "jd._prompt_anchor_uuid": ("sig", ("transcript",)),
    "_heal_session_tops": ("sig", ("transcript", "store")),            # the background scan over the store's tops
    "_warm_wanted": ("sig", ("transcript", "parse")),                  # moved since boot, or working: worth a warm
    # the placeholders: their own _parse, the caption gist, the clear set, the current ask
    "_provisional_card": ("sig", ("transcript", "captions", "cleared")),
    "_blocked_placeholder": ("sig", ("transcript", "captions", "ask")),
    "_awaiting_card": ("sig", ("transcript",)),
    # the states log (machine cuts, the retrying-since fold, the awaiting overlay) and the live row
    "_interrupt_suppresses_nudge": ("sig", ("states",)),
    "_session_retrying": ("sig", ("states", "row")),
    "_session_awaiting": ("sig", ("states", "reg", "row", "bg", "watch", "subagents", "peers")),
    # the names registry (own sid, and the peers a card names)
    "_name_color": ("sig", ("names", "peers")),
    "_name_of": ("sig", ("names", "peers")),
    # the goal store (every node and status read of ctx["store"], and the shared loads inside the bg memos)
    "_agent_open_set": ("sig", ("store",)),
    "_all_outstanding_delegated": ("sig", ("store",)),
    "_goal_awaiting_stamp_full": ("sig", ("store",)),
    "_node_log_rows": ("sig", ("store",)),
    "_open_leaves": ("sig", ("store",)),
    "_parked_rows": ("sig", ("store",)),
    "_session_started_face": ("sig", ("store",)),
    "jd._done_since": ("sig", ("store",)),
    "jd.review_boundary": ("sig", ("store",)),
    "_handoff_card_fields": ("sig", ("store", "peers")),
    "_bg_owner_tops": ("sig", ("transcript", "store", "reg", "bg")),
    "_bg_service_descs": ("sig", ("transcript", "store", "bg", "postal")),
    "_awaiting_task_descs": ("sig", ("transcript", "store", "bg")),
    "_bg_live_norm": ("sig", ("bg", "reg", "row", "transcript")),      # the launch ledger, the row's bgTasks
    # the warm-anchor table, the postal log, the nudge records, the flags, the debug rows, the cap offer
    "_node_anchor_uuids": ("sig", ("anchors",)),
    "_peer_answered": ("sig", ("postal",)),
    "_peer_identity": ("sig", ("postal", "peers")),
    "_handoff_peer_identities": ("sig", ("peers",)),
    "jd.load_goals_shared_or_fault": ("sig", ("peers",)),               # an origin sender's store, by the peers deps
    "_auto_nudge_data": ("sig", ("nudge",)),
    "_nudge_times": ("sig", ("nudge",)),
    "_session_flag": ("sig", ("hide",)),
    "_card_warn_rows": ("sig", ("debug",)),
    "_cap_switch_offer": ("sig", ("row", "usage", "auth")),            # authLive, usage.json (recorded), the key on hand
    # pure over classified inputs
    "_awaiting_peer_items": ("pure", "over the peer identities _session_awaiting resolved (peers), nothing else"),
}

# ── the context fields the body reads, field -> (kind, labels or note) ────────────────────────────────────
CTX = {
    "now": ("clock", "handed to the placeholders and the stamp reads; every clock-derived output leaves the entry"),
    "live_map": ("sig", ("row",)),                     # tm = live_map.get(fsid): live, perm_state, since
    "cleared": ("sig", ("cleared",)),                  # `nid in cleared` per top (the session's slice)
    "dbg_rows": ("sig", ("debug",)),
    "wmap": ("sig", ("wait",)),
    "stalls": ("sig", ("stalls",)),
    "jauth_map": ("sig", ("jauth",)),
    "jactive": ("sig", ("jactive",)),
    "ps": ("sig", ("parse", "transcript", "live", "cut", "states")),   # the cache-only, live-merged parse
    "who_working": ("sig", ("downtime", "parse")),     # _session_working over the open turn, suspension-aware
    "interrupting": ("sig", ("interrupting",)),
    "store": ("sig", ("store",)),                      # _feed_goals(fsid), read once in the key
    "closer": ("sig", ("closer", "jactive")),          # the settle gap under the body's gate
}

# closures defined inside the body: pure over its locals, no component
LOCAL = ("_subtree", "_closure_done", "_fsubmax", "_closure_blocked", "_block_check_floor", "_note_peers")

KINDS = {"sig", "pure", "clock"}


def _stripped(src, strings=False):
    """The source with comments removed and, unless `strings`, every string literal replaced by an empty one,
    so a mention of a helper in a comment or a message is not counted as a call (the ctx census keeps the
    literals: the field names are the strings)."""
    toks = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type == tokenize.COMMENT:
            continue
        if t.type == tokenize.STRING and not strings:
            t = t._replace(string='""')
        toks.append(t)
    return tokenize.untokenize(toks)


def _calls_of(src):
    """Every `_name(`, `jd.name(` and `em.name(` call in the stripped source."""
    text = _stripped(src)
    own = set(re.findall(r"(?<![\w.])(_[a-z_0-9]+)\(", text))
    dotted = set("%s.%s" % m for m in re.findall(r"\b(jd|em)\.([a-z_0-9]+)\(", text))
    return own | dotted


def _ctx_reads_of(src):
    return set(re.findall(r'ctx\["([a-z_]+)"\]', _stripped(src, strings=True)))


def _documented_labels():
    """The component list the key builder's docstring documents: the `label:` lines of its Components block, at
    the block's own indent, in order."""
    doc = inspect.cleandoc(km._feed_session_key.__doc__)
    block = doc.split("Components, label:", 1)[1].split("NOT components", 1)[0]
    rows = [(len(m.group(1)), m.group(2)) for m in re.finditer(r"^( +)([a-z]+): ", block, re.M)]
    indent = min(i for i, _ in rows)
    return tuple(lab for i, lab in rows if i == indent)


class Census(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(km._feed_session_entry)
        cls.calls = _calls_of(cls.src) - {"_feed_session_entry"}       # the def line names the function itself
        cls.ctx = _ctx_reads_of(cls.src)

    def test_every_helper_the_body_calls_is_classified_and_nothing_stale_remains(self):
        table = set(HELPERS) | set(LOCAL)
        self.assertEqual(self.calls, table,
                         "a helper _feed_session_entry calls is missing from HELPERS (an unclassified read: label it "
                         "under the key component that covers it, or add the component), or the table names one the "
                         "body no longer calls: %r" % sorted(self.calls ^ table))

    def test_every_context_field_the_body_reads_is_classified(self):
        self.assertEqual(self.ctx, set(CTX), sorted(self.ctx ^ set(CTX)))

    def test_every_entry_has_a_known_kind_and_a_sig_entry_names_labels_of_the_key(self):
        labels = set(km._FEED_MEMO_LABELS)
        for table in (HELPERS, CTX):
            for name, (kind, what) in table.items():
                self.assertIn(kind, KINDS, name)
                if kind == "sig":
                    self.assertIsInstance(what, tuple, name)
                    self.assertTrue(what, "%s: a sig entry names at least one label" % name)
                    for lab in what:
                        self.assertIn(lab, labels, "%s: %r is not a component of _feed_session_key" % (name, lab))
                else:
                    self.assertIsInstance(what, str, "%s: a %s entry carries its note" % (name, kind))

    def test_every_component_of_the_key_is_claimed_by_a_read(self):
        claimed = set()
        for table in (HELPERS, CTX):
            for kind, what in table.values():
                if kind == "sig":
                    claimed.update(what)
        self.assertEqual(claimed, set(km._FEED_MEMO_LABELS),
                         "a key component no read claims is a dead component (or a read lost its label): %r"
                         % sorted(claimed ^ set(km._FEED_MEMO_LABELS)))

    def test_the_local_closures_are_defs_nested_in_the_body(self):
        fn = ast.parse(self.src).body[0]
        nested = {x.name for x in ast.walk(fn) if isinstance(x, ast.FunctionDef) and x is not fn}
        for name in LOCAL:
            self.assertIn(name, nested, "%s is listed as a local closure but the body defines no such def" % name)
        self.assertFalse(set(LOCAL) & set(HELPERS), "a name is a closure or a helper, never both")

    def test_the_helper_names_resolve_in_the_kernel(self):
        for name in HELPERS:
            mod, _, attr = name.rpartition(".")
            owner = getattr(km, mod) if mod else km
            self.assertTrue(callable(getattr(owner, attr, None)), name)


class LabelsAndDocstring(unittest.TestCase):
    def test_the_label_tuple_matches_the_key_builders_documented_component_list_in_order(self):
        self.assertEqual(km._FEED_MEMO_LABELS, _documented_labels(),
                         "the docstring of _feed_session_key lists every component; the tuple must be that list")

    def test_the_labels_are_distinct_and_the_deps_are_labels(self):
        self.assertEqual(len(set(km._FEED_MEMO_LABELS)), len(km._FEED_MEMO_LABELS))
        for dep in km._FEED_MEMO_DEPS:
            self.assertIn(dep, km._FEED_MEMO_LABELS, dep)
        self.assertEqual(km._FEED_MEMO_LABELS[-1], "peers", "the peers dependency closes the tuple")

    def test_the_miss_attribution_map_covers_every_label_and_cold(self):
        self.assertEqual(set(km._FEED_MEMO_STATS["miss_by"]), set(km._FEED_MEMO_LABELS) | {"cold"})
        self.assertEqual(set(km._feed_memo_report()["miss_by"]), set(km._FEED_MEMO_LABELS) | {"cold"})

    def test_the_key_builder_returns_one_value_per_label(self):
        """A key is compared to the labels by position (_feed_memo_miss zips them), so the return statement must
        hand back exactly as many values as there are labels: pinned on the source, since a build needs a world."""
        src = _stripped(inspect.getsource(km._feed_session_key))
        ret = src.rsplit("return (", 1)[1].rsplit(")", 1)[0]
        names = [n.strip() for n in ret.replace("\n", " ").split(",") if n.strip()]
        self.assertEqual(len(names), len(km._FEED_MEMO_LABELS),
                         "the key's return tuple has %d values for %d labels" % (len(names), len(km._FEED_MEMO_LABELS)))

    def test_the_entry_docstring_names_this_pin(self):
        self.assertIn("test_feed_memo_inputs", km._feed_session_entry.__doc__)


if __name__ == "__main__":
    unittest.main()
