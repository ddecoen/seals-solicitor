#!/usr/bin/env python3
"""Render a San Francisco Seals Solicitor issue as paste-ready HTML.

Usage:
  python render_issue.py issues/mlbcfile_2145_sim11

Reads issue_facts.json (from build_facts.py) and story.json (the written copy)
from that folder and writes:
  post.html  - inline-styled fragment to paste into the MLBC team news form
  page.html  - the same issue wrapped as a standalone page (for GitHub Pages etc.)

Every style is inline because the league site's news form keeps inline styles
and nothing else. No web fonts, scripts or images are used.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

# ---------------------------------------------------------------- palette/type
INK = "#1f1b16"        # body text
PAPER = "#f7f2e6"      # newsprint
RULE = "#1f1b16"
MUTED = "#6f6556"
RED = "#9b2226"        # Seals oxblood accent
GOLD = "#b08a3e"       # thin gilt rules
TINT = "#efe5cf"       # win-row tint
LINE = "#d8cdb4"

SERIF = "Georgia,'Times New Roman',Times,serif"
DISPLAY = "'Playfair Display',Didot,'Bodoni 72','Bodoni MT',Georgia,serif"
MONO = "'Courier New',Courier,monospace"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def md_inline(s: str) -> str:
    """Escape text and support **bold** and *italic*."""
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    return s


def avg3(x: float) -> str:
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


def gb(x: float) -> str:
    return "—" if x == 0 else (f"{x:.1f}")


ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n: int) -> str:
    out = ""
    for v, s in ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


# ---------------------------------------------------------------- building blocks
def p(text: str, first=False) -> str:
    style = f"font-family:{SERIF};font-size:17px;line-height:1.62;color:{INK};margin:0 0 14px 0;"
    if first:
        t = md_inline(text)
        cap, rest = t[0], t[1:]
        dc = (f"<span style=\"float:left;font-family:{DISPLAY};font-size:66px;line-height:54px;"
              f"font-weight:bold;color:{RED};padding:6px 8px 0 0;\">{cap}</span>")
        return f"<p style=\"{style}\">{dc}{rest}</p>"
    return f"<p style=\"{style}\">{md_inline(text)}</p>"


def section_head(text: str) -> str:
    return (f"<div style=\"margin:28px 0 10px 0;border-top:3px double {RULE};padding-top:8px;\">"
            f"<span style=\"font-family:{SANS};font-size:12px;font-weight:bold;letter-spacing:3px;"
            f"text-transform:uppercase;color:{RED};\">{esc(text)}</span></div>")


def sub_head(text: str) -> str:
    return (f"<h3 style=\"font-family:{DISPLAY};font-size:24px;line-height:1.15;font-weight:bold;"
            f"color:{INK};margin:22px 0 8px 0;\">{esc(text)}</h3>")


def table(headers, rows, aligns=None, tints=None, note=None) -> str:
    aligns = aligns or ["left"] + ["right"] * (len(headers) - 1)
    th = "".join(
        f"<th style=\"font-family:{SANS};font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;"
        f"color:{MUTED};border-bottom:2px solid {RULE};padding:6px 7px;text-align:{a};white-space:nowrap;\">{esc(h)}</th>"
        for h, a in zip(headers, aligns))
    body = []
    for i, r in enumerate(rows):
        bg = f"background:{TINT};" if tints and tints[i] else ""
        tds = "".join(
            f"<td style=\"font-family:{MONO};font-size:13px;color:{INK};{bg}border-bottom:1px solid {LINE};"
            f"padding:6px 7px;text-align:{a};white-space:nowrap;\">{c}</td>"
            for c, a in zip(r, aligns))
        body.append(f"<tr>{tds}</tr>")
    out = (f"<div style=\"overflow-x:auto;margin:10px 0 6px 0;\"><table style=\"width:100%;border-collapse:collapse;\">"
           f"<tbody><tr>{th}</tr>{''.join(body)}</tbody></table></div>")
    if note:
        out += (f"<div style=\"font-family:{SERIF};font-style:italic;font-size:13px;color:{MUTED};margin:0 0 14px 0;\">"
                f"{md_inline(note)}</div>")
    return out


def stat_strip(items) -> str:
    """Row of big-number boxes: [(value, label), ...]."""
    w = int(100 / len(items))
    cells = "".join(
        f"<td style=\"width:{w}%;vertical-align:top;text-align:center;padding:12px 6px;"
        f"border-left:{'0' if i == 0 else '1px solid ' + LINE};\">"
        f"<div style=\"font-family:{DISPLAY};font-size:30px;font-weight:bold;line-height:1;color:{INK};\">{esc(v)}</div>"
        f"<div style=\"font-family:{SANS};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED};"
        f"margin-top:6px;line-height:1.3;\">{esc(l)}</div></td>"
        for i, (v, l) in enumerate(items))
    return (f"<table style=\"width:100%;border-collapse:collapse;border-top:1px solid {RULE};border-bottom:1px solid {RULE};"
            f"margin:18px 0;\"><tbody><tr>{cells}</tr></tbody></table>")


# ---------------------------------------------------------------- page sections
def masthead(f, s) -> str:
    season = f["season"]
    year = (f["through"] or "2145")[:4]
    st = {r["team"]: r for r in f["standings"]}[f["team"]]
    place = [r["team"] for r in f["standings"]].index(f["team"]) + 1
    ord_ = {1: "1st", 2: "2nd", 3: "3rd"}.get(place, f"{place}th")
    left = (f"<div style=\"font-family:{SANS};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED};\">Record</div>"
            f"<div style=\"font-family:{DISPLAY};font-size:22px;font-weight:bold;color:{INK};\">{season['W']}-{season['L']}</div>")
    right = (f"<div style=\"font-family:{SANS};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED};\">{esc(f['division'])}</div>"
             f"<div style=\"font-family:{DISPLAY};font-size:22px;font-weight:bold;color:{INK};\">"
             f"{ord_}{'' if st['GB'] == 0 else ', ' + gb(st['GB']) + ' GB'}</div>")
    vol = roman(int(year) - 2000) if year.isdigit() else ""
    issue = s.get("issue_no") or f.get("issue_no") or ""
    return f"""
