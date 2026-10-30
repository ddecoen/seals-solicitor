# The San Francisco Seals Solicitor

A newspaper-style team news issue for the Seals after every MLBC sim.

## Each sim

1. Download the sim file into `~/Downloads/MLBC Sim Files/` as usual (`mlbcfile_2145_simNN/mlbcSeason/...`).
2. Build the stats packet (compares the newest sim with the one before it):

   ```
   python3 build_facts.py "~/Downloads/MLBC Sim Files" --issue 2
   ```

   This writes `issues/mlbcfile_2145_simNN/issue_facts.json` and `issue_facts.md`.
3. Write `story.json` in that folder: headline, dek, lead paragraphs and sections. Copy the
   previous issue's `story.json` as a template, or hand `issue_facts.md` to Claude and ask for the issue.
   Sections can drop in a table with `"insert": "standings" | "batting" | "pitching" | "leaders"`.
4. Render:

   ```
   python3 render_issue.py issues/mlbcfile_2145_simNN
   ```

   - `post.html`: paste into the MLBC team news form (all styles are inline, the same way the Scranton posts work).
   - `page.html`: the same issue as a standalone web page.

Options: `--sim 11` to rebuild an older issue, `--box/--prev` to point at specific BoxScores.txt files.

## Hosting a fuller version for free

`page.html` is a complete static page. To publish it, put the `issues/` folders in a GitHub repo
(e.g. `ddecoen/seals-solicitor`) and turn on GitHub Pages (Settings → Pages → deploy from `main`).
Each issue gets a URL like `https://ddecoen.github.io/seals-solicitor/issues/mlbcfile_2145_sim11/page.html`,
which you can link from the MLBC post. Netlify and Cloudflare Pages also work and are free.

## Notes

- Requires only Python 3 (no packages).
- Standings, records and run totals are counted from `BoxScores.txt` and match the league site's standings page.
- MLBC years = engine year + 140. The All-Star Game is excluded from all stats.
- HR, 2B, 3B and SB come from the box score notes. A few engine box scores have minor internal
  inconsistencies (e.g. hits in the line score vs. the totals); the notes match the season totals the game keeps.
- Division alignment is in `DIVISIONS` at the top of `build_facts.py` if the league ever realigns.
