# 2026 Midterms Vote Tracker (prototype)
- `pipeline/` — Python data fetchers -> `site/data/*.json`
  - `fetch_races.py` (Wikipedia: 435 House + 35 Senate), `fetch_early_vote.py` (UF Election Lab CSVs), `fetch_results.py` (Open America feed; `--test2024` replay), `run_all.py`
- `site/` — static HTML/JS (no build step). Serve: `cd site && python3 -m http.server 8787`
- `.github/workflows/refresh.yml` — refreshes data every 2h and deploys `site/` to GitHub Pages
- `RESEARCH.md` — sources, granularity, gaps
Run: `pip install -r requirements.txt && python3 pipeline/run_all.py`

## Election-night posts from X (Live results tab)
`site/data/x_feed.json` holds verbatim public posts from news-desk accounts on X, each linking to the original.
GitHub Actions has no X access, so it's refreshed from the Grok Bot box: run the built-in X `search_posts_all` tool
with the `QUERY` in `pipeline/x_feed_write.py` (`start_time` 2026-11-03T22:00:00Z, `sort_order` recency, `max_results` 100,
`expansions` author_id, `user.fields` name,username, `post.fields` created_at,author_id), save the response to
`/workspace/x_raw.json`, then run `pipeline/x_feed_publish.sh /workspace/x_raw.json`. Existing posts are kept (max 60, newest first).
