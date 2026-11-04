#!/usr/bin/env bash
# Box-side step after fetching X results with the built-in search_posts_all tool (query: see QUERY in x_feed_write.py).
# Usage: pipeline/x_feed_publish.sh /workspace/x_raw.json [page2.json ...]
# Merges into site/data/x_feed.json (+ race_calls.json) and pushes ONLY those files if they changed (the push triggers the Pages deploy).
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --rebase -q origin main
out=$(python3 pipeline/x_feed_write.py "$@"); echo "$out"
FILES=""; for f in site/data/x_feed.json site/data/race_calls.json; do [ -f "$f" ] && FILES="$FILES $f"; done
git add $FILES
git diff --cached --quiet -- $FILES && { echo "x_feed.json / race_calls.json unchanged; nothing to push"; exit 0; }
git commit -q -m "x feed refresh $(date -u +%FT%TZ)" -- $FILES
for i in 1 2 3; do git pull --rebase -q origin main && git push -q origin HEAD:main && { git log --oneline -1; exit 0; }; sleep $((i*5)); done
echo "push failed" >&2; exit 1
