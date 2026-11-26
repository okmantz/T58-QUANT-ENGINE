"""Coach answer engine: deterministic retrieval over app.coach.knowledge. No AI, no network.

answer(question, page="") -> {"reply": str, "links": [{"label","href"}], "followups": [{"id","label"}], "kind": str, "matched": id|None}
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

from app.coach.knowledge import CATEGORIES, ENTRIES, GREETINGS, PAGES, THANKS

STOP = set(
    "a an the is are was were am do does did i me my mine we our you your it its this that these those to of in on for and or but with be been "
    "how what where when which who why should would could can will shall about please there get got just so if as at by from into than then "
    "some any also really very tell show want need like let us".split()
)
SYN = [
    (r"\bback[- ]?test(ing|s|ed)?\b", "backtest"), (r"\bwalk[- ]forward\b", "walk forward"), (r"\bout[- ]of[- ]sample\b", "out of sample"),
    (r"\bin[- ]sample\b", "in sample"), (r"\br[- ]multiples?\b", "r multiple"), (r"\bdd\b", "drawdown"), (r"\bevals?\b", "evaluation"),
    (r"\bevaluations\b", "evaluation"), (r"\bbt\b", "backtest"), (r"\bsl\b", "stop loss"), (r"\btp\b", "take profit"), (r"\bpf\b", "profit factor"),
    (r"\boptimis", "optimiz"), (r"\bstrategies\b", "strategy"), (r"\bstrats?\b", "strategy"), (r"\bpropfirms?\b", "prop firm"), (r"\bt-?58\b", "t58"),
    (r"\bsign ?in\b", "login"), (r"\blog ?in\b", "login"), (r"\bset ?up\b", "setup"), (r"\bconfigur\w*", "configure"), (r"\bemails?\b", "email"),
    (r"\bmonte[- ]carlo\b", "monte carlo"), (r"\bun-?subscribe\b", "unsubscribe"), (r"\bopt[- ]?out\b", "opt out"), (r"\bcan'?t\b", "cannot"),
    (r"\bdoesn'?t\b", "does not"), (r"\bwon'?t\b", "will not"),
]


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and re.search(r"(ss|x|ch|sh)es$", w):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def _norm(text: str) -> str:
    t = (text or "").lower().replace("&", " and ")
    for pat, rep in SYN:
        t = re.sub(pat, rep, t)
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def _toks(text: str) -> Tuple[List[str], List[str]]:
    raw = [_stem(w) for w in _norm(text).split() if w]
    filt = [w for w in raw if w not in {_stem(s) for s in STOP} and len(w) > 1]
    return raw, filt


@lru_cache(maxsize=1)
def _index():
    idx = []
    for e in ENTRIES:
        phrases = []
        for p in e["kw"]:
            raw, filt = _toks(p)
            use = filt or raw
            if use:
                phrases.append((set(use), " ".join(raw), bool(filt)))
        title_set = set(_toks(e["title"])[1])
        body_set = set(_toks(e["answer"])[1])
        idx.append((e, phrases, title_set, body_set))
    return idx


def _score(q_raw: List[str], q_filt: List[str]) -> List[Tuple[float, dict]]:
    qset, qraw_set, qjoin = set(q_filt), set(q_raw), " ".join(q_raw)
    first = q_raw[0] if q_raw else ""
    out = []
    for e, phrases, title_set, body_set in _index():
        s = 0.0
        for pset, pjoin, has_filt in phrases:
            ok = pset <= qset if has_filt else pset <= qraw_set
            if not ok:
                continue
            w = 2.5 if len(pset) == 1 else 4.0 * len(pset)
            if pjoin and (" " + pjoin + " ") in (" " + qjoin + " "):
                w += 3.0
            s += w
        s += 1.2 * len(qset & title_set)
        s += min(1.5, 0.12 * len(qset & body_set))
        if first in ("where", "find") and e["cat"] == "app":
            s += 1.5
        if first in ("how",) and e["cat"] in ("flow", "setup", "dev"):
            s += 1.0
        if first in ("what", "define", "explain") and e["cat"] == "concept":
            s += 1.0
        out.append((s, e))
    out.sort(key=lambda x: -x[0])
    return out


def _links(e) -> List[dict]:
    return [{"label": a, "href": b} for a, b in e.get("links", [])]


def _follow(e) -> List[dict]:
    by = {x["id"]: x for x in ENTRIES}
    return [{"id": r, "label": by[r]["title"]} for r in e.get("related", []) if r in by][:4]


def _page_info(page: str):
    page = (page or "").split("?")[0].rstrip("/") or "/"
    best = None
    for k in PAGES:
        if page == k or page.startswith(k + "/"):
            if best is None or len(k) > len(best):
                best = k
    return PAGES.get(best) if best else None


def _starters() -> List[dict]:
    ids = ["next_step", "workflow", "where_data", "overfitting", "buy_challenge", "weekly_digest"]
    by = {x["id"]: x for x in ENTRIES}
    return [{"id": i, "label": by[i]["title"]} for i in ids if i in by]


def topics() -> List[dict]:
    """Browse list: categories with their questions (used for the 'Browse topics' chips)."""
    out = []
    for key, label in CATEGORIES:
        out.append({"cat": key, "label": label, "items": [{"id": e["id"], "label": e["title"]} for e in ENTRIES if e["cat"] == key]})
    return out


def entry_reply(entry_id: str, page: str = "") -> Optional[dict]:
    for e in ENTRIES:
        if e["id"] == entry_id:
            return _wrap(e, page, "entry")
    return None


def _wrap(e: dict, page: str, kind: str, extra: str = "") -> dict:
    text = e["answer"]
    info = _page_info(page)
    if e["id"] == "next_step" and info:
        text = "You are on {0}, which is {1}\n\nRight here: {2}\n\n".format(info[0], info[1], info[2]) + text
    if extra:
        text += "\n\n" + extra
    return {"reply": text, "links": _links(e), "followups": _follow(e), "kind": kind, "matched": e["id"]}


def answer(question: str, page: str = "") -> dict:
    q = (question or "").strip()
    raw, filt = _toks(q)
    joined = " ".join(raw)
    if not raw:
        return {"reply": "Ask me anything about the app, trading or strategy development.", "links": [], "followups": _starters(), "kind": "empty", "matched": None}
    if len(raw) <= 3 and any(joined.startswith(_stem(g)) for g in GREETINGS):
        return {"reply": "Hi! I'm Coach. Ask me where to find something, how to set it up, what to do next, or how a trading idea works.", "links": [], "followups": _starters(), "kind": "greeting", "matched": None}
    if len(raw) <= 4 and any(t in joined for t in (_stem(x) for x in THANKS)):
        return {"reply": "Any time. Ask me anything else, or open the First Payout Mission to see your next step.", "links": [{"label": "First Payout Mission", "href": "/mission"}], "followups": _starters()[:3], "kind": "thanks", "matched": None}
    info = _page_info(page)
    if info and re.search(r"\b(this page|where am i|what is this|what does this)\b", _norm(q)) or (info and joined in ("what is this", "where am i")):
        reply = "{0}: {1}\n\nWhat to do here: {2}".format(info[0], info[1][0].upper() + info[1][1:], info[2])
        return {"reply": reply, "links": [], "followups": _starters()[:3], "kind": "page", "matched": None}
    ranked = _score(raw, filt)
    top_s, top = ranked[0]
    if top_s >= 4.0:
        extra = ""
        if len(ranked) > 1 and ranked[1][0] >= top_s * 0.75 and ranked[1][0] >= 4.0:
            second = ranked[1][1]
            extra = "You might also mean: " + second["title"]
        res = _wrap(top, page, "answer")
        if extra:
            res["followups"] = ([{"id": ranked[1][1]["id"], "label": ranked[1][1]["title"]}] + [f for f in res["followups"] if f["id"] != ranked[1][1]["id"]])[:4]
        return res
    near = [e for s, e in ranked[:3] if s >= 1.5]
    if near:
        return {"reply": "I am not sure I have that exactly. Did you mean one of these? Tap one, or rephrase with a few key words (for example 'import data', 'drawdown', 'weekly email').",
                "links": [], "followups": [{"id": e["id"], "label": e["title"]} for e in near], "kind": "suggest", "matched": None}
    return {"reply": "I could not find that in what I know. I can help with the app (where things are, how to set them up), strategy development and trading concepts, prop firms and troubleshooting. Try one of these:",
            "links": [{"label": "User Manual", "href": "/user-manual"}, {"label": "Help and Support", "href": "/support"}], "followups": _starters(), "kind": "fallback", "matched": None}
