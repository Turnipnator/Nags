---
name: healthcheck
description: Comprehensive health check on the Nags horse racing bot — container, Racing API, judgement layer, ledger integrity, backups, live-money safety and overdue paper-trade reviews
---

# Nags Horse Racing Bot — Health Check

Work through each section, run independent commands in parallel, and finish with the summary
dashboard in §15. Report what you actually find — if a check can't be run, say so rather than
omitting it.

## ⛔ HARD RULES FOR THIS SKILL

- **NEVER fire `/run`.** It writes the day's card and the Betfair bot acts on it with real money.
  A health check is read-only.
- **NEVER rebuild any container except `horse-racing-bot` or `betfair-bot`.** `trading-bot`,
  `ig-trading-bot`, `ib-gateway`, `postgres`/`betfair-db` are other people's money.
- **NEVER copy a SQLite DB with `cp`.** Both DBs run in WAL mode; `cp` silently captures a stale
  main file (this cost 8 days of ledger in July). Always `sqlite3 <db> ".backup '<file>'"`.
- Read-only queries only. Do not INSERT, UPDATE, DELETE or migrate anything from a health check.

## Environment

| | |
|---|---|
| VPS | `149.102.144.190`, key `~/.ssh/id_ed25519_vps` |
| Nags container | `horse-racing-bot`, path `/root/horse-racing-bot` |
| Nags DB | `/app/data/racing.db` in-container = `/root/horse-racing-bot/data/racing.db` on host |
| Betfair container | `betfair-bot`, path `/opt/betfair-bot`, DB `/opt/betfair-bot/data/betfair_bot.db` |
| Local repo | `/Users/paulturner/horse-racing-bot` (deploy by **scp**, not git pull) |
| Rules file | `/Users/paulturner/Horses/CLAUDE.md` |
| Remote | `git@github.com:Turnipnator/Nags.git` |

Prefix SSH with `-q -o LogLevel=ERROR` to suppress banner noise.

---

## 1. PROCESS STATUS

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker ps --format '{{.Names}}\t{{.Status}}\t{{.RunningFor}}' | grep -E 'horse-racing-bot|betfair-bot' && docker inspect -f '{{.Name}} started {{.State.StartedAt}} restarts={{.RestartCount}}' horse-racing-bot betfair-bot"
```

Flag: restart count rising, or a container up far longer than the last deploy (stale code).
⚠ Restarting `betfair-bot` mid-day resets its in-memory `_markets_with_bets` dedup — it can re-bet
a market it already backed. Note any restart that happened during racing hours.

## 2. LOG ANALYSIS

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs --since 48h horse-racing-bot 2>&1 | grep -iE 'error|warn|fail|fatal|exception|traceback' | grep -v getUpdates | tail -30"
```

Classify: Racing API 4xx/5xx · Anthropic errors · parser/None propagation · scheduler misses ·
Telegram send failures.

## 3. ⚠ JUDGEMENT-LAYER SILENT FAILURE (highest-value check on this page)

This has broken **twice** and both times the bot kept producing a card that looked fine while the
entire CLAUDE.md judgement layer was gone — picks were raw deterministic scorer output.

- 5 Jun 2026: `temperature=0` sent to a model that deprecates it → HTTP 400 → fallback
- 27 Jul 2026: Opus 5 leads with a ThinkingBlock → `content[0].text` raised → fallback

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs --since 7d horse-racing-bot 2>&1 | grep -iE 'programmatic fallback|Claude API HTTP|BadRequest|no selections' | tail -15"
```

**The reliable tell is in the scores themselves: LLM scores are INTEGERS, fallback scores end in `.1`.**

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && docker compose exec -T horse-racing-bot python3 -c \"
import sqlite3
c = sqlite3.connect('/app/data/racing.db')
rows = c.execute('SELECT date(created_at), horse, score FROM selections WHERE superseded_at IS NULL AND score > 0 ORDER BY id DESC LIMIT 20').fetchall()
bad = [r for r in rows if abs(r[2] - round(r[2])) > 0.001]
print('recent picks:', len(rows), '| fractional (fallback) scores:', len(bad))
for r in bad[:5]: print('  FALLBACK?', r)
\""
```

