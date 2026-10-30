# The San Francisco Seals Solicitor

A newspaper-style team news issue for the Seals after every MLBC sim.

## Each sim

1. Download the sim file into `~/Downloads/MLBC Sim Files/` as usual (`mlbcfile_2145_simNN/mlbcSeason/...`).
2. Build the stats packet:

   ```
   cd ~/Downloads/"MLBC Sim Files"/"Seals Solicitor"
   python3 build_facts.py
   ```

   It finds the newest sim, compares it with the one before it, numbers the issue automatically and
   writes `issues/mlbcfile_2145_simNN/issue_facts.json` and `issue_facts.md`.
3. Write `story.json` in that folder (ask Claude for "next issue", or copy the last issue's story.json as a template).
   Sections can drop in a table with `"insert": "standings" | "batting" | "pitching" | "leaders"`.
4. Publish:

   ```
   bash publish.sh
   ```

   This renders the newest issue, rebuilds the front page (`index.html`), commits and pushes to GitHub,
   and copies `post.html` to the clipboard so you can paste it straight into the MLBC team news form.

Options: `python3 build_facts.py --sim 11` rebuilds an older issue; `bash publish.sh issues/<folder>` publishes a specific one.

## Website

Hosted free on GitHub Pages from `ddecoen/seals-solicitor`:

- Front page (latest issue + back issues): https://ddecoen.github.io/seals-solicitor/
- Each issue: `https://ddecoen.github.io/seals-solicitor/issues/<folder>/page.html`

Every MLBC post ends with a link to the front page (set `SITE_URL` at the top of `render_issue.py`).

## Notes

- Requires only Python 3 (no packages).
- Standings, records and run totals are counted from `BoxScores.txt` and match the league site's standings page.
- MLBC years = engine year + 140. The All-Star Game is excluded from all stats.
- HR, 2B, 3B and SB come from the box score notes. A few engine box scores have minor internal
  inconsistencies (e.g. hits in the line score vs. the totals); the notes match the season totals the game keeps.
- Division alignment is in `DIVISIONS` at the top of `build_facts.py` if the league ever realigns.