<table style="width:100%;border-collapse:collapse;"><tbody><tr>
<td style="width:22%;vertical-align:middle;text-align:left;padding:4px 0;">{left}</td>
<td style="vertical-align:middle;text-align:center;padding:4px 0;">
<div style="font-family:{SANS};font-size:10px;letter-spacing:4px;text-transform:uppercase;color:{RED};">The</div>
<div style="font-family:{DISPLAY};font-size:40px;line-height:1.02;font-weight:bold;color:{INK};letter-spacing:0.5px;">San Francisco<br>Seals Solicitor</div>
</td>
<td style="width:22%;vertical-align:middle;text-align:right;padding:4px 0;">{right}</td>
</tr></tbody></table>
<div style="border-top:3px solid {RULE};border-bottom:1px solid {RULE};height:3px;margin:8px 0 0 0;"></div>
<table style="width:100%;border-collapse:collapse;"><tbody><tr>
<td style="font-family:{SERIF};font-style:italic;font-size:12px;color:{MUTED};padding:6px 0;text-align:left;">Vol. {vol} · No. {esc(issue)}</td>
<td style="font-family:{SERIF};font-style:italic;font-size:12px;color:{MUTED};padding:6px 0;text-align:center;">“{esc(s.get('motto', 'All the Seals news fit to print'))}”</td>
<td style="font-family:{SERIF};font-style:italic;font-size:12px;color:{MUTED};padding:6px 0;text-align:right;">Through {esc(f['through_str'])}</td>
</tr></tbody></table>
<div style="border-top:1px solid {RULE};margin:0 0 6px 0;"></div>"""


def headline_block(s) -> str:
    return f"""
