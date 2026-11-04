#!/usr/bin/env python3
"""Merge raw X search results into site/data/x_feed.json (credited, linked posts for the
'News desks on X' tab, #news). Each post also gets a deterministic `races` array (see tag_races).

The X fetch can't run in GitHub Actions; it runs from the Grok Bot box via the built-in X read tool
(`search_posts_all`, see QUERY below). Save each raw tool response to a file, then:

    python pipeline/x_feed_write.py /workspace/x_raw.json [more_pages.json ...]

Inputs may be the raw API JSON ({data, includes.users, meta}) or a tool-output file with text
wrapped around that JSON. Posts are stored verbatim (exact text), never edited or paraphrased.
Existing posts in x_feed.json are kept, so the feed accumulates (max 300). Explicit race calls are
extracted into site/data/race_calls.json, which accumulates independently of the post cap. Prints "changed" or "unchanged".
"""
import html, json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "x_feed.json"
MAX_POSTS = 300
CALLS_OUT = ROOT / "site" / "data" / "race_calls.json"
START_TIME = "2026-11-03T22:00:00Z"
# Handles verified via user lookup on 2026-11-03. AP_Politics was dropped (an unrelated 1-post account).
HANDLES = ["AP", "DecisionDeskHQ", "NBCNews", "CBSNews", "ABC", "CNN", "FoxNews", "nytimes", "Reuters", "CookPolitical"]
QUERY = ("(" + " OR ".join("from:" + h for h in HANDLES) + ") "
         '(Senate OR House OR Congress OR congressional OR "balance of power" OR projects OR wins OR reelection OR "re-election") '
         '-Governor -is:retweet -is:reply')
ALLOWED = {h.lower() for h in HANDLES}
# Keep only posts that are about House/Senate/Congress ("White House" alone doesn't count).
RELEVANT = re.compile(r"\b(Senate|House|Congress|congressional|balance of power|Sen\.|Rep\.)", re.I)
NOTE = ("Posts are quoted verbatim from the accounts shown and link to the original on X; race calls are "
        "theirs, not this site's. Official counts above come from the Open America feed.")


# ---------- Race tagging (deterministic; only what the post text literally supports) ----------
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
          "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
          "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
          "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
          "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
          "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
          "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
          "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
          "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
          "WI": "Wisconsin", "WY": "Wyoming"}
SENATE_CTRL, HOUSE_CTRL, OTHER = "Senate control", "House control", "Other / general"
SUFFIX = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
# Longest names first so "West Virginia" wins over "Virginia"; plain regex per state name (no "Alaskans" etc.).
_ST_NAMES = sorted(STATES.items(), key=lambda kv: -len(kv[1]))


def _load_races():
    d = ROOT / "site" / "data"
    sen = json.loads((d / "races_senate.json").read_text())["races"]
    house = json.loads((d / "races_house.json").read_text())["races"]
    return sen, house


def _name_parts(full):
    toks = [t for t in re.sub(r"\(.*?\)", "", full).replace(",", " ").split() if t.lower() not in SUFFIX]
    toks = [t for t in toks if not re.fullmatch(r"[A-Z]\.?", t)]  # drop middle initials
    return (toks[0], toks[-1]) if len(toks) >= 2 else (None, None)


def senate_label(r):
    return f"{r['state']} Senate" + (" (special)" if r.get("special") else "")


def build_index():
    sen, house = _load_races()
    idx = {"sen_by_state": {r["state"]: senate_label(r) for r in sen},
           "house_keys": {r["key"] for r in house},
           "full": {},    # "jon ossoff" -> {labels}
           "last": {}}    # (state, "ossoff") -> {labels}
    def add(label, state, name):
        first, last = _name_parts(name or "")
        if not last or len(last) < 3:
            return
        idx["full"].setdefault(f"{first} {last}".lower(), set()).add(label)
        idx["last"].setdefault((state, last.lower()), set()).add(label)
    for r in sen:
        lab = senate_label(r)
        for c in r.get("candidates", []):  # general-election candidates only (a retiring incumbent isn't in the race)
            add(lab, r["state"], c.get("name"))
    for r in house:
        for c in r.get("candidates", []):
            add(r["key"], r["state"], c.get("name"))
    idx["full_rx"] = {}
    for full, labs in idx["full"].items():
        f, l = full.split(" ", 1)
        idx["full_rx"].setdefault(l.split()[-1], []).append(
            (re.compile(r"\b" + re.escape(f) + r"(?:\s+[\w.'’-]+){0,2}?\s+" + re.escape(l) + r"\b"), labs))
    return idx


