"""Pick audit: was each primary selection warranted? (11 Sep 2026)

For every live bot primary (nap / next_best / selection) in a ledger export,
re-score its race with the LIVE scorer from the harvest cache and print, per
pick: the deterministic anchor and its component split, the judgement layer's
adjusted score and the delta, where the pick ranked in its own race on
deterministic score, and how the pick, the named DANGER, the deterministic
top scorer and the market favourite actually finished.

Deterministic layer only, no Rule 18b enrichment (so anchors for 18b horses
read a little LOW versus the live run), no Sporting Life, no LLM.

Usage:
  .venv/bin/python scripts/pick_audit.py <ledger.json> [--from 2026-08-17]
ledger.json rows: [date, race_time, race_name, horse, type, odds, score, danger,
                   each_way, stake_pts, result, finish_position, pnl_pts]
"""
import argparse
import glob
import gzip
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.scorer as SC  # noqa: E402
import src.analyst as A  # noqa: E402
from src.scraper import Scraper  # noqa: E402

HARVEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "harvest")
_CC = re.compile(r"\s*\([A-Z]{2,4}\)\s*$")


def norm(n):
    return re.sub(r"[^a-z0-9 ]", "", _CC.sub("", (n or "")).lower()).strip()


def load_day(ds):
    cf = os.path.join(HARVEST, f"{ds}_cards.json.gz")
    if not os.path.exists(cf):
        return None, {}
    cards = json.load(gzip.open(cf))
    res = {}
    for rf in sorted(glob.glob(os.path.join(HARVEST, f"{ds}_res_*.json.gz"))):
        for race in json.load(gzip.open(rf)).get("results", []):
            key = (norm(race.get("course")), race.get("off"))
            runners = {}
            for rn in race.get("runners", []):
                p = str(rn.get("position", "")).strip()
                try:
                    spd = float(rn.get("sp_dec"))
                except (TypeError, ValueError):
                    spd = None
                runners[norm(rn.get("horse"))] = (int(p) if p.isdigit() else None, spd)
            res[key] = runners
    return cards, res


def meetings_from(ds, cards):
    sc = Scraper()
    sc._api_get = lambda endpoint, max_attempts=3: cards if endpoint.startswith("/racecards/pro") else None
    y, m, d = (int(x) for x in ds.split("-"))
    return sc.fetch_all_uk_irish_races(date(y, m, d))


