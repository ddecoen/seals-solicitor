#!/bin/bash
# Render the newest issue (or the folder given), rebuild the front page,
# push to GitHub Pages, and copy the MLBC post to the clipboard.
#
#   bash publish.sh                                  # newest issue with a story.json
#   bash publish.sh issues/mlbcfile_2145_sim12       # a specific issue
set -e
cd "$(dirname "$0")"

python3 render_issue.py "$@"

read -r FOLDER NUM <<<"$(python3 - "$@" <<'PY'
import json, os, sys
import render_issue as r
args = [a for a in sys.argv[1:] if a]
if args:
    folder = os.path.abspath(args[0])
else:
    folder = [fp for fp in r.issue_folders() if os.path.exists(os.path.join(fp, "story.json"))][-1]
f = json.load(open(os.path.join(folder, "issue_facts.json")))
print(os.path.relpath(folder, r.HERE), f.get("issue_no", ""))
PY
)"

git add -A
if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -q -m "Seals Solicitor No. $NUM"
  git push -q
  echo "Pushed No. $NUM to GitHub. The site updates in a minute or two."
fi

if command -v pbcopy >/dev/null; then
  pbcopy < "$FOLDER/post.html"
  echo "Copied $FOLDER/post.html to the clipboard. Paste it into the MLBC team news form."
fi
echo "Issue:      https://ddecoen.github.io/seals-solicitor/$FOLDER/page.html"
echo "Front page: https://ddecoen.github.io/seals-solicitor/"
