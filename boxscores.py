"""Parser for High Heat Baseball 2003 BoxScores.txt exports (MLBC league).

Produces a list of Game dicts with line score, batting/pitching lines,
extra-base hits, decisions and the Player of the Game.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime

YEAR_OFFSET = 140  # MLBC display year = engine year + 140

HEADER_RE = re.compile(r"^Team(\d+) vs Team(\d+) \(Day (\d+)\)\s*$")
DATE_RE = re.compile(r"^Date of game:\s+(.+?)\s*$")
FINAL_RE = re.compile(r"^FINAL(?: IN (\d+))?\s")
BAT_HDR_RE = re.compile(r"^(\S.*?)\s+AB\s+R\s+H\s+BI\s+BB\s+SO\s+LO\s+AVG\s*$")
PIT_HDR_RE = re.compile(r"^(\S.*?)\s+IP\s+H\s+R\s+ER\s+BB\s+SO\s+HR\s+ERA\s*$")
BAT_RE = re.compile(
    r"^(\s*)(\S.*?)\s+([A-Za-z0-9\-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*$"
)
PIT_RE = re.compile(
    r"^(\S.*?)\s{2,}(\d+ \d/3|\d/3|\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*$"
)
POTG_RE = re.compile(r"^High Heat Baseball Player of the Game:\s+(.+?)\s*$")
ATT_RE = re.compile(r"Att:\s*([\d,]+)")
LABELS = ["2B", "3B", "HR", "RBI", "2-OUT RBI", "SB", "CS", "E", "GIDP", "SF", "SH",
          "Runners left in scoring position, 2 outs", "Team LOB", "PB", "DP", "Outfield assists"]


def ip_to_outs(s: str) -> int:
    s = s.strip()
    if " " in s:
        whole, frac = s.split()
        return int(whole) * 3 + int(frac[0])
    if "/" in s:
        return int(s[0])
    return int(s) * 3


def split_top(s: str, sep: str = ";") -> list[str]:
    """Split on sep only outside parentheses."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def parse_notes(block: str) -> dict[str, list[tuple[str, int]]]:
    """Parse 'BATTING' note block into {label: [(lastname, count), ...]}."""
    text = " ".join(block.split())
    # Find label positions (only labels followed by ':' at a sentence start)
    # Any label at the start of a sentence: "HR:", "S:", "2-OUT RBI:", "Team LOB:" ...
    pat = re.compile(r"(?:(?<=\.\s)|^)([A-Z0-9][A-Za-z0-9\- ,]{0,45}?):\s")
    hits = list(pat.finditer(text))
    res = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end].strip().rstrip(".").strip()
        items = []
        for ent in split_top(body):
            mm = re.match(r"^(.+?)(?:\s+(\d+))?(?:\s*\(.*\))?$", ent)
            if mm:
                items.append((mm.group(1).strip(), int(mm.group(2) or 1)))
        res[m.group(1)] = items
    return res


def parse(path: str) -> list[dict]:
    lines = open(path, encoding="latin-1").read().splitlines()
    starts = [i for i, l in enumerate(lines) if HEADER_RE.match(l)]
    starts.append(len(lines))
    games = []
    for gi in range(len(starts) - 1):
        g = parse_game(lines[starts[gi]:starts[gi + 1]])
        if g:
            g["idx"] = gi
            games.append(g)
    return games