def _sentences(text):
    t = re.sub(r"https?://\S+", " ", text)
    for a, b in (("U.S.", "US"), ("Sen.", "Sen"), ("Rep.", "Rep"), ("a.m.", "am"), ("p.m.", "pm"), ("Gov.", "Gov")):
        t = t.replace(a, b)
    return [s for s in re.split(r"[.!?\n]+", t) if s.strip()]


def _states_in(s):
    found, rest = set(), s
    for ab, name in _ST_NAMES:
        if re.search(r"\b" + re.escape(name) + r"(?:'s|’s)?\b(?!\w)", rest):
            found.add(ab); rest = re.sub(re.escape(name), " ", rest)
    # 2-letter codes only in unambiguous forms: "GA US Senate", "FL US House 14", "OH Senate"
    for m in re.finditer(r"\b([A-Z]{2})\s+(?:US\s+)?(?:Senate|House)\b", s):
        if m.group(1) in STATES:
            found.add(m.group(1))
    return found


def tag_races(text, idx):
    tags = []
    post_states = _states_in(text)
    def add(t):
        if t not in tags:
            tags.append(t)
    for s in _sentences(text):
        states = _states_in(s)
        # House districts: "Ohio US House 7", "FL US House 14", "Florida's 13th District", "#KY06", "VA-02"
        for m in re.finditer(r"\b(" + "|".join([n for _, n in _ST_NAMES] + list(STATES)) + r")(?:'s|’s)?\s+(?:US\s+House|House\s+District|Congressional\s+District)\s+(\d{1,2})\b", s):
            ab = next((a for a, n in STATES.items() if n == m.group(1).strip() or a == m.group(1).strip()), None)
            if ab and f"{ab}-{int(m.group(2)):02d}" in idx["house_keys"]:
                add(f"{ab}-{int(m.group(2)):02d}")
        for m in re.finditer(r"\b(" + "|".join(n for _, n in _ST_NAMES) + r")(?:'s|’s)\s+(\d{1,2})(?:st|nd|rd|th)\s+(?:Congressional\s+)?District\b", s):
            ab = next(a for a, n in STATES.items() if n == m.group(1))
            if f"{ab}-{int(m.group(2)):02d}" in idx["house_keys"]:
                add(f"{ab}-{int(m.group(2)):02d}")
        for m in re.finditer(r"(?:#|\b)([A-Z]{2})-?(\d{2})\b", s):
            if f"{m.group(1)}-{m.group(2)}" in idx["house_keys"]:
                add(f"{m.group(1)}-{m.group(2)}")
        # Senate by state: a state named in the same sentence as "Senate"/"Sen", or "#GASen"
        for m in re.finditer(r"#([A-Z]{2})Sen\b", s, re.I):
            lab = idx["sen_by_state"].get(m.group(1).upper())
            if lab: add(lab)
        if re.search(r"\bSen(?:ate|ator)?\b", s) and not re.search(r"\bSenate\s+(?:control|majority)\b|\bcontrol of the (?:US )?Senate\b", s):
            for ab in sorted(states):
                if ab in idx["sen_by_state"]:
                    add(idx["sen_by_state"][ab])
        # Candidates: full first+last name anywhere; a bare last name only right after a title
        # (Rep/Sen/Senator/Congressman/Congresswoman) and with that race's state named in the same sentence
        low = s.lower()
        # first + last, allowing up to two middle names/initials ("Anna Paulina Luna", "Dan S. Sullivan");
        # only names whose last name occurs in the sentence are tested (fast path)
        for w in set(re.findall(r"[\w'’-]+", low)):
          for rx, labs in idx["full_rx"].get(w, ()):
            if rx.search(low):
                # a name shared by candidates in different races (e.g. Mike Rogers, MI Senate / AL-03)
                # only counts for the race(s) whose state the post names
                if len(labs) > 1:
                    labs = {l for l in labs if l[:2] in post_states}
                for l in sorted(labs): add(l)
        for ab in states:
            for w in set(re.findall(r"\b(?:Rep|Sen|Senator|Congressman|Congresswoman)\s+([A-Z][a-z'’-]{2,})\b", s)):
                for l in sorted(idx["last"].get((ab, w.lower()), ())): add(l)
        # Chamber control
        if re.search(r"Balance of Power[^\n]*:\s*Senate|\bSenate\s+(?:control|majority)\b|\bcontrol of the (?:US )?Senate\b", s, re.I):
            add(SENATE_CTRL)
        if re.search(r"Balance of Power[^\n]*:\s*House|\bHouse\s+(?:control|majority)\b|\bcontrol of the (?:US )?House\b", s, re.I):
            add(HOUSE_CTRL)
        if re.search(r"\bcontrol of Congress\b", s, re.I):
            add(SENATE_CTRL); add(HOUSE_CTRL)
    return tags or [OTHER]


