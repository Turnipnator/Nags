"""Backfill historical results P&L through database.settle().

Rows before id 707 were settled by hand: placed rows split the E/W stake
correctly, winning rows were logged as `stake_pts * SP` (as if win-only),
which overstates every winner. This re-settles them from Racing API results.

Dry-run by default. Pass --apply to write.
"""
import json
import os
import re
import sqlite3
import sys
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from src.database import settle, place_terms  # noqa: E402

DB = sys.argv[1] if len(sys.argv) > 1 else "hist.db"
APPLY = "--apply" in sys.argv
CACHE = Path("apicache")
CACHE.mkdir(exist_ok=True)

USER = os.environ.get("RACING_API_USERNAME", "")
PWD = os.environ.get("RACING_API_PASSWORD", "")
if not USER or not PWD:
    sys.exit("set RACING_API_USERNAME / RACING_API_PASSWORD")


def fetch_day(d):
    """All races for a date, paginated. Uses curl -- urllib gets 403 (UA), and
    limit>50 is rejected 422, so page through `total` in 50s."""
    f = CACHE / f"{d}.json"
    if f.exists():
        return json.loads(f.read_text())
    races, skip, total = [], 0, None
    while True:
        url = (f"https://api.theracingapi.com/v1/results?start_date={d}"
               f"&end_date={d}&limit=50&skip={skip}")
        page = None
        for attempt in range(6):
            out = subprocess.run(
                ["curl", "-sS", "-u", f"{USER}:{PWD}", url],
                capture_output=True, text=True, timeout=90,
            )
            try:
                p = json.loads(out.stdout)
            except json.JSONDecodeError:
                p = None
            # The API rate-limits under rapid calls and answers with an EMPTY
            # body (total=None, results=[]) rather than an error code. Caching
            # that as "no races" silently drops a whole day, so treat it as a
            # failure and back off.
            if p is not None and p.get("total") is not None:
                page = p
                break
            time.sleep(2 * (attempt + 1))
        if page is None:
            raise RuntimeError(f"{d}: no valid response after retries")
        races.extend(page.get("results", []))
        total = page.get("total", len(races))
        skip += 50
        if len(races) >= total or not page.get("results"):
            break
        time.sleep(1)
    if not races:
        raise RuntimeError(f"{d}: API returned zero races -- refusing to cache")
    data = {"results": races, "total": total}
    f.write_text(json.dumps(data))
    time.sleep(1)
    return data