def to12(t):
    h, mi = t.split(":")
    h = int(h)
    return f"{h - 12 if h > 12 else h}:{mi}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--from", dest="d_from", default="2026-08-17")
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.ledger)) if r[0] >= a.d_from and r[4] in ("nap", "next_best", "selection")]
    by_day = {}
    for r in rows:
        by_day.setdefault(r[0], []).append(r)

    out = []
    for ds in sorted(by_day):
        cards, res = load_day(ds)
        if cards is None:
            print(f"# {ds}: no cached card"); continue
        meetings = meetings_from(ds, cards)
        for r in by_day[ds]:
            d, rtime, rname, horse, typ, odds, llm, danger, ew, stk, result, pos, pnl = r
            course = norm(rname.split(" - ")[0])
            race = next((rc for m in meetings for rc in m.races
                         if norm(m.course) == course and rc.time.strip() == rtime.strip()), None)
            if race is None:
                print(f"# {ds} {rtime} {rname[:30]}: race not found in cache"); continue
            scored = SC.Scorer().score_race(race)
            ranked = sorted(scored, key=lambda s: -s.total)
            mine = next((s for s in scored if norm(s.runner.name) == norm(horse)), None)
            if mine is None:
                print(f"# {ds} {rtime} {horse}: not in scored field"); continue
            rank = ranked.index(mine) + 1
            rr = res.get((course, to12(rtime)), {})
            def fin(name):
                return rr.get(norm(name), (None, None))[0]
            def sp(name):
                return rr.get(norm(name), (None, None))[1]
            fav = min(rr.items(), key=lambda kv: (kv[1][1] is None, kv[1][1] or 999))[0] if rr else None
            danger_name = (danger or "").split(" - ")[0].strip()
            top = ranked[0]
            comp = f"F{mine.form_score:.0f} C{mine.course_score:.0f} G{mine.going_score:.0f} D{mine.distance_score:.0f} Cl{mine.class_score:.0f} Sp{mine.speed_score:.0f} W{mine.weight_score:.0f} J{mine.jockey_score:.0f} T{mine.trainer_score:.0f} E{mine.edge_bonus:+.0f}"
            cgd = mine.course_score + mine.going_score + mine.distance_score
            out.append(dict(date=ds, time=rtime, course=rname.split(" - ")[0][:14], horse=horse, typ=typ, odds=odds,
                            det=round(mine.total, 1), llm=llm, delta=round((llm or 0) - mine.total, 1), rank=rank,
                            n=len(scored), cgd=cgd, comp=comp, pos=pos, danger=danger_name, danger_pos=fin(danger_name),
                            top=top.runner.name, top_odds=top.runner.odds, top_pos=fin(top.runner.name),
                            fav=fav, fav_pos=fin(fav) if fav else None, is_fav=(norm(horse) == fav), pnl=pnl, result=result,
                            pick_sp=sp(horse), danger_sp=sp(danger_name), top_sp=sp(top.runner.name)))

    hdr = f"{'date':10} {'time':5} {'course':14} {'pick':18} {'slot':9} {'odds':5} {'det':5} {'llm':4} {'Δ':5} {'rk':3} {'CGD':3} {'fin':3} | {'danger':18} {'fin':3} | {'det top':18} {'fin':3} | fav?"
    print(hdr)
    for o in out:
        print(f"{o['date']:10} {o['time']:5} {o['course']:14} {o['horse'][:18]:18} {o['typ']:9} {str(o['odds']):5} {o['det']:5} {o['llm'] or 0:4.0f} {o['delta']:+5.1f} {o['rank']:>2}/{o['n']:<2} {o['cgd']:3.0f} {str(o['pos'] or '-'):3} | {o['danger'][:18]:18} {str(o['danger_pos'] or '-'):3} | {o['top'][:18]:18} {str(o['top_pos'] or '-'):3} | {'FAV' if o['is_fav'] else ''}")
        print(f"{'':10} {'':5} {'':14} └ {o['comp']}")
    settled = [o for o in out if o["result"] not in (None, "nr", "void")]
    print(f"\npicks audited: {len(out)} (settled {len(settled)})")
    print(f"pick was deterministic #1 in its race: {sum(1 for o in settled if o['rank']==1)} / {len(settled)}")
    print(f"pick WON: {sum(1 for o in settled if o['pos']==1)} | named DANGER won: {sum(1 for o in settled if o['danger_pos']==1)} | deterministic top scorer won: {sum(1 for o in settled if o['top_pos']==1)} | market favourite won: {sum(1 for o in settled if o['fav_pos']==1)}")
    print(f"pick finished behind its named DANGER: {sum(1 for o in settled if o['danger_pos'] and o['pos'] and o['danger_pos'] < o['pos'])} / {sum(1 for o in settled if o['danger_pos'] and o['pos'])}")
    print(f"pick was the market favourite: {sum(1 for o in settled if o['is_fav'])} / {len(settled)}")
    d = [o["delta"] for o in settled]
    print(f"LLM adjusted minus deterministic: mean {sum(d)/len(d):+.1f}, lifted >=+5 on {sum(1 for x in d if x>=5)}, cut <=-5 on {sum(1 for x in d if x<=-5)}")
    lifted = [o for o in settled if o["delta"] >= 5]
    print(f"  lifted >=+5 picks: {len(lifted)} won {sum(1 for o in lifted if o['pos']==1)} pnl {sum(o['pnl'] for o in lifted):+.2f}")
    hi = [o for o in settled if o["cgd"] >= 30]; lo = [o for o in settled if o["cgd"] < 30]
    def win1pt(g, pos_key, sp_key):
        g = [o for o in g if o[sp_key] and o[pos_key]]
        return len(g), sum((o[sp_key] - 1.0) if o[pos_key] == 1 else -1.0 for o in g), (sum(o[sp_key] for o in g) / len(g) if g else 0)
    for label, pk, sk in (("our PICK", "pos", "pick_sp"), ("named DANGER", "danger_pos", "danger_sp"), ("det TOP scorer", "top_pos", "top_sp")):
        n, pl, avg = win1pt(settled, pk, sk)
        print(f"1pt WIN at SP on {label:15}: n={n:2} P&L {pl:+7.2f}pt  ROI {100*pl/max(n,1):+6.1f}%  avg SP {avg:.2f}")
    print(f"C+G+D >=30: n={len(hi)} won {sum(1 for o in hi if o['pos']==1)} pnl {sum(o['pnl'] for o in hi):+.2f} | <30: n={len(lo)} won {sum(1 for o in lo if o['pos']==1)} pnl {sum(o['pnl'] for o in lo):+.2f}")


if __name__ == "__main__":
    main()
