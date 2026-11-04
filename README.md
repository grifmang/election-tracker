# 2026 Midterms Vote Tracker (prototype)
- `pipeline/` — Python data fetchers -> `site/data/*.json`
  - `fetch_races.py` (Wikipedia: 435 House + 35 Senate), `fetch_early_vote.py` (UF Election Lab CSVs), `fetch_results.py` (Open America feed; `--test2024` replay), `run_all.py`
- `site/` — static HTML/JS (no build step). Serve: `cd site && python3 -m http.server 8787`
- `.github/workflows/refresh.yml` — refreshes data every 2h and deploys `site/` to GitHub Pages
- `RESEARCH.md` — sources, granularity, gaps
Run: `pip install -r requirements.txt && python3 pipeline/run_all.py`

## Election-night posts from X (News desks on X tab, `#news`)
`site/data/x_feed.json` holds verbatim public posts from news-desk accounts on X, each linking to the original.
GitHub Actions has no X access, so it's refreshed from the Grok Bot box: run the built-in X `search_posts_all` tool
with the `QUERY` in `pipeline/x_feed_write.py` (`start_time` 2026-11-03T22:00:00Z, `sort_order` recency, `max_results` 100,
`expansions` author_id, `user.fields` name,username, `post.fields` created_at,author_id), save the response to
`/workspace/x_raw.json`, then run `pipeline/x_feed_publish.sh /workspace/x_raw.json`. Existing posts are kept (max 60, newest first).
Each post gets a `races` array (e.g. `GA Senate`, `VA-02`, `Senate control`, `Other / general`), tagged deterministically in
`x_feed_write.py` against `races_senate.json` / `races_house.json`; the tab groups by race by default, with a race filter and a plain newest-first toggle.

## Seats-won scoreboard (sticky sidebar on the `#news` tab)
- Counts **only explicit race calls/projections** in the collected news-desk posts ("X wins …", "… projects X will win", "#DecisionMade", "race call: …"), plus the Open America feed's own `called`/`winner` field if it ever reports one. Not official results.
- `pipeline/x_feed_write.py` extracts calls from every post it has seen (before the feed is capped at 300 posts) and keeps them in the durable `site/data/race_calls.json` — `{calls:[{race, chamber, winner_name, party, called_by:[{handle, post_url, created_at}]}], conflicting:[…], totals, claims}`. Claims from posts that later roll off the feed are kept.
- A claim counts only when the post is tagged to one specific race and names exactly one of that race's general-election candidates as the winner. A race counts once; if desks name different winners it goes under `conflicting` and isn't counted.
- `pipeline/x_feed_publish.sh` commits both `x_feed.json` and `race_calls.json`.
- Senate whole-chamber total = seats not up in 2026 + called seats. Seats not up come from `pipeline/senate_holdovers.py` → `site/data/senate_holdovers.json` (Wikipedia's 2026 Senate summary table at the same revision as `races_senate.json`; the script refuses to write unless seats-before minus the 35 incumbents up equals the "Not up" row). If that file is missing the sidebar shows only "of 35 seats up".
