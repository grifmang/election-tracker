"""Race list (House 435 + Senate regular/special) from Wikipedia's 2026 election articles.
Wikipedia content is CC BY-SA 4.0 - attribution is shown on the site."""
import io, re, pandas as pd
from common import get, save, now_iso, STATES

API = "https://en.wikipedia.org/w/api.php?action=parse&page={}&prop=text|revid&format=json&formatversion=2"
HOUSE = "2026_United_States_House_of_Representatives_elections"
SENATE = "2026_United_States_Senate_elections"

def page(title):
    j = get(API.format(title)).json()["parse"]
    return j["text"], j.get("revid")

def clean(s):
    s = "" if pd.isna(s) else str(s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_cands(cell):
    out = []
    for part in clean(cell).split("▌"):
        part = part.strip()
        if not part: continue
        m = re.match(r"(.+?)\s*\(([^)]+)\)\s*(.*)$", part)
        if m: out.append({"name": m.group(1).strip(), "party": m.group(2).strip(), "note": m.group(3).strip() or None})
        else: out.append({"name": part, "party": None, "note": None})
    return out

def flat(cols):
    return [" / ".join(dict.fromkeys(str(x) for x in c)) if isinstance(c, tuple) else str(c) for c in cols]

def district_key(loc):
    loc = clean(loc)
    m = re.match(r"(.+?)\s+(at-large|\d+)$", loc)
    st = STATES.get(m.group(1))
    n = 0 if m.group(2) == "at-large" else int(m.group(2))
    return st, n, f"{st}-{n:02d}"

def house():
    html, rev = page(HOUSE)
    tables = pd.read_html(io.StringIO(html))
    races = {}
    for t in tables:
        cols = flat(t.columns)
        if not any(c.startswith("Candidates") for c in cols) or not cols[0].startswith("District"): continue
        t.columns = cols
        for _, r in t.iterrows():
            loc = clean(r.iloc[0])
            if not re.match(r"^[A-Z][a-z].* (at-large|\d+)$", loc): continue
            st, n, key = district_key(loc)
            if st is None: continue  # non-voting delegates (AS, GU, ...)
            ccol = [c for c in cols if c.startswith("Candidates")][0]
            d = races.setdefault(key, {"key": key, "state": st, "district": n, "pvi": clean(r.iloc[1]),
                                       "incumbents": [], "status": [], "candidates": parse_cands(r[ccol])})
            inc = {"name": clean(r.iloc[2]), "party": clean(r.iloc[3]), "first_elected": clean(r.iloc[4])}
            if inc not in d["incumbents"]: d["incumbents"].append(inc)
            stt = clean(r.iloc[5])
            if stt and stt not in d["status"]: d["status"].append(stt)
    out = sorted(races.values(), key=lambda x: (x["state"], x["district"]))
    print("house races:", len(out))
    save("races_house.json", {"generated": now_iso(), "source": f"https://en.wikipedia.org/wiki/{HOUSE}", "wikipedia_revid": rev,
                              "license": "CC BY-SA 4.0 (Wikipedia)", "count": len(out), "races": out})

def senate():
    html, rev = page(SENATE)
    tables = pd.read_html(io.StringIO(html))
    races, ratings, calendar = [], {}, {}
    for t in tables:
        cols = flat(t.columns); t.columns = cols
        if cols[0].startswith("Constituency") and any(c.startswith("Ratings") for c in cols):
            for _, r in t.iterrows():
                st = clean(r.iloc[0])
                if st.startswith("Overall"): continue
                ratings[st.replace(" (special)", "") + (" special" if "special" in st else "")] = {
                    re.sub(r"\[.*$", "", re.sub(r"^Ratings / ", "", c)): clean(r[c]) for c in cols if c.startswith("Ratings")}
        elif cols[0] == "State" and any("Poll closing" in c for c in cols):
            for _, r in t.iterrows():
                st = clean(r.iloc[0]); pc = [c for c in cols if "Poll closing" in c][0]
                calendar[st.replace(" (special)", "") + (" special" if "special" in st else "")] = {
                    "primary": clean(r.iloc[2]), "poll_close_et": clean(r[pc])}
        elif cols[0].startswith("Constituency") and any(c.startswith("Candidates") for c in cols):
            ccol = [c for c in cols if c.startswith("Candidates")][0]
            for _, r in t.iterrows():
                stname = clean(r.iloc[0]); special = "Class 3" in stname
                base = re.sub(r"\s*\(.*\)", "", stname)
                st = STATES.get(base)
                if not st: continue
                races.append({"key": f"{st}-S{'-special' if special else ''}", "state": st, "state_name": base,
                              "special": special, "pvi": clean(r.iloc[1]),
                              "incumbent": {"name": clean(r.iloc[2]), "party": clean(r.iloc[3])},
                              "status": clean(r.iloc[6] if not special else r.iloc[5]) if len(cols) > 6 else clean(r.iloc[5]),
                              "candidates": parse_cands(r[ccol])})
    for x in races:
        k = x["state_name"] + (" special" if x["special"] else "")
        x["ratings"] = ratings.get(k, {}); x["calendar"] = calendar.get(k, {})
    races.sort(key=lambda x: (x["state"], x["special"]))
    print("senate races:", len(races), "specials:", sum(x["special"] for x in races))
    save("races_senate.json", {"generated": now_iso(), "source": f"https://en.wikipedia.org/wiki/{SENATE}", "wikipedia_revid": rev,
                               "license": "CC BY-SA 4.0 (Wikipedia)", "count": len(races), "races": races})

if __name__ == "__main__":
    house(); senate()
