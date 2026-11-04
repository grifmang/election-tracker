"""Senate seats NOT up in 2026 (holdovers), so the scoreboard can show a projected chamber total.

Source: the "Not up" / "Before these elections" rows of the summary table on Wikipedia's
"2026 United States Senate elections" page, at the same revision races_senate.json was built from.
Cross-check: seats before the election minus the incumbents of the 35 races in races_senate.json
must equal the "Not up" row exactly; otherwise nothing is written and the site shows only
"of 35 seats up".
"""
import json, re, sys, pathlib
from common import get, save, now_iso

DATA = pathlib.Path(__file__).resolve().parent.parent / "site" / "data"
PARTY = {"Democratic": "D", "DFL": "D", "Democratic-Farmer-Labor": "D", "Republican": "R", "Independent": "I"}


def nums(row):
    # cells after the header: "| {{Party shading/Democratic}} | 32", "| 31", "| {{sdash}}"; last "! 65" is the total
    vals = []
    for ln in row.splitlines()[1:]:
        ln = ln.strip()
        if not ln.startswith(("|", "!")) or ln.startswith("|-"):
            continue
        cell = re.split(r"[|!]", ln)[-1].strip()
        cell = re.sub(r"\{\{efn.*", "", cell).strip()
        vals.append(0 if "sdash" in cell else int(cell))
    return vals  # [D, I, R, total]


def main():
    races = json.loads((DATA / "races_senate.json").read_text())
    rev = races["wikipedia_revid"]
    j = get("https://en.wikipedia.org/w/index.php", params={"oldid": rev, "action": "raw"})
    wt = j.text
    def row(label):
        m = re.search(r"!\s*colspan=2[^|\n]*\|\s*" + label + r"\s*\n(.*?)\n\|-", wt, re.S)
        if not m:
            sys.exit(f"row {label!r} not found in revision {rev}")
        return nums(label + "\n" + m.group(1))
    before, notup = row("Before these elections"), row("Not up")
    D, I, R, tot = notup
    up = {"D": 0, "R": 0, "I": 0}
    for r in races["races"]:
        up[PARTY[r["incumbent"]["party"]]] += 1
    ok = (before[0] - up["D"], before[1] - up["I"], before[2] - up["R"]) == (D, I, R) and tot == 100 - len(races["races"])
    if not ok:
        sys.exit(f"cross-check failed: before={before} up={up} not_up={notup}; not writing")
    save("senate_holdovers.json", {
        "generated": now_iso(),
        "source": races["source"], "wikipedia_revid": rev, "license": races.get("license"),
        "not_up": {"D": D, "R": R, "I": I}, "independents_caucus_with": "D",
        "seats_up": len(races["races"]), "chamber": 100, "majority": 51,
        "tie_note": "At 50-50 the Vice President (JD Vance, R) breaks ties.",
        "cross_check": f"before {before[0]}D/{before[1]}I/{before[2]}R minus incumbents up {up['D']}D/{up['I']}I/{up['R']}R = not up {D}D/{I}I/{R}R",
    })
    print("senate_holdovers.json written", D, I, R)


if __name__ == "__main__":
    main()
