#!/usr/bin/env python3
"""Build the stats packet for a San Francisco Seals Solicitor issue.

Usage:
  python build_facts.py "~/Downloads/MLBC Sim Files"            # latest sim vs. the one before it
  python build_facts.py "~/Downloads/MLBC Sim Files" --sim 11   # a specific sim
  python build_facts.py --box path/BoxScores.txt --prev path/prev/BoxScores.txt

Writes issue_facts.json (read by render_issue.py) and issue_facts.md (a readable
brief to write the story from) into --out (default: ./issues/<sim tag>/).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

import boxscores

TEAM = "San Francisco"
DIVISIONS = {
    "RL East": ["Dayton", "Richmond", "Bangor", "Norwich", "Rome"],
    "RL Central": ["Erie", "Peoria", "Midland", "Sugar Land", "Auckland"],
    "RL West": ["Lake Elsinore", "San Francisco", "Omaha", "Oklahoma City", "Las Vegas"],
    "AL East": ["Chesapeake", "Louisville", "Mahoning Valley", "Scranton", "Maine"],
    "AL Central": ["El Paso", "Altoona", "Edmonton", "Wisconsin", "Rocket City"],
    "AL West": ["Frisco", "Portland", "Casper", "Texas", "Idaho Falls"],
}
NICK = {"San Francisco": "SF", "Lake Elsinore": "LE", "Oklahoma City": "OKC", "Las Vegas": "LV", "Sugar Land": "SL",
        "Mahoning Valley": "MV", "Rocket City": "RC", "Idaho Falls": "IF", "El Paso": "EP"}
PYTH_EXP = 1.83


def abbr(team: str) -> str:
    return NICK.get(team, team[:3].upper())


def fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}"


def avg3(x: float) -> str:
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


def ip_str(outs: int) -> str:
    return f"{outs // 3}" + (f" {outs % 3}/3" if outs % 3 else "")


# ----------------------------------------------------------------- team records
def team_games(games, team):
    return [g for g in games if team in (g["away"], g["home"])]


def result(g, team):
    me = g["teams"][0] if g["teams"][0]["name"] == team else g["teams"][1]
    op = g["teams"][1] if me is g["teams"][0] else g["teams"][0]
    return me, op, me["R"] > op["R"]


def record(games, team):
    r = {"W": 0, "L": 0, "RS": 0, "RA": 0, "home": [0, 0], "road": [0, 0], "one_run": [0, 0],
         "extras": [0, 0], "results": []}
    for g in team_games(games, team):
        me, op, won = result(g, team)
        k = 0 if won else 1
        r["W" if won else "L"] += 1
        r["RS"] += me["R"]
        r["RA"] += op["R"]
        r["home" if g["home"] == team else "road"][k] += 1
        if abs(me["R"] - op["R"]) == 1:
            r["one_run"][k] += 1
        if g["innings"] > 9:
            r["extras"][k] += 1
        r["results"].append("W" if won else "L")
    res = r.pop("results")
    streak_t, n = (res[-1], 0) if res else ("", 0)
    for x in reversed(res):
        if x != streak_t:
            break
        n += 1
    l10 = res[-10:]
    r["streak"] = f"{streak_t}{n}"
    r["last10"] = f"{l10.count('W')}-{l10.count('L')}"
    g = r["W"] + r["L"]
    r["G"] = g
    r["pct"] = r["W"] / g if g else 0
    rs, ra = r["RS"] ** PYTH_EXP, r["RA"] ** PYTH_EXP
    r["pyth_W"] = round(g * rs / (rs + ra), 1) if g else 0
    return r


def standings(games):
    out = {}
    for div, teams in DIVISIONS.items():
        rows = [dict(team=t, **record(games, t)) for t in teams]
        rows.sort(key=lambda x: (-(x["W"] - x["L"]), -x["W"]))
        lead = rows[0]
        for x in rows:
            x["GB"] = ((lead["W"] - x["W"]) + (x["L"] - lead["L"])) / 2
        out[div] = rows
    return out


# ------------------------------------------------------------------ player stats
def batting_totals(games, team=None):
    """Return {(team, player): stats}. team=None for league-wide."""
    tot = defaultdict(Counter)
    for g in games:
        for t, rows in g["batting"].items():
            if team and t != team:
                continue
            seen = set()
            for r in rows:
                k = (t, r["name"])
                c = tot[k]
                for f in ("AB", "R", "H", "BI", "BB", "SO"):
                    c[f] += r[f]
                if k not in seen:
                    c["G"] += 1
                    seen.add(k)
            for p, d in g["xbh"].get(t, {}).items():
                for f, n in d.items():
                    tot[(t, p)][f] += n
    return {k: finish_bat(v) for k, v in tot.items()}


def finish_bat(c):
    d = dict(c)
    for f in ("G", "AB", "R", "H", "BI", "BB", "SO"):
        d.setdefault(f, 0)
    ab, h, bb = c["AB"], c["H"], c["BB"]
    singles = h - c["2B"] - c["3B"] - c["HR"]
    tb = singles + 2 * c["2B"] + 3 * c["3B"] + 4 * c["HR"]
    d["PA"] = ab + bb
    d["AVG"] = h / ab if ab else 0
    d["OBP"] = (h + bb) / (ab + bb) if ab + bb else 0  # no HBP/SF in box lines
    d["SLG"] = tb / ab if ab else 0
    d["OPS"] = d["OBP"] + d["SLG"]
    for f in ("2B", "3B", "HR", "SB"):
        d.setdefault(f, 0)
    return d


def pitching_totals(games, team=None):
    tot = defaultdict(Counter)
    for g in games:
        for t, rows in g["pitching"].items():
            if team and t != team:
                continue
            for i, p in enumerate(rows):
                c = tot[(t, p["name"])]
                c["G"] += 1
                c["GS"] += i == 0
                for f in ("outs", "H", "R", "ER", "BB", "SO", "HR"):
                    c[f] += p[f]
                for dcode in p["dec"]:
                    c[dcode] += 1
    out = {}
    for k, c in tot.items():
        d = dict(c)
        for f in ("W", "L", "S", "H", "BS", "GS"):
            d.setdefault(f, 0)
        o = c["outs"]
        d["IP"] = ip_str(o)
        d["ERA"] = c["ER"] * 27 / o if o else 99.99
        d["WHIP"] = (c["H"] + c["BB"]) * 3 / o if o else 99.99
        d["K9"] = c["SO"] * 27 / o if o else 0
        out[k] = d
    return out


def game_score(p):
    """Bill James game score for a starter line."""
    return 50 + p["outs"] + 2 * max(0, p["outs"] // 3 - 4) + p["SO"] - 2 * p["H"] - 4 * p["ER"] - 2 * (p["R"] - p["ER"]) - p["BB"]


# ------------------------------------------------------------------ main builder
def build(box_path, prev_path=None, team=TEAM, issue_no=None):
    real = {t for ts in DIVISIONS.values() for t in ts}
    keep = lambda gs: [g for g in gs if g["away"] in real and g["home"] in real]  # drops All-Star Game
    all_games = boxscores.parse(box_path)
    n_prev = len(boxscores.parse(prev_path)) if prev_path else 0
    games, new = keep(all_games), keep(all_games[n_prev:])
    n_prev = len(games) - len(new)
    my_all = team_games(games, team)
    my_new = team_games(new, team)
    before = games[:n_prev]

    season = record(games, team)
    prior = record(before, team) if n_prev else None
    period = record(new, team)
    st = standings(games)
    st_prev = standings(before) if n_prev else None
    div = next(d for d, ts in DIVISIONS.items() if team in ts)
    league = div.split()[0]

    # games table
    log = []
    for g in my_new:
        me, op, won = result(g, team)
        home = g["home"] == team
        opp = op["name"]
        sp = g["starters"].get(team)
        sp_line = g["pitching"][team][0] if g["pitching"].get(team) else None
        decs = {}
        for t, rows in g["pitching"].items():
            for p in rows:
                for dcode in p["dec"]:
                    if dcode in ("W", "L", "S"):
                        decs[dcode] = p["name"] + ("" if t == team else f" ({abbr(t)})")
        potg = g.get("potg", "")
        potg_team = team if any(r["name"] == potg for r in g["batting"].get(team, []) + g["pitching"].get(team, [])) else opp
        hrs = [f"{p}" + (f" {d['HR']}" if d["HR"] > 1 else "") for p, d in g["xbh"].get(team, {}).items() if d.get("HR")]
        log.append({
            "date": g["date"], "date_str": fmt_date(g["date"]), "home": home, "opp": opp,
            "opp_label": ("" if home else "@ ") + opp,
            "score": f"{me['R']}-{op['R']}" + (f" ({g['innings']})" if g["innings"] > 9 else ""),
            "R": me["R"], "RA": op["R"], "H": me["H"], "won": won, "result": "W" if won else "L",
            "innings": g["innings"],
            "potg": potg + ("" if potg_team == team else f" ({abbr(opp)})"), "potg_is_seal": potg_team == team,
            "starter": sp, "starter_line": sp_line and {k: sp_line[k] for k in ("outs", "H", "R", "ER", "BB", "SO", "HR")},
            "starter_ip": sp_line and ip_str(sp_line["outs"]),
            "game_score": sp_line and game_score(sp_line),
            "decisions": decs, "seal_hr": hrs, "att": g.get("att"),
        })

    # player stats
    bat_p = {p: v for (t, p), v in batting_totals(new, team).items()}
    bat_s = {p: v for (t, p), v in batting_totals(games, team).items()}
    pit_p = {p: v for (t, p), v in pitching_totals(new, team).items()}
    pit_s = {p: v for (t, p), v in pitching_totals(games, team).items()}

    def top_bat(d, minpa):
        rows = [dict(name=k, **v) for k, v in d.items() if v["PA"] >= minpa]
        return sorted(rows, key=lambda r: -r["OPS"])

    def top_pit(d):
        rows = [dict(name=k, **v) for k, v in d.items()]
        return sorted(rows, key=lambda r: (-r["GS"], -r["outs"]))

    # league leaders + Seals ranks
    lg_bat = batting_totals(games)
    lg_pit = pitching_totals(games)
    gp = Counter()
    for g in games:
        gp[g["away"]] += 1
        gp[g["home"]] += 1

    def leaders(stat, src, qual=None, reverse=True, n=10, fmt=None):
        rows = [(t, p, v) for (t, p), v in src.items() if (qual is None or qual(t, v))]
        rows.sort(key=lambda r: r[2][stat], reverse=reverse)
        out, rank, prev = [], 0, None
        for i, (t, p, v) in enumerate(rows):
            if v[stat] != prev:
                rank = i + 1
                prev = v[stat]
            out.append({"rank": rank, "name": p, "team": t, "value": v[stat]})
        top = out[:n]
        seals = [r for r in out if r["team"] == team and r["rank"] <= 25]
        return {"top": top, "seals": seals}

    bq = lambda t, v: v["PA"] >= 3.1 * gp[t]
    pq = lambda t, v: v["outs"] >= 3 * gp[t]
    lead = {
        "HR": leaders("HR", lg_bat), "RBI": leaders("BI", lg_bat),
        "AVG": leaders("AVG", lg_bat, bq), "OPS": leaders("OPS", lg_bat, bq),
        "SB": leaders("SB", lg_bat),
        "W": leaders("W", lg_pit), "ERA": leaders("ERA", lg_pit, pq, reverse=False),
        "SO": leaders("SO", lg_pit), "S": leaders("S", lg_pit),
    }

    # notable items in the period
    notes = []
    for x in log:
        for p, d in (g2 for g in my_new if g["date"] == x["date"] for g2 in g["xbh"].get(team, {}).items()):
            if d.get("HR", 0) >= 2:
                notes.append(f"{p} hit {d['HR']} HR on {x['date_str']} vs {x['opp']}")
    for g in my_new:
        for r in g["batting"].get(team, []):
            if r["H"] >= 4:
                notes.append(f"{r['name']} went {r['H']}-for-{r['AB']} on {fmt_date(g['date'])} vs {[t for t in (g['away'], g['home']) if t != team][0]}")
            if r["BI"] >= 5:
                notes.append(f"{r['name']} drove in {r['BI']} on {fmt_date(g['date'])}")
    best_start = max((x for x in log if x["game_score"] is not None), key=lambda x: x["game_score"], default=None)

    first, last = (my_new[0]["date"], my_new[-1]["date"]) if my_new else (None, None)
    facts = {
        "team": team, "team_full": "San Francisco Seals", "issue_no": issue_no,
        "through": last, "through_str": fmt_date(last) + f", {date.fromisoformat(last).year}" if last else None,
        "period_start": first, "period_start_str": fmt_date(first) if first else None,
        "league": league, "division": div,
        "season": season, "prior": prior, "period": period,
        "standings": st[div], "standings_prev": st_prev[div] if st_prev else None,
        "league_standings": {d: st[d] for d in DIVISIONS if d.startswith(league)},
        "log": log,
        "batting_period": top_bat(bat_p, 10), "batting_season": top_bat(bat_s, 3.1 * season["G"]),
        "batting_season_all": top_bat(bat_s, 1),
        "pitching_period": top_pit(pit_p), "pitching_season": top_pit(pit_s),
        "leaders": lead, "notables": notes,
        "best_start": best_start,
        "n_games_league": len(games), "n_games_new_league": len(new),
    }
    return facts


def brief(f) -> str:
    """Readable markdown brief of the facts for writing the story."""
    s, p, pr = f["season"], f["period"], f["prior"]
    L = [f"# Seals facts through {f['through_str']}", ""]
    L.append(f"Season: {s['W']}-{s['L']} ({avg3(s['pct'])}), RS {s['RS']} RA {s['RA']} (diff {s['RS']-s['RA']:+d}), "
             f"Pythag W {s['pyth_W']}, home {s['home'][0]}-{s['home'][1]}, road {s['road'][0]}-{s['road'][1]}, "
             f"1-run {s['one_run'][0]}-{s['one_run'][1]}, extras {s['extras'][0]}-{s['extras'][1]}, streak {s['streak']}, L10 {s['last10']}")
    if pr:
        L.append(f"Before this sim: {pr['W']}-{pr['L']}")
    L.append(f"This sim ({f['period_start_str']} - {f['through_str']}): {p['W']}-{p['L']}, RS {p['RS']} RA {p['RA']}, "
             f"home {p['home'][0]}-{p['home'][1]}, road {p['road'][0]}-{p['road'][1]}, 1-run {p['one_run'][0]}-{p['one_run'][1]}, "
             f"extras {p['extras'][0]}-{p['extras'][1]}")
    L += ["", f"## {f['division']} standings (prev GB in brackets)"]
    prevgb = {r["team"]: r["GB"] for r in (f["standings_prev"] or [])}
    for r in f["standings"]:
        L.append(f"- {r['team']} {r['W']}-{r['L']} GB {r['GB']} [{prevgb.get(r['team'], '')}] {r['streak']} L10 {r['last10']} RS {r['RS']} RA {r['RA']}")
    L += ["", "## Game log this sim"]
    for x in f["log"]:
        dec = ", ".join(f"{k}: {v}" for k, v in x["decisions"].items())
        L.append(f"- {x['date_str']} {x['opp_label']} {x['score']} {x['result']} | SP {x['starter']} {x['starter_ip']} IP "
                 f"{x['starter_line']['H']}H {x['starter_line']['ER']}ER {x['starter_line']['BB']}BB {x['starter_line']['SO']}K GSc {x['game_score']} "
                 f"| {dec} | POTG {x['potg']} | Seal HR: {', '.join(x['seal_hr']) or '-'}")
    L += ["", "## Batting this sim (PA>=10, by OPS)"]
    for r in f["batting_period"]:
        L.append(f"- {r['name']}: {r['H']}-{r['AB']}, {r['2B']} 2B {r['3B']} 3B {r['HR']} HR {r['BI']} RBI {r['R']} R {r['BB']} BB {r['SO']} K {r['SB']} SB, "
                 f"{avg3(r['AVG'])}/{avg3(r['OBP'])}/{avg3(r['SLG'])}")
    L += ["", "## Pitching this sim"]
    for r in f["pitching_period"]:
        L.append(f"- {r['name']}: {r['G']} G {r['GS']} GS, {r['W']}-{r['L']} {r['S']} SV, {r['IP']} IP {r['H']} H {r['ER']} ER {r['BB']} BB {r['SO']} K {r['HR']} HR, ERA {r['ERA']:.2f}")
    L += ["", "## Season batting (qualified, by OPS)"]
    for r in f["batting_season"]:
        L.append(f"- {r['name']}: {r['G']} G, {avg3(r['AVG'])}/{avg3(r['OBP'])}/{avg3(r['SLG'])}, {r['HR']} HR {r['BI']} RBI {r['SB']} SB")
    L += ["", "## Season pitching"]
    for r in f["pitching_season"][:12]:
        L.append(f"- {r['name']}: {r['G']} G {r['GS']} GS, {r['W']}-{r['L']} {r['S']} SV, {r['IP']} IP, ERA {r['ERA']:.2f} WHIP {r['WHIP']:.2f} K {r['SO']}")
    L += ["", "## League leaders (whole league) and Seals ranks"]
    for k, v in f["leaders"].items():
        top = ", ".join(f"{x['rank']}. {x['name']} ({abbr(x['team'])}) {fmtv(k, x['value'])}" for x in v["top"][:5])
        seals = ", ".join(f"#{x['rank']} {x['name']} {fmtv(k, x['value'])}" for x in v["seals"])
        L.append(f"- {k}: {top} || Seals: {seals or '-'}")
    L += ["", "## Notables"] + [f"- {n}" for n in f["notables"]]
    if f["best_start"]:
        b = f["best_start"]
        L.append(f"- Best start: {b['starter']} on {b['date_str']} vs {b['opp']} (game score {b['game_score']})")
    return "\n".join(L) + "\n"


def fmtv(stat, v):
    if stat in ("AVG", "OPS"):
        return avg3(v)
    if stat == "ERA":
        return f"{v:.2f}"
    return str(v)


def find_sims(root):
    root = os.path.expanduser(root)
    dirs = []
    for d in os.listdir(root):
        m = re.search(r"sim(\d+)$", d)
        if m and os.path.exists(os.path.join(root, d, "mlbcSeason", "BoxScores.txt")):
            dirs.append((int(m.group(1)), os.path.join(root, d, "mlbcSeason", "BoxScores.txt"), d))
    return sorted(dirs)


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SIMS = [os.path.dirname(HERE), os.path.expanduser("~/Downloads/MLBC Sim Files")]


def next_issue_no(issues_dir, out):
    """Keep the number if this folder was built before, else one more than the highest so far."""
    nums = {}
    if os.path.isdir(issues_dir):
        for d in os.listdir(issues_dir):
            fp = os.path.join(issues_dir, d, "issue_facts.json")
            if os.path.exists(fp):
                n = json.load(open(fp)).get("issue_no")
                if n:
                    nums[os.path.abspath(os.path.join(issues_dir, d))] = n
    return nums.get(os.path.abspath(out)) or (max(nums.values(), default=0) + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sims_dir", nargs="?", help="folder holding mlbcfile_YYYY_simNN folders "
                    "(default: the folder this script sits in, or ~/Downloads/MLBC Sim Files)")
    ap.add_argument("--sim", type=int, help="sim number to report (default: latest)")
    ap.add_argument("--box", help="BoxScores.txt to report on (instead of sims_dir)")
    ap.add_argument("--prev", help="previous sim's BoxScores.txt (games in it are excluded from 'this sim')")
    ap.add_argument("--issue", type=int, help="issue number (default: next number automatically)")
    ap.add_argument("--team", default=TEAM)
    ap.add_argument("--out", help="output folder")
    a = ap.parse_args()

    tag = "issue"
    if not a.box:
        roots = [a.sims_dir] if a.sims_dir else DEFAULT_SIMS
        sims = next((s for r in roots if os.path.isdir(os.path.expanduser(r)) for s in [find_sims(r)] if s), None)
        if not sims:
            sys.exit(f"No mlbcfile_*_simNN folders with BoxScores.txt found in: {', '.join(roots)}")
        idx = next(i for i, s in enumerate(sims) if s[0] == a.sim) if a.sim else len(sims) - 1
        a.box = sims[idx][1]
        a.prev = sims[idx - 1][1] if idx > 0 else None
        tag = sims[idx][2]
    issues_dir = os.path.join(HERE, "issues")
    out = a.out or os.path.join(issues_dir, tag)
    issue_no = a.issue or next_issue_no(issues_dir, out)
    f = build(a.box, a.prev, a.team, issue_no)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "issue_facts.json"), "w") as fh:
        json.dump(f, fh, indent=1, default=str)
    with open(os.path.join(out, "issue_facts.md"), "w") as fh:
        fh.write(brief(f))
    print(f"Issue No. {issue_no}: wrote {os.path.relpath(out, HERE)}/issue_facts.json and issue_facts.md "
          f"({len(f['log'])} Seals games, {f['period_start_str']} - {f['through_str']})")
    print(f"Next: write story.json in that folder (or ask Claude), then run: bash publish.sh")


if __name__ == "__main__":
    main()