Also confirm the model is still pinned:

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "grep JUDGEMENT_MODEL /root/horse-racing-bot/.env"
```

Expect `claude-opus-5`. Revert lever if scores inflate (NAPs at long odds, scores >90):
`JUDGEMENT_MODEL=claude-opus-4-8`.

## 4. RACING API HEALTH

The API renamed its premium fields on 16 Jun 2026 — the OLD keys still exist but return empty.
Three cards were scored blind before this was caught, so **check the data is populated, not just
that the call succeeded**.

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && docker compose exec -T horse-racing-bot python3 -c \"
import os, httpx, datetime
u=os.getenv('RACING_API_USERNAME'); p=os.getenv('RACING_API_PASSWORD')
d=datetime.date.today().isoformat()
r=httpx.get(f'https://api.theracingapi.com/v1/racecards/pro?date={d}', auth=(u,p), timeout=30)
print('HTTP', r.status_code)
rc=r.json().get('racecards',[])
gb=[x for x in rc if x.get('region') in ('GB','IRE')]
runners=[y for x in gb for y in x.get('runners',[])]
pct=lambda k: round(100*sum(1 for y in runners if y.get(k) not in (None,'',0))/max(len(runners),1))
print('races', len(gb), 'runners', len(runners))
for k in ('comment','performance_rating','speed_rating','ofr','trainer_14_days','odds'):
    print(f'  {k:20} {pct(k):3}% populated')
\""
```

⚠ Use **httpx**, not `urllib` — the API answers urllib with **HTTP 403** on User-Agent. Other API
traps: `limit > 50` returns 422, and under rate limiting `/results` returns an **empty body**
rather than an error code, so a day silently joins zero races.

Flag: `comment` / `performance_rating` / `speed_rating` near 0% — that is the schema having moved
again, not a lapsed subscription. Legacy names were `spotlight` / `rpr` / `ts`.
`comment` sitting around 60–75% is normal (not every runner gets analyst text); near 0% is not.

## 5. LEDGER INTEGRITY (racing.db)

The nightly settler only started running in June; **Mar–May were 0–18% settled and nobody noticed
for two months.** Coverage is the check that would have caught it.

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && docker compose exec -T horse-racing-bot python3 -c \"
import sqlite3
c=sqlite3.connect('/app/data/racing.db')
q=lambda s: c.execute(s).fetchall()
print('live selections   ', q('SELECT COUNT(*) FROM selections WHERE superseded_at IS NULL')[0][0])
print('superseded        ', q('SELECT COUNT(*) FROM selections WHERE superseded_at IS NOT NULL')[0][0])
print('unsettled (live)  ', q('SELECT COUNT(*) FROM selections s LEFT JOIN results r ON r.selection_id=s.id WHERE r.id IS NULL AND s.superseded_at IS NULL')[0][0])
print()
print('monthly settle coverage:')
for m,t,s in q('''SELECT strftime('%Y-%m',s.created_at) m, COUNT(*) t, SUM(CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END) s FROM selections s LEFT JOIN results r ON r.selection_id=s.id WHERE s.superseded_at IS NULL GROUP BY m ORDER BY m'''):
    print(f'  {m}  {s}/{t}  {round(100*s/max(t,1))}%')
print()
for src, in q('SELECT DISTINCT COALESCE(source,\\\"bot\\\") FROM selections'):
    r=q(f'''SELECT COUNT(*), ROUND(SUM(r.pnl_pts),2), ROUND(SUM(s.stake_pts),2) FROM selections s JOIN results r ON r.selection_id=s.id WHERE s.superseded_at IS NULL AND COALESCE(s.source,\\\"bot\\\")=\\\"{src}\\\"''')[0]
    roi = round(100*r[1]/r[2],2) if r[2] else 0
    print(f'{src:8} n={r[0]:4} P&L {r[1]:+8}pt  staked {r[2]}pt  ROI {roi:+.2f}%')
