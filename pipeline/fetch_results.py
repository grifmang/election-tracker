"""Election-night results adapter. Default source: Open America public feed
(https://openamerica.io/elections/api/) - official state counts, no race calls, ~22 states, free, CORS.
Swap in AP / DDHQ / Clarity adapters here later; the site reads site/data/results_<office>.json.
Usage: python fetch_results.py            -> 2026 live feed
       python fetch_results.py --test2024 -> 2024 replay written to results_test2024_<office>.json"""
import sys
from common import get, save, now_iso

URL = "https://openamerica.io/elections/results.json?year={y}&office={o}"

def normalize(j, office):
    races = {}
    for key, r in (j.get("races") or {}).items():
        races[key] = {"pct_in": r.get("pct_in"), "total": r.get("total"), "leader": r.get("leader"),
                      "called": r.get("called"), "winner": r.get("winner") or None,
                      "candidates": [{"name": c.get("n"), "party": c.get("p"), "votes": c.get("v"), "pct": c.get("pct")} for c in r.get("cands", [])]}
    return {"generated": now_iso(), "source": "Open America results feed (official state counts; no projections)",
            "source_url": URL.format(y=j.get("year"), o=office), "year": j.get("year"), "office": office,
            "live": j.get("live"), "as_of": j.get("as_of"), "counts": j.get("counts"), "races": races}

if __name__ == "__main__":
    test = "--test2024" in sys.argv
    y = 2024 if test else 2026
    for office in ("House", "Senate"):
        j = get(URL.format(y=y, o=office)).json()
        save(f"results_{'test2024_' if test else ''}{office.lower()}.json", normalize(j, office))