# ---------- Race calls (deterministic; only explicit wins/projections for a named general-election candidate) ----------
def _party(p):
    p = (p or "").strip()
    if re.match(r"(?i)^(D|Dem|Democratic|DFL)", p): return "D"
    if re.match(r"(?i)^(R|Rep|Republican)", p): return "R"
    if re.match(r"(?i)^(I|Ind|Independent)", p): return "I"
    return "O"


def _chamber(label):
    return "Senate" if " Senate" in label else "House"


def candidates_by_race():
    sen, house = _load_races()
    out = {}
    for r in sen:
        out[senate_label(r)] = r.get("candidates", [])
    for r in house:
        out[r["key"]] = r.get("candidates", [])
    return out


# "<name> wins / has won / defeats / has defeated / is re-elected / clinches" are declarative calls;
# "<name> will win / will defeat / is projected to win / projected winner" count only when the post is a projection.
DECL = r"(?:has\s+won|wins|has\s+defeated|defeats|defeated|is\s+re-?elected|has\s+been\s+re-?elected|clinches)\b"
PROJ = r"(?:will\s+win|will\s+defeat|is\s+projected\s+to\s+(?:win|defeat)|is\s+(?:the\s+)?projected\s+winner)\b"
PROJ_MARK = re.compile(r"(?i)\bproject(?:s|ed|ion)?\b|#DecisionMade|\brace call\b|\bcalls? the race\b")


def _name_rx(cand):
    first, last = _name_parts(cand.get("name") or "")
    if not last:
        return None
    full = re.escape(first) + r"(?:\s+[A-Z][\w.'’-]*){0,2}?\s+" + re.escape(last)
    return r"(?:" + full + r"|(?<![\w.])" + re.escape(last) + r")" + r"(?:\s+(?:Jr\.?|Sr\.?|II|III|IV))?(?:\s*\([A-Z]{1,3}\))?"


def extract_calls(post, cands):
    """Return [(race_label, candidate)] explicitly called as won by this post."""
    text = post["text"]
    is_proj = bool(PROJ_MARK.search(text))
    out = []
    for race in post.get("races", []):
        if race not in cands:
            continue  # control / other tags never produce calls
        winners = []
        for c in cands[race]:
            rx = _name_rx(c)
            if not rx:
                continue
            pat = rx + r",?\s+(?:" + DECL + (r"|" + PROJ if is_proj else "") + r")"
            pats = [pat, r"(?i:projected winner)[:\s]+" + rx, r"(?i:race call)[:\s]+(?:\S+\s+){0,3}?" + rx]
            if any(re.search(x, text) for x in pats):
                winners.append(c)
        if len(winners) == 1:  # two different winners claimed for one race in one post: ignore as unparseable
            out.append((race, winners[0]))
    return out


def feed_claims():
    """Calls from the Open America results feed's own `called`/`winner` fields (none so far)."""
    out = []
    d = ROOT / "site" / "data"
    try:
        sen = {r["state"]: senate_label(r) for r in _load_races()[0]}
        for fn, keyf in (("results_senate.json", lambda k: sen.get(k)), ("results_house.json", lambda k: k)):
            f = json.loads((d / fn).read_text())
            for k, r in (f.get("races") or {}).items():
                if r.get("called") and r.get("winner") and keyf(k):
                    party = next((c.get("party") for c in r.get("candidates", []) if c.get("name") == r["winner"]), "")
                    out.append({"race": keyf(k), "winner_name": r["winner"], "party": _party(party), "handle": "Open America feed",
                                "post_url": None, "created_at": f.get("as_of") or f.get("generated"), "source": "feed"})
    except Exception as e:
        print(f"warning: feed calls skipped: {e}", file=sys.stderr)
    return out


