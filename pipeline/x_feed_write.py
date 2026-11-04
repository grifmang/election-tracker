#!/usr/bin/env python3
"""Merge raw X search results into site/data/x_feed.json (credited, linked posts for the Live results tab).

The X fetch can't run in GitHub Actions; it runs from the Grok Bot box via the built-in X read tool
(`search_posts_all`, see QUERY below). Save each raw tool response to a file, then:

    python pipeline/x_feed_write.py /workspace/x_raw.json [more_pages.json ...]

Inputs may be the raw API JSON ({data, includes.users, meta}) or a tool-output file with text
wrapped around that JSON. Posts are stored verbatim (exact text), never edited or paraphrased.
Existing posts in x_feed.json are kept, so the feed accumulates. Prints "changed" or "unchanged".
"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "x_feed.json"
MAX_POSTS = 60
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
        text = p.get("text") or ""
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
    by_id = {p["id"]: p for p in old.get("posts", [])}
    new = 0
    for path in paths:
        for p in posts_from(parse(path)):
            new += p["id"] not in by_id
            by_id[p["id"]] = p
    posts = sorted(by_id.values(), key=lambda p: (p["created_at"], int(p["id"])), reverse=True)[:MAX_POSTS]
    if old.get("posts") == posts:
        print("unchanged"); return
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "note": NOTE, "query": QUERY, "accounts": HANDLES, "posts": posts}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"changed: {new} new, {len(posts)} total")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