def norm_course(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", "", s)          # drop (AW) / (IRE)
    s = re.sub(r"[^a-z]", "", s)
    # The API uses the full racecourse name where our sheet uses the short one.
    return {"epsom": "epsomdowns"}.get(s, s)


def norm_horse(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", "", s)          # drop country suffix
    return re.sub(r"[^a-z0-9]", "", s)


def to12(t):
    """'20:00' -> '8:00'; '15:42' -> '3:42'. API uses 12h with no am/pm."""
    m = re.match(r"(\d{1,2}):(\d{2})", (t or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), m.group(2)
    if h > 12:
        h -= 12
    return f"{h}:{mi}"


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """SELECT s.id, date(s.created_at) d, s.race_time, s.race_name, s.horse,
              s.each_way, s.stake_pts, s.odds_guide, s.selection_type,
              r.id rid, r.finish_position, r.result, r.sp_odds, r.pnl_pts
       FROM results r JOIN selections s ON s.id = r.selection_id
       WHERE r.selection_id < 707
       ORDER BY s.id"""
).fetchall()

by_date = defaultdict(list)
for r in rows:
    by_date[r["d"]].append(r)

updates, unmatched, changed = [], [], []
relocated, voided, seen_bets = [], [], {}
old_total = new_total = 0.0

for d in sorted(by_date):
    races = fetch_day(d).get("results", [])
    idx = {}
    for rc in races:
        idx[(norm_course(rc.get("course")), rc.get("off"))] = rc

    for r in by_date[d]:
        course = (r["race_name"] or "").split(" - ")[0]
        key = (norm_course(course), to12(r["race_time"]))
        target = norm_horse(r["horse"])
        rc = idx.get(key)
        run = None
        if rc is not None:
            run = next((x for x in rc.get("runners", [])
                        if norm_horse(x.get("horse")) == target), None)

        if run is None:
            # The stored race_time can be wrong two ways: a plain sheet error,
            # or the pre-CHECK-0b cross-race NB bug that filed a horse under a
            # DIFFERENT race's time. The horse name is the reliable field, so
            # fall back to searching that course's whole card -- but ONLY if the
            # horse ran exactly once there that day. Ambiguity => leave alone.
            # Search the whole day's racing, not just that course -- the
            # cross-race NB bug could file a horse under another COURSE
            # entirely (Mahons Glory, 18 Jul: filed Newbury 2:25, actually ran
            # Market Rasen 2:45). Require a UNIQUE hit; ambiguity => leave alone.
            cands = [(rc2, x) for rc2 in idx.values()
                     for x in rc2.get("runners", [])
                     if norm_horse(x.get("horse")) == target]
            if len(cands) == 1:
                rc, run = cands[0]
                relocated.append(
                    (r, f"{key[0]} {key[1]}",
                     f"{norm_course(rc.get('course'))} {rc.get('off')}"))
            else:
                unmatched.append(
                    (r, "race not found" if idx.get(key) is None
                     else "horse not in race", key))
                continue

        n = len(rc.get("runners", []))
        is_hcap = "handicap" in (rc.get("race_name", "") or "").lower()

        pos_raw = str(run.get("position", "")).strip()
        pos = int(pos_raw) if pos_raw.isdigit() else None   # PU/F/UR -> unplaced
        if pos is None:
            pos = n + 1                                     # non-completion = beaten

        sp = run.get("sp") or r["sp_odds"] or ""

        s = settle(
            stake_pts=r["stake_pts"], each_way=bool(r["each_way"]),
            finish_position=pos, sp_odds=sp, num_runners=n,
            is_handicap=is_hcap, morning_odds=r["odds_guide"] or "", bog=True,
        )
        # One horse can legitimately appear once per race. A SECOND row for the
        # same (race, horse) is a duplicate artefact of the pre-CHECK-0b bugs
        # (cross-race NB, or two selections in one race) -- no separate bet
        # existed, so settle it VOID rather than double-count the result.
        dkey = (rc.get("race_id") or (key[0], rc.get("off")), target)
        if dkey in seen_bets:
            voided.append((r, seen_bets[dkey]))
            old_total += r["pnl_pts"]
            updates.append((r["rid"], None, "void", "-", 0.0, 0.0))
            continue
        seen_bets[dkey] = r["id"]

        old_total += r["pnl_pts"]
        new_total += s["pnl_pts"]
        delta = s["pnl_pts"] - r["pnl_pts"]
        updates.append((r["rid"], pos if pos_raw.isdigit() else None,
                        s["result"], sp, s["returns_pts"], s["pnl_pts"]))
        if abs(delta) > 0.005 or s["result"] != r["result"]:
            changed.append((r, s, delta, n, is_hcap, pos_raw))

print(f"rows examined : {len(rows)}")
print(f"matched       : {len(updates)}")
print(f"UNMATCHED     : {len(unmatched)}")
print(f"changed       : {len(changed)}")
print()
print(f"old total pnl : {old_total:+.3f} pts")
print(f"new total pnl : {new_total:+.3f} pts")
print(f"DELTA         : {new_total - old_total:+.3f} pts")
void_effect = -sum(r["pnl_pts"] for r, _ in voided)
print(f"  of which: voided duplicates {void_effect:+.3f} | re-settlement "
      f"{(new_total - old_total) - void_effect:+.3f}")
print()

if relocated:
    print("=== RELOCATED (stored race_time wrong; matched by horse on same card) ===")
    for r, was, now in relocated:
        print(f"  id{r['id']:4d} {r['d']} {r['horse'][:22]:22s} {r['selection_type']:10s} stored {was} -> actual {now}")
    print()

if voided:
    print("=== VOIDED (duplicate row for same horse+race; no separate bet existed) ===")
    for r, keeper in voided:
        print(f"  id{r['id']:4d} {r['d']} {r['horse'][:22]:22s} {r['selection_type']:10s} duplicate of id{keeper} | was {r['pnl_pts']:+.3f}")
    print()

if unmatched:
    print("=== UNMATCHED (left untouched) ===")
    for r, why, key in unmatched:
        print(f"  id{r['id']:4d} {r['d']} {r['race_time']:>5s} {r['horse'][:22]:22s} {why} {key}")
    print()

print("=== CHANGED (top 25 by absolute delta) ===")
for r, s, delta, n, hc, pos_raw in sorted(changed, key=lambda x: -abs(x[2]))[:25]:
    print(f"  id{r['id']:4d} {r['horse'][:20]:20s} {r['selection_type']:10s} "
          f"{'EW' if r['each_way'] else 'W '} stake{r['stake_pts']:4.1f} "
          f"pos{pos_raw:>3s}/{n:2d}{'H' if hc else ' '} "
          f"{r['result']:6s}->{s['result']:6s} "
          f"{r['pnl_pts']:+7.3f} -> {s['pnl_pts']:+7.3f}  ({delta:+.3f})")

wins = [c for c in changed if c[1]["result"] == "won"]
print()
print(f"winners re-settled: {len(wins)}, total delta on winners: "
      f"{sum(c[2] for c in wins):+.3f} pts")

if "--sql" in sys.argv:
    with open("backfill.sql", "w") as fh:
        fh.write("BEGIN;\n")
        for rid, pos, res, sp, ret, pnl in updates:
            posv = "NULL" if pos is None else str(pos)
            fh.write(
                f"UPDATE results SET finish_position={posv}, result='{res}', "
                f"sp_odds='{sp.replace(chr(39), chr(39)*2)}', returns_pts={ret}, "
                f"pnl_pts={pnl} WHERE id={rid};\n")
        fh.write("COMMIT;\n")
    print(f"\nwrote backfill.sql ({len(updates)} updates)")

if APPLY:
    for rid, pos, res, sp, ret, pnl in updates:
        conn.execute(
            "UPDATE results SET finish_position=?, result=?, sp_odds=?, "
            "returns_pts=?, pnl_pts=? WHERE id=?",
            (pos, res, sp, ret, pnl, rid),
        )
    conn.commit()
    print(f"\nAPPLIED {len(updates)} updates to {DB}")
else:
    print("\n(dry run — nothing written; pass --apply)")