\""
```

**Expect ~100% coverage in every month and 0 unsettled.** Any month dropping below ~95% means the
settler is failing silently — re-run `scripts/backfill_results.py` (it upserts on `selection_id`,
safe to repeat).

⚠ Report bot and manual ROI **separately**. Authoritative bot figure is at BOG; never quote an
SP-based ROI (BOG is worth ~9 points to us).

## 6. DUPLICATE-CARD / TWO-NAP CHECK

On 1 Aug 2026 two `/run`s in one day produced 8 selections, **two NAPs and £245 staked** for
−£116. A later run should now SUPERSEDE the earlier card.

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && docker compose exec -T horse-racing-bot python3 -c \"
import sqlite3
c=sqlite3.connect('/app/data/racing.db')
print('BOT days breaching the Operating Policy cap (last 30d):')
for d,n,naps in c.execute('''SELECT date(created_at) d, COUNT(*) n, SUM(CASE WHEN selection_type='nap' THEN 1 ELSE 0 END) naps FROM selections WHERE superseded_at IS NULL AND COALESCE(source,'bot')='bot' AND selection_type IN ('nap','next_best','selection') AND created_at > date('now','-30 day') GROUP BY d HAVING n>6 OR naps>1 ORDER BY d'''):
    print(f'  BREACH {d}: {n} top-level picks, {naps} NAP(s)')
print('  (no rows above = clean)')
\""
```

⚠ **Count only TOP-LEVEL bot rows.** The cap of 6/day and 1 NAP applies to
`nap` + `next_best` + `selection`. **`race_nb` rows are per-race second strings, not separate
top-level picks**, and `source='manual'` is Claude's own card kept as a separate ledger — counting
either makes this fire on perfectly normal days.