def parse_game(L: list[str]) -> dict | None:
    hm = HEADER_RE.match(L[0])
    g = {"day": int(hm.group(3)), "innings": 9, "teams": [], "batting": {}, "pitching": {}, "notes": {}}
    i = 1
    while i < len(L):
        l = L[i]
        if m := DATE_RE.match(l):
            d = datetime.strptime(m.group(1), "%B %d, %Y").date()
            g["engine_date"] = d.isoformat()
            g["date"] = date(d.year + YEAR_OFFSET, d.month, d.day).isoformat()
        elif m := FINAL_RE.match(l):
            if m.group(1):
                g["innings"] = int(m.group(1))
            j = i + 1
            while not L[j].strip():
                j += 1
            for k in (j, j + 1):
                row = L[k]
                nums = row[19:].split()
                g["teams"].append({
                    "name": row[:19].strip(),
                    "R": int(nums[-3]), "H": int(nums[-2]), "E": int(nums[-1]),
                    "line": nums[:-3],
                })
            i = j + 1
        elif m := BAT_HDR_RE.match(l):
            team = m.group(1).strip()
            rows, i = [], i + 1
            while i < len(L) and not L[i].startswith("TOTALS"):
                if bm := BAT_RE.match(L[i]):
                    rows.append({
                        "name": bm.group(2).strip(), "pos": bm.group(3), "sub": bool(bm.group(1)),
                        "AB": int(bm.group(4)), "R": int(bm.group(5)), "H": int(bm.group(6)),
                        "BI": int(bm.group(7)), "BB": int(bm.group(8)), "SO": int(bm.group(9)),
                    })
                i += 1
            g["batting"][team] = rows
            # notes block until next team header / pitching header
            j, buf = i + 1, []
            while j < len(L) and not BAT_HDR_RE.match(L[j]) and not PIT_HDR_RE.match(L[j]):
                buf.append(L[j])
                j += 1
            notes = {}
            for sect in ("BATTING", "BASERUNNING", "FIELDING"):
                txt = "\n".join(buf)
                mm = re.search(sect + r"\n(.*?)(?:\n\s*\n|\Z)", txt, re.S)
                if mm:
                    notes.update(parse_notes(mm.group(1)))
            g["notes"][team] = notes
            i = j - 1
        elif m := PIT_HDR_RE.match(l):
            team = m.group(1).strip()
            rows, i = [], i + 1
            while i < len(L) and not L[i].strip():
                i += 1
            while i < len(L) and L[i].strip():
                if pm := PIT_RE.match(L[i]):
                    raw = pm.group(1)
                    name = re.sub(r"\s*\(.*$", "", raw).strip()
                    dec = re.findall(r"\((W|L|S|H|BS)(?:,\s*([\d\-]+))?\)", raw)
                    rows.append({
                        "name": name, "dec": [d[0] for d in dec], "dec_raw": raw[len(name):].strip(),
                        "outs": ip_to_outs(pm.group(2)), "H": int(pm.group(3)), "R": int(pm.group(4)),
                        "ER": int(pm.group(5)), "BB": int(pm.group(6)), "SO": int(pm.group(7)),
                        "HR": int(pm.group(8)),
                    })
                i += 1
            g["pitching"][team] = rows
            continue
        elif m := POTG_RE.match(l):
            g["potg"] = m.group(1)
        elif "Att:" in l and (m := ATT_RE.search(l)):
            g["att"] = int(m.group(1).replace(",", ""))
        elif l.startswith("GAME SUMMARY"):
            break
        i += 1
    if len(g["teams"]) != 2:
        return None
    g["away"], g["home"] = g["teams"][0]["name"], g["teams"][1]["name"]
    # Starters: first pitcher listed per team
    g["starters"] = {t: rows[0]["name"] for t, rows in g["pitching"].items() if rows}
    # resolve extra-base-hit notes (last names) to full names
    g["xbh"] = {}
    for t, notes in g["notes"].items():
        roster = [r["name"] for r in g["batting"].get(t, [])]
        per = defaultdict(lambda: defaultdict(int))
        for lab in ("2B", "3B", "HR", "SB"):
            for short, n in notes.get(lab, []):
                full = resolve(short, roster)
                per[full][lab] += n
        g["xbh"][t] = {k: dict(v) for k, v in per.items()}
    return g


def resolve(short: str, roster: list[str]) -> str:
    cands = [r for r in roster if r.endswith(" " + short) or r == short]
    if len(cands) == 1:
        return cands[0]
    # Initial-qualified ("J. Smith") or ambiguous
    m = re.match(r"^([A-Z])\.?\s+(.+)$", short)
    if m:
        c2 = [r for r in roster if r.startswith(m.group(1)) and r.endswith(" " + m.group(2))]
        if len(c2) == 1:
            return c2[0]
    return cands[0] if cands else short