<div style="font-family:{SANS};font-size:12px;font-weight:bold;letter-spacing:3px;text-transform:uppercase;color:{RED};margin-top:22px;">{esc(s.get('kicker', 'Seals Beat'))}</div>
<h1 style="font-family:{DISPLAY};font-size:42px;line-height:1.05;font-weight:bold;color:{INK};margin:8px 0 12px 0;">{esc(s['headline'])}</h1>
<p style="font-family:{SERIF};font-style:italic;font-size:20px;line-height:1.4;color:#4a4237;margin:0 0 10px 0;">{md_inline(s['dek'])}</p>
<div style="font-family:{SANS};font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED};margin:0 0 20px 0;padding-bottom:12px;border-bottom:1px solid {LINE};">{esc(s.get('byline', 'By the Solicitor Seals desk'))} · Stats through games of {esc(f_through_short(s))}</div>"""


def f_through_short(s):
    return s.get("_through_short", "")


def games_table(f) -> str:
    rows, tints = [], []
    for x in f["log"]:
        rows.append([esc(x["date_str"]), esc(x["opp_label"]), esc(x["score"]),
                     f"<strong>{x['result']}</strong>" if x["won"] else x["result"],
                     esc(f"{x['starter']}"), esc(x["potg"])])
        tints.append(x["won"])
    extras = [x for x in f["log"] if x["innings"] > 9]
    note = "Seals' score listed first. Shaded rows are wins."
    if extras:
        note += " Inning count shown for extra-inning games."
    return table(["Date", "Opponent", "Score", "W/L", "Seals Starter", "Player of the Game"], rows,
                 ["left", "left", "right", "center", "left", "left"], tints, note)


def standings_table(f) -> str:
    prev = {r["team"]: r for r in (f.get("standings_prev") or [])}
    rows, tints = [], []
    for r in f["standings"]:
        move = ""
        if r["team"] in prev:
            d = prev[r["team"]]["GB"] - r["GB"] if r["GB"] or prev[r["team"]]["GB"] else 0
            move = "" if abs(d) < 0.01 else (f"▲ {abs(d):.1f}" if d > 0 else f"▼ {abs(d):.1f}")
        name = f"<strong>{esc(r['team'])}</strong>" if r["team"] == f["team"] else esc(r["team"])
        rows.append([name, f"{r['W']}-{r['L']}", avg3(r["pct"]), gb(r["GB"]), r["streak"], r["last10"],
                     f"{r['RS'] - r['RA']:+d}", move])
        tints.append(r["team"] == f["team"])
    return table(["Team", "W-L", "Pct", "GB", "Strk", "L10", "Diff", "Since last"], rows,
                 ["left"] + ["right"] * 7, tints,
                 "“Since last” is the change in games back since the previous issue.")


def batting_table(rows_src, n=9) -> str:
    rows = []
    for r in rows_src[:n]:
        rows.append([esc(r["name"]), f"{r['H']}-{r['AB']}", str(r["2B"]), str(r["HR"]), str(r["BI"]), str(r["R"]),
                     str(r["BB"]), str(r["SO"]), f"{avg3(r['AVG'])}/{avg3(r['OBP'])}/{avg3(r['SLG'])}"])
    return table(["Hitter", "H-AB", "2B", "HR", "RBI", "R", "BB", "SO", "AVG/OBP/SLG"], rows,
                 note="Hitters with 10+ plate appearances this sim, ranked by OPS. OBP from hits and walks only (box scores do not credit HBP).")


def pitching_table(rows_src) -> str:
    rows = []
    for r in rows_src:
        rec = f"{r['W']}-{r['L']}" + (f", {r['S']} SV" if r["S"] else "")
        rows.append([esc(r["name"]), f"{r['GS']}" if r["GS"] else "–", rec, r["IP"], str(r["H"]), str(r["ER"]),
                     str(r["BB"]), str(r["SO"]), f"{r['ERA']:.2f}"])
    return table(["Pitcher", "GS", "Dec", "IP", "H", "ER", "BB", "SO", "ERA"], rows)


LEADER_LABELS = {"HR": "Home runs", "RBI": "RBI", "AVG": "Batting avg", "OPS": "OPS", "SB": "Stolen bases",
                 "W": "Wins", "ERA": "ERA", "SO": "Strikeouts", "S": "Saves"}


def leaders_table(f, max_rank=10) -> str:
    rows = []
    for k, v in f["leaders"].items():
        for x in v["seals"]:
            if x["rank"] > max_rank:
                continue
            val = avg3(x["value"]) if k in ("AVG", "OPS") else (f"{x['value']:.2f}" if k == "ERA" else str(x["value"]))
            lead = v["top"][0]
            lv = avg3(lead["value"]) if k in ("AVG", "OPS") else (f"{lead['value']:.2f}" if k == "ERA" else str(lead["value"]))
            leader = "—" if lead["name"] == x["name"] or x["rank"] == 1 and lead["value"] == x["value"] and lead["name"] == x["name"] else f"{esc(lead['name'])} {lv}"
            if x["rank"] == 1 and lead["name"] != x["name"]:
                leader = f"tied w/ {esc(lead['name'])}"
            rows.append([LEADER_LABELS[k], esc(x["name"]), val, f"#{x['rank']}", leader])
    if not rows:
        return ""
    return table(["Category", "Seal", "Total", "MLBC rank", "League leader"], rows,
                 ["left", "left", "right", "right", "left"],
                 note="Ranks are league-wide across all 30 clubs. Rate stats require 3.1 PA or 1 IP per team game.")


def footer(f, s) -> str:
    extra = s.get("footer", "")
    return (f"<div style=\"border-top:3px double {RULE};margin-top:26px;padding-top:10px;font-family:{SERIF};font-style:italic;"
            f"font-size:12px;line-height:1.5;color:{MUTED};\">Every figure in this issue is counted from MLBC box scores through "
            f"{esc(f['through_str'])}. Pythagorean record uses a 1.83 exponent. {md_inline(extra)}</div>")


# ---------------------------------------------------------------- assemble
def render(f, s) -> str:
    from datetime import date
    d = date.fromisoformat(f["through"])
    s["_through_short"] = f"{d.strftime('%B')} {d.day}"
    p_ = f["period"]
    se = f["season"]
    blocks = [masthead(f, s), headline_block(s)]
    for i, para in enumerate(s["lead"]):
        blocks.append(p(para, first=(i == 0)))

    blocks.append(section_head(s.get("games_heading", "The sim, game by game")))
    blocks.append(games_table(f))

    strip = s.get("stat_strip") or [
        (f"{p_['W']}-{p_['L']}", "This sim"),
        (f"{p_['home'][0]}-{p_['home'][1]} / {p_['road'][0]}-{p_['road'][1]}", "Home / road"),
        (f"{se['RS'] - se['RA']:+d}", "Season run diff."),
        (f"{se['one_run'][0]}-{se['one_run'][1]}", "One-run games"),
    ]
    blocks.append(stat_strip([tuple(x) for x in strip]))

    for sec in s.get("sections", []):
        if sec.get("label"):
            blocks.append(section_head(sec["label"]))
        if sec.get("heading"):
            blocks.append(sub_head(sec["heading"]))
        for para in sec.get("paragraphs", []):
            blocks.append(p(para))
        if sec.get("insert") == "standings":
            blocks.append(standings_table(f))
        elif sec.get("insert") == "batting":
            blocks.append(batting_table(f["batting_period"]))
        elif sec.get("insert") == "pitching":
            blocks.append(pitching_table(f["pitching_period"]))
        elif sec.get("insert") == "leaders":
            blocks.append(leaders_table(f))

    blocks.append(footer(f, s))
    inner = "\n".join(blocks)
    return (f"<div style=\"max-width:760px;margin:0 auto;background:{PAPER};color:{INK};padding:22px 24px 18px 24px;"
            f"border:1px solid {LINE};font-family:{SERIF};\">\n{inner}\n</div>")


def page(fragment: str, title: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>body{{margin:0;padding:24px 12px;background:#e9e2d0;}} @media (max-width:600px){{h1{{font-size:32px!important;}}}}</style>
</head><body>
{fragment}
</body></html>
"""


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    f = json.load(open(os.path.join(folder, "issue_facts.json")))
    s = json.load(open(os.path.join(folder, "story.json")))
    frag = render(f, s)
    with open(os.path.join(folder, "post.html"), "w") as fh:
        fh.write(frag)
    title = f"Seals Solicitor No. {s.get('issue_no', '')}: {s['headline']}"
    with open(os.path.join(folder, "page.html"), "w") as fh:
        fh.write(page(frag, title))
    print(f"Wrote {folder}/post.html ({len(frag):,} chars) and page.html")


if __name__ == "__main__":
    main()