## 7. BACKUPS — VPS NIGHTLY + MAC OFF-SITE

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "crontab -l | grep -i backup; echo '--- recent ---'; ls -lt /root/db-backups/*.gz 2>/dev/null | head -6; echo '--- last log ---'; tail -12 /root/db-backups/backup.log"
```

```bash
ls -lt ~/Backups/nags-vps/*.gz 2>/dev/null | head -5; echo '--- pull log ---'; tail -12 ~/Backups/nags-vps/pull.log 2>/dev/null; launchctl list | grep -i nags-backup
```

Flag: newest VPS snapshot older than ~26h, newest Mac copy older than ~48h, or any `FAIL` /
quarantine line. ⚠ A closed laptop lid delays the pull to next wake — that is a delay, not a miss.
Retention is 14d on the VPS, 60d on the Mac. Prune only happens **after** a snapshot verifies.

## 8. ⚠ LIVE-MONEY SAFETY (Betfair)

`nags_place` places **real** place-only bets. `nags_back` and `nags_lay_fav` are forced to paper —
this is a hardcoded frozenset, not an env var, so a bad deploy can silently flip it.

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "sed -n '108,112p' /opt/betfair-bot/src/strategies/horse_racing.py"
```

**Must contain both `nags_lay_fav` and `nags_back`.** If either is missing, that strategy is live on
real money — treat as P1 and tell Paul immediately.

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs --since 48h betfair-bot 2>&1 | grep -iE 'not logged in|session|placed|PAPER|LIVE' | tail -20"
```

Also confirm the Betfair side is reading a current card — `NagsReader.load_today` filters
`superseded_at IS NULL`, and a mis-keyed pick silently places **no** bet (logged at debug only).

## 9. TODAY'S CARD QUALITY

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && docker compose exec -T horse-racing-bot python3 -c \"
import sqlite3
c=sqlite3.connect('/app/data/racing.db')
for r in c.execute('''SELECT race_time, horse, selection_type, odds_guide, score, each_way, stake_pts FROM selections WHERE date(created_at)=date('now') AND superseded_at IS NULL ORDER BY race_time'''):
    print(' ', r)
\""
```

Sanity: ≤6 top-level picks, ≤1 NAP, NAP ≥75 and ≤10/1, NB-of-day ≥70 and ≤14/1, nothing at evens or
shorter, nothing at 11/1+ (F2 drops those), E/W only where a place market exists (5+ runners).

**An empty result is normal** — card generation is on-demand, not scheduled. Confirm the scheduler
state rather than assuming a failure:

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs --since 48h horse-racing-bot 2>&1 | grep -iE 'auto-schedule|scheduled:|bot ready' | tail -5"
```

Expect `Auto-schedule DISABLED` (picks come from `/run` on demand) plus the nightly **results
settler at 21:15 Europe/London**. If the settler line is missing, §5 coverage will start to rot —
that is the failure mode that went unnoticed for two months.

## 10. COMPLIANCE + SHADOW FILTER ACTIVITY

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs --since 7d horse-racing-bot 2>&1 | grep -E 'FILTER|FILTER-SHADOW|CROSS-RACE|DUPLICATE RACE|T14 SMALL SAMPLE|MARGIN GUARD|GATE FIX|DROPPED-' | tail -30"
```

Note which shadow filters fired and how often. Live: **F2 LONGSHOT** (drops ≥11/1).
Shadow (log only): **F1 HIGHSCORE**, **F3 SHORT-PREMIUM-NAP**, **F4 TOP2-REDFLAG**.

## 11. OVERDUE PAPER-TRADE REVIEWS

Check today's date against these and flag anything due. This is the section most likely to be
genuinely actionable — these are easy to forget and each has a written revert trigger in CLAUDE.md.

| Due | Item | Trigger to check |
|---|---|---|
| 11 Aug 2026 | **F1 HIGHSCORE** review | 85+ band vs 75–80 band; expected to die |
| 12 Aug 2026 | Going-gate spatial phrases | 2+ NAPs beaten on a card whose going actually moved |
| 13 Aug 2026 | T14 min-runs guard + edge-block removals | 3+ suppressed horses winning |
| 16 Aug 2026 | **F3 SHORT-PREMIUM-NAP** review | sub-4/1 premium NAP cell |
| 18 Aug 2026 | Re-run `swap_gap.py` (script is ephemeral — recreate) | needs `race_nb` rows with `score>0` |
| 1 Sep 2026 | Class-floor unclassed counter | revert at **3** blocked winners (currently **1**) |
| 10 Sep 2026 | **F4 TOP2-REDFLAG** review | flagged races must underperform **on our own picks** |

## 12. CODE DRIFT (local ↔ GitHub ↔ VPS)

```bash
cd /Users/paulturner/horse-racing-bot && git fetch -q origin && echo "local  $(git rev-parse --short HEAD)  origin $(git rev-parse --short origin/main)" && git status --porcelain | head
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "md5sum /root/horse-racing-bot/src/analyst.py /root/horse-racing-bot/src/scorer.py /root/horse-racing-bot/config/settings.py"
md5 -q /Users/paulturner/horse-racing-bot/src/analyst.py /Users/paulturner/horse-racing-bot/src/scorer.py /Users/paulturner/horse-racing-bot/config/settings.py
```

Hashes must match. Deploy is **scp**, so the VPS can drift from git without anyone noticing.
Also confirm CLAUDE.md is in sync — the VPS copy is what the judgement layer actually reads:

```bash
md5 -q /Users/paulturner/Horses/CLAUDE.md; ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "md5sum /root/horse-racing-bot/CLAUDE.md"
```

## 13. RESOURCES & TESTS

```bash
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "df -h / | tail -1; free -m | head -2; docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' | grep -E 'horse|betfair'"
ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && for t in tests/*.py; do printf '%-40s ' \$t; docker compose exec -T -w /app -e PYTHONPATH=/app horse-racing-bot python \$t >/tmp/o 2>&1 && tail -1 /tmp/o || echo FAIL; done"
```

⚠ `tests/test_demote_stake.py` fails with `no such column: source` — a known-broken **test**, not
broken production. Don't report it as a new fault.

## 14. RECOMMENDATIONS

- **P1** — a forced-paper strategy missing from the frozenset; fallback scores (judgement layer
  lost); settle coverage collapsing; backups stale or failing; code drift between GitHub and VPS;
  two NAPs on one day.
- **P2** — Racing API fields unpopulated; Telegram failures; unsettled backlog; an overdue
  paper-trade review; container restarts during racing hours.
- **P3** — disk/log tidying, cosmetic config drift.

Do not propose scorer changes off a health check. Seven scorer-improvement hypotheses have been
refuted; the measured position is that the scorer is a candidate generator and the gates, filters
and judgement layer are the edge.

## 15. SUMMARY DASHBOARD

| Check | Status | Notes |
|---|---|---|
| Containers | | uptime, restarts |
| Logs (48h) | | error count |
| Judgement layer | | integer scores? model pinned? |
| Racing API | | field population % |
| Ledger integrity | | coverage %, unsettled, ROI @BOG |
| Duplicate cards | | >6 sels or >1 NAP |
| Backups | | VPS age, Mac age, verify status |
| **Live-money safety** | | frozenset intact? |
| Today's card | | count, NAP, caps respected |
| Filters/compliance | | what fired |
| Overdue reviews | | which are due |
| Code drift | | local/GitHub/VPS/CLAUDE.md |
| Resources & tests | | disk, mem, test results |

Traffic light 🟢 / 🟡 / 🔴, and open with a one-line verdict: **OK / WARN / ALERT**, plus whether the
bot is safe to run today as-is.
