# 2026 Midterms Vote Tracker (prototype)
- `pipeline/` — Python data fetchers -> `site/data/*.json`
  - `fetch_races.py` (Wikipedia: 435 House + 35 Senate), `fetch_early_vote.py` (UF Election Lab CSVs), `fetch_results.py` (Open America feed; `--test2024` replay), `run_all.py`
- `site/` — static HTML/JS (no build step). Serve: `cd site && python3 -m http.server 8787`
- `.github/workflows/refresh.yml` — refreshes data every 2h and deploys `site/` to GitHub Pages
- `RESEARCH.md` — sources, granularity, gaps
Run: `pip install -r requirements.txt && python3 pipeline/run_all.py`
