"""Early / absentee / mail vote from the UF Election Lab 2026 tracker (Dr. Michael McDonald).
State totals: /data-downloads/earlyvote/2026/US.csv ; district files: <ST>_cd.csv (only some states).
Numbers are passed through as published - no estimates."""
import io, re, os, json, pandas as pd, requests
from common import get, save, now_iso, ABBR2NAME, STATES, DATA

HERE = os.path.dirname(os.path.abspath(__file__))
LINKS = json.load(open(os.path.join(HERE, "source_links.json")))
UF_STATE = "https://election.lab.ufl.edu/early-vote/2026-early-voting/2026-general-election-early-vote-{}/"

def _prev_uf_urls():
    try:
        return {x["state"]: x.get("uf_state_url") for x in json.load(open(os.path.join(DATA, "early_vote_states.json")))["states"]}
    except Exception:
        return {}

def uf_state_url(name, prev):
    """UF per-state page (same slug rule as UF's own JS). Only kept if it answers 200; on network error keep last known value."""
    u = UF_STATE.format(re.sub(r"(^-+|-+$)", "", re.sub(r"[^a-z0-9]+", "-", name.lower())))
    try:
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0 ElectionTrackerPrototype/0.1"}, timeout=30)
        return u if r.status_code == 200 else None
    except requests.RequestException:
        return prev

def source_fields(st, raw):
    """Split UF's data_source (sometimes a URL, sometimes just an agency name) into link + label."""
    raw = None if raw is None or (isinstance(raw, float) and pd.isna(raw)) else str(raw).strip()
    if raw in LINKS["placeholder_values"]: raw = None
    ov = LINKS["overrides"].get(st)
    if ov: return ov["url"], raw if raw and not raw.startswith("http") else None, raw
    if raw and re.match(r"^https?://", raw): return raw, None, raw
    return None, raw, raw

BASE = "https://election.lab.ufl.edu/data-downloads/earlyvote/2026"
PAGE = "https://election.lab.ufl.edu/early-vote/2026-early-voting/"
KEEP = ["request_all", "accept_all", "inperson_all", "voted_all",
        "request_dem", "request_rep", "request_none", "accept_dem", "accept_rep", "accept_none",
        "inperson_dem", "inperson_rep", "inperson_none", "voted_dem", "voted_rep", "voted_none"]

def num(v):
    try:
        if pd.isna(v): return None
        return int(float(v))
    except (TypeError, ValueError):
        return None

def states():
    df = pd.read_csv(io.StringIO(get(f"{BASE}/US.csv").text))
    out, prev = [], _prev_uf_urls()
    for _, r in df.iterrows():
        link, label, raw = source_fields(r["state_abbv"], r["data_source"])
        rec = {"state": r["state_abbv"], "name": r["state"], "last_update": r["last_update"],
               "source_link": link, "source_label": label, "source_raw": raw,
               "uf_state_url": uf_state_url(r["state"], prev.get(r["state_abbv"])),
               "notes": None if pd.isna(r["notes"]) or r["notes"] == "NA" else r["notes"],
               "turnout_2022": num(r["turn_2022"])}
        for k in KEEP:
            rec[k] = num(r.get(k))
        # party fields are 0 for states without party registration -> treat as "not available"
        has_party = any((rec.get(f"{m}_dem") or 0) + (rec.get(f"{m}_rep") or 0) > 0 for m in ("request", "accept", "inperson", "voted"))
        rec["has_party_breakdown"] = has_party
        rec["reporting"] = (rec["voted_all"] or 0) > 0 or (rec["request_all"] or 0) > 0
        out.append(rec)
    listed = {o["state"] for o in out}
    missing = sorted(set(STATES.values()) - listed)
    for st in missing:
        out.append({"state": st, "name": ABBR2NAME[st], "reporting": False, "not_in_tracker": True,
                    "uf_state_url": uf_state_url(ABBR2NAME[st], prev.get(st)), "source_link": None, "source_label": None})
    out.sort(key=lambda x: x["state"])
    tot = {k: sum((o.get(k) or 0) for o in out) for k in ("voted_all", "accept_all", "inperson_all", "request_all")}
    return out, tot, missing

def cd_label_to_num(v):
    if pd.isna(v): return None
    m = re.findall(r"\d+", str(v).replace(".0", ""))
    return int(m[-1]) if m else None

def districts(state_list):
    out, avail = [], []
    for st in [s["state"] for s in state_list]:
        r = requests.get(f"{BASE}/{st}_cd.csv", headers={"User-Agent": "ElectionTrackerPrototype/0.1"}, timeout=60)
        if r.status_code != 200 or not r.text.strip() or "<html" in r.text[:200].lower():
            continue
        df = pd.read_csv(io.StringIO(r.text))
        if "cd" not in df: continue
        avail.append(st)
        df["cdn"] = df["cd"].map(cd_label_to_num)
        cols = [c for c in KEEP if c in df.columns]
        g = df.groupby(df["cdn"].fillna(-1))[cols].sum(min_count=1)
        for cdn, row in g.iterrows():
            rec = {"state": st, "district": None if cdn == -1 else int(cdn),
                   "key": f"{st}-UNASSIGNED" if cdn == -1 else f"{st}-{int(cdn):02d}",
                   "fields_available": cols}
            rec.update({c: num(row[c]) for c in cols})
            out.append(rec)
    return out, avail

if __name__ == "__main__":
    st, tot, missing = states()
    save("early_vote_states.json", {"generated": now_iso(), "source": PAGE, "data_url": f"{BASE}/US.csv",
        "attribution": "UF Election Lab (Dr. Michael McDonald), 2026 Early Voting tracker",
        "caveats": ["Party figures are voter party registration, not votes cast for a party.",
                    "States update on different schedules; see last_update per state.",
                    "Some states provide no early-vote data or are not in the tracker."],
        "states_not_in_tracker": missing, "national_totals": tot, "states": st})
    d, avail = districts(st)
    save("early_vote_districts.json", {"generated": now_iso(), "source": PAGE,
        "note": "Summed from UF district-by-county files. Coverage varies by state; some states' district files may not sum to the state total.",
        "states_with_district_data": avail, "districts": d})
    tu = pd.read_csv(io.StringIO(get(f"{BASE}/house_tossup_races.csv").text), dtype=str)
    save("house_competitive.json", {"generated": now_iso(), "source": f"{BASE}/house_tossup_races.csv",
        "note": "Districts flagged by the UF Election Lab as rated Toss-up by at least one outlet; ratings as compiled by UF.",
        "districts": tu.fillna("").to_dict(orient="records")})
    print("national", tot, "missing", missing, "cd states", avail)