def write_calls(all_posts):
    """Accumulate claims in race_calls.json (claims survive posts rolling off x_feed.json) and aggregate per race."""
    cands = candidates_by_race()
    old = {}
    if CALLS_OUT.exists():
        try: old = json.loads(CALLS_OUT.read_text())
        except Exception: old = {}
    seen_urls = {p["url"] for p in all_posts}
    # keep old X claims whose post is no longer in view; re-extract claims for posts we still have
    claims = [c for c in old.get("claims", []) if c.get("source") == "x" and c.get("post_url") not in seen_urls]
    for p in all_posts:
        for race, c in extract_calls(p, cands):
            claims.append({"race": race, "winner_name": c["name"], "party": _party(c.get("party")), "handle": p["handle"],
                           "post_url": p["url"], "created_at": p["created_at"], "source": "x"})
    claims += feed_claims()
    claims.sort(key=lambda c: (c["race"], c["created_at"] or "", c["post_url"] or ""))
    by_race = {}
    for c in claims:
        by_race.setdefault(c["race"], []).append(c)
    calls, conflicting = [], []
    for race, cs in sorted(by_race.items()):
        names = sorted({c["winner_name"] for c in cs})
        by = [{"handle": c["handle"], "post_url": c["post_url"], "created_at": c["created_at"]} for c in cs]
        if len(names) == 1:
            calls.append({"race": race, "chamber": _chamber(race), "winner_name": names[0], "party": cs[0]["party"],
                          "status": "called", "called_by": by})
        else:
            conflicting.append({"race": race, "chamber": _chamber(race), "winner_name": None, "party": None, "status": "conflicting",
                                "claimed_winners": [{"winner_name": n, "party": next(c["party"] for c in cs if c["winner_name"] == n),
                                                     "called_by": [{"handle": c["handle"], "post_url": c["post_url"], "created_at": c["created_at"]}
                                                                   for c in cs if c["winner_name"] == n]} for n in names],
                                "called_by": by})
    totals = {}
    for ch in ("Senate", "House"):
        t = {"D": 0, "R": 0, "I": 0, "O": 0}
        for c in calls:
            if c["chamber"] == ch: t[c["party"]] += 1
        totals[ch] = {**t, "called": sum(t.values()), "conflicting": sum(1 for c in conflicting if c["chamber"] == ch)}
    body = {"note": ("Seats counted from explicit race calls/projections in posts by the news-desk accounts on X (and the "
                     "Open America feed's own call field, if it ever reports one). Not official results. A race counts once; "
                     "races where desks name different winners are listed as conflicting and not counted."),
            "totals": totals, "calls": calls, "conflicting": conflicting, "claims": claims}
    old_cmp = {k: v for k, v in old.items() if k != "generated"}
    if old_cmp == body:
        return False
    CALLS_OUT.write_text(json.dumps({"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **body},
                                    indent=1, ensure_ascii=False) + "\n")
    return True


def parse(path):
    t = pathlib.Path(path).read_text(encoding="utf-8")
    i = t.find("{")
    if i < 0:
        return {}
    obj, _ = json.JSONDecoder().raw_decode(t[i:])
    return obj


def posts_from(obj):
    users = {u["id"]: u for u in (obj.get("includes") or {}).get("users", [])}
    for p in obj.get("data") or []:
        u = users.get(p.get("author_id"))
        if not u or u.get("username", "").lower() not in ALLOWED:
            continue
        text = html.unescape(p.get("text") or "")  # API returns &amp; &lt; &gt; entity-encoded; store the literal text
        if not RELEVANT.search(re.sub(r"White House", "", text, flags=re.I)):
            continue
        if p.get("created_at", "") < START_TIME.replace("Z", ".000Z"):
            continue
        h = u["username"]
        yield {"id": str(p["id"]), "url": f"https://x.com/{h}/status/{p['id']}", "author_name": u.get("name") or h,
               "handle": h, "text": text, "created_at": p["created_at"]}


def main(paths):
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text())
        except Exception:
            old = {}
    old_posts = json.loads(json.dumps(old.get("posts", [])))  # snapshot: posts are re-tagged in place below
    by_id = {p["id"]: p for p in json.loads(json.dumps(old.get("posts", [])))}
    new = 0
    for path in paths:
        for p in posts_from(parse(path)):
            new += p["id"] not in by_id
            by_id[p["id"]] = p
    every = sorted(by_id.values(), key=lambda p: (p["created_at"], int(p["id"])), reverse=True)
    try:
        idx = build_index()
        for p in every:  # (re-)tag every post, so tagging rules/race lists apply to the whole feed
            p["races"] = tag_races(p["text"], idx)
    except Exception as e:  # never block the feed on tagging
        print(f"warning: race tagging skipped: {e}", file=sys.stderr)
    try:  # calls are extracted from every post seen this run (incl. ones past the cap) and accumulate in race_calls.json
        print("race_calls.json " + ("changed" if write_calls(every) else "unchanged"))
    except Exception as e:
        print(f"warning: race calls skipped: {e}", file=sys.stderr)
    posts = every[:MAX_POSTS]
    if old_posts == posts:
        print("unchanged"); return
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "note": NOTE, "query": QUERY, "accounts": HANDLES, "posts": posts}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"changed: {new} new, {len(posts)} total")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
