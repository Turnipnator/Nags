---
name: healthcheck
description: Run a comprehensive health check on the horse racing bot (Nags)
---

# Horse Racing Bot Health Check

Run a comprehensive health check on the horse-racing-bot. Work through each section systematically, run commands in parallel where possible, and provide a summary dashboard at the end.

## VPS Details
- Server: 149.102.144.190
- SSH Key: `~/.ssh/id_ed25519_vps`
- Container: `horse-racing-bot`
- Path: `/root/horse-racing-bot`
- SQLite DB: `/app/data/racing.db` (inside container)
- Logs: `/app/logs/` (inside container) + Docker stdout
- GitHub remote: https://github.com/Turnipnator/Nags
- All SSH commands should prefix: `ssh -q -o LogLevel=ERROR -i ~/.ssh/id_ed25519_vps root@149.102.144.190 '...'` to suppress banner noise

## 1. PROCESS STATUS

Is the container running and healthy? Any recent restarts or crashes?

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker ps --format '{{.Names}}\t{{.Status}}\t{{.RunningFor}}' | grep horse && docker inspect -f '{{.State.StartedAt}} (restarts: {{.RestartCount}})' horse-racing-bot"
```

Flag: restart count > 0 in last 24h, or container older than a rebuild but restart count = 0 (means no recent deploys — could be stale code).

## 2. LOG ANALYSIS

Check for errors, warnings, API failures, rule misfires. Filter out known noise (Telegram getUpdates polling).

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs horse-racing-bot 2>&1 | grep -iE 'error|warn|fail|fatal|exception|traceback' | grep -v 'getUpdates' | tail -25"
```

Classify findings:
- API failures (Racing API 4xx/5xx, Anthropic rate limits)
- Parser errors (runner data missing, bad odds format, None propagation)
- Scheduler errors (missed run, job failure)
- Telegram send failures

## 3. RACING API HEALTH (CRITICAL)

The Racing API is the sole data source. Verify authentication, fetch success, and — post 24 Apr 2026 fix — that real Bet365 odds are being populated (not hallucinated by the LLM).

```bash
# Last successful racecards fetch
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs horse-racing-bot 2>&1 | grep -iE 'racing api|racecards|Parsed .* from API' | tail -10"

# Odds population sanity check — pull Saddadd-style inspection for today's first meeting
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
from src.scraper import Scraper
from datetime import date, timedelta
s = Scraper()
# Try tomorrow (prices still forming — better test than today's run races)
m = s.fetch_meeting([pick a likely meeting], date.today() + timedelta(days=1))
if m and m.races:
    race = m.races[0]
    print(f'{race.time} {m.course} {race.name[:40]}')
    populated = sum(1 for r in race.runners if r.odds)
    print(f'  Odds populated: {populated}/{len(race.runners)} runners')
    for r in race.runners[:3]:
        print(f'    {r.name}: {r.odds!r}')
s.close()
\""
```

Red flags:
- 🔴 Odds populated: 0/N runners → API change or `/racecards/pro` endpoint broken — LLM will hallucinate prices again
- 🔴 "Validation error - unrecognised query parameter" in logs → API contract changed
- 🟡 Partial odds population (some None) → acceptable for unpriced/NR runners

## 4. TELEGRAM HEALTH

Polling active, recent successful posts, no send failures.

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs horse-racing-bot 2>&1 | grep -iE 'telegram' | grep -v 'getUpdates' | tail -10"
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs horse-racing-bot 2>&1 | grep -c 'chat_id'"
```

Flag any "failed to send", "chat not found", "forbidden", or rate-limit errors.

## 5. SCHEDULER STATE

Is auto-schedule on/off? When did the last run happen? When is the next?

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker logs horse-racing-bot 2>&1 | grep -iE 'scheduler|scheduled|next run|auto-schedule' | tail -10"
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot printenv | grep -E 'AUTO_SCHEDULE|ANALYSIS_TIME|SCRAPE_TIME|RESULTS_TIME'"
```

Report: auto-schedule enabled?, last analysis run time, last results run time, gap between runs.

## 6. DATABASE HEALTH

SQLite `racing.db` — check tables, row counts, recent activity.

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
import sqlite3
conn = sqlite3.connect('/app/data/racing.db')
c = conn.cursor()
# Table sizes
for tbl in ['meetings','selections','results','bot_state','daily_summary']:
    try:
        n = c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
        print(f'  {tbl}: {n} rows')
    except sqlite3.OperationalError as e:
        print(f'  {tbl}: MISSING ({e})')
# Latest selection
try:
    latest = c.execute('SELECT MAX(created_at) FROM selections').fetchone()[0]
    print(f'  Latest selection: {latest}')
except: pass
# Latest result
try:
    latest_r = c.execute('SELECT MAX(recorded_at) FROM results').fetchone()[0]
    print(f'  Latest result: {latest_r}')
except: pass
conn.close()
\""
```

Red flags: missing tables, zero rows after the bot has been running, latest-selection timestamp > 48h old when bot is up.

## 7. TODAY'S RUN QUALITY

Did the bot run today? What did it pick? Is the output coherent with the Operating Policy (max 6 selections, NAP ≥ 78+ or no NAP, no sub-evens, mostly one meeting)?

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
import sqlite3
conn = sqlite3.connect('/app/data/racing.db')
c = conn.cursor()
today = c.execute(\\\"SELECT selection_type, horse, course, race_time, odds_guide, score FROM selections WHERE date(created_at) = date('now') ORDER BY score DESC\\\").fetchall()
if not today:
    print('No selections today')
else:
    print(f'Today: {len(today)} selections')
    for row in today:
        print(f'  {row[0]:12s} {row[1]:20s} {row[2]:15s} {row[3]} @ {row[4]} (score {row[5]})')
conn.close()
\""
```

Manually assess:
- Count ≤ 6? (Operating Policy max)
- NAP score ≥ 78? (or no NAP at all — both fine)
- Any odds_guide "CHECK PRICE"? (should be near-zero — means odds fell through)
- Any sub-evens (≤ 1/1)? (should be zero — compliance gate)
- All from same meeting or at most 2? (concentration policy)

## 8. ODDS QUALITY SPOT CHECK

Confirm the LLM is using real odds from the API, not inventing. Compare bot output odds to raw API for 2-3 runners.

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
import sqlite3
conn = sqlite3.connect('/app/data/racing.db')
c = conn.cursor()
picks = c.execute(\\\"SELECT horse, odds_guide FROM selections WHERE date(created_at) = date('now') LIMIT 3\\\").fetchall()
for horse, odds in picks:
    print(f'  Bot said {horse}: {odds}')
conn.close()
\""
```

Then cross-reference against raw API (run manually from laptop):
```bash
curl -s -u "$RACING_API_USERNAME:$RACING_API_PASSWORD" "https://api.theracingapi.com/v1/racecards/pro" | python3 -c "import json,sys; d=json.load(sys.stdin); [print(r['horse'], (r.get('odds') or [{}])[0].get('fractional')) for rc in d.get('racecards',[]) for r in rc.get('runners',[]) if r['horse'] in {'<picks>'}]"
```

Should match within one price tick (small drift acceptable as odds move in real time; large divergence = hallucination or stale cache).

## 9. RECENT PERFORMANCE (P&L)

Last 7 days of results — winners, placings, hit rate.

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
import sqlite3
conn = sqlite3.connect('/app/data/racing.db')
c = conn.cursor()
rows = c.execute(\\\"SELECT s.selection_type, s.horse, s.odds_guide, r.finish_pos, r.result FROM selections s LEFT JOIN results r ON r.selection_id = s.id WHERE s.created_at > datetime('now','-7 days') ORDER BY s.created_at DESC\\\").fetchall()
wins = sum(1 for r in rows if r[4] == 'WON')
places = sum(1 for r in rows if r[4] == 'PLACED')
losses = sum(1 for r in rows if r[4] in ('LOST','UNPLACED'))
pending = sum(1 for r in rows if r[4] is None)
print(f'Last 7d: {len(rows)} selections | {wins}W / {places}P / {losses}L ({pending} pending)')
# NAP winners specifically
nap_rows = [r for r in rows if r[0] == 'NAP']
nap_wins = sum(1 for r in nap_rows if r[4] == 'WON')
print(f'NAPs: {len(nap_rows)} taken, {nap_wins} won')
conn.close()
\""
```

Flag: 0 winners in 10+ selections = something broken (card bias or ruleset drift). Long NAP droughts (0 from 5+) = check NAP threshold discipline.

## 10. CODE DRIFT (Local ↔ GitHub ↔ VPS)

The standing instruction is that local git, GitHub, and VPS stay in lockstep. Check for drift.

```bash
# Local commit on main
echo "=== LOCAL HEAD ===" && git -C /Users/paulturner/horse-racing-bot log -1 --oneline

# GitHub HEAD on main
echo "=== GITHUB HEAD ===" && git -C /Users/paulturner/horse-racing-bot ls-remote origin main | awk '{print $1}' | cut -c1-10

# VPS deployed code — hash of key files
echo "=== VPS FILE HASHES ===" && ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "cd /root/horse-racing-bot && md5sum src/analyst.py src/scraper.py src/scorer.py"

# Compare to local
echo "=== LOCAL FILE HASHES ===" && md5sum /Users/paulturner/horse-racing-bot/src/analyst.py /Users/paulturner/horse-racing-bot/src/scraper.py /Users/paulturner/horse-racing-bot/src/scorer.py
```

🔴 Any mismatch = code drift. Either:
- Local has uncommitted changes → commit + push + deploy
- VPS has files local doesn't → investigate (did someone edit directly on VPS?)
- GitHub HEAD behind local → push
- VPS hashes differ from local → rebuild/redeploy

## 11. DISK, LOGS & CACHE

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker stats horse-racing-bot --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'"
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot ls -lh /app/data/ /app/logs/ 2>/dev/null"
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "df -h / | tail -1 && free -h | head -2"
```

Flag: `racing.db` > 500MB (investigate table bloat), any log file > 100MB, disk free < 10%, memory > 80%.

## 12. CONFIGURATION AUDIT

Confirm env vars are set and look sane.

```bash
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot printenv | grep -E 'TELEGRAM_|RACING_API_|ANTHROPIC_|TIMEZONE|LOG_LEVEL|AUTO_SCHEDULE|FOCUS_COURSES' | sed 's/=.*/=***/'"
```

Values are masked — just check presence. Missing any of TELEGRAM_TOKEN / RACING_API_USERNAME / RACING_API_PASSWORD / ANTHROPIC_API_KEY = bot won't function properly.

## 13. RULE REGRESSION CHECKS

A handful of known bugs that have been fixed — confirm they don't reappear.

```bash
# Evens parser (fixed 21 Apr 2026 after Crystal Island EvensF slipped the sub-evens block)
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "docker exec horse-racing-bot python3 -c \"
from src.analyst import _parse_odds_to_decimal, _is_sub_evens
for s in ['Evens', 'EvensF', 'Evs', 'E/Fav', 'EV']:
    print(f'  {s}: decimal={_parse_odds_to_decimal(s)}, sub_evens={_is_sub_evens(s)}')
\""

# Odds-population sanity (fixed 24 Apr 2026 after LLM was hallucinating prices)
ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "grep -c 'odds_value = None' /root/horse-racing-bot/src/scraper.py"
# expect: 1 (the line we added)

ssh -i ~/.ssh/id_ed25519_vps root@149.102.144.190 "grep -c 'racecards/pro' /root/horse-racing-bot/src/scraper.py"
# expect: 3 or more (the pro endpoint switch)
```

Expected:
- `Evens: decimal=1.0, sub_evens=True` for all variants
- `odds_value = None` present in scraper
- `racecards/pro` appears 3+ times

## 14. RECOMMENDATIONS

Provide prioritised recommendations:
- **P1 (Critical):** crashes, auth failures, odds population broken, database corrupted, code drift between GitHub and VPS
- **P2 (Important):** NAP drought > 5, long error streak in logs, Telegram send failures, Anthropic rate limits
- **P3 (Nice to have):** log rotation, DB cleanup, config tidying

## 15. SUMMARY DASHBOARD

Present a quick status table at the end of every run:

| Check | Status | Notes |
|-------|--------|-------|
| Container Running | | uptime, restart count |
| Logs Healthy | | error count last 24h |
| Racing API | | last successful fetch, odds population rate |
| Telegram | | polling active, last send |
| Scheduler | | auto-schedule state, next run |
| Database | | rows per table, latest activity |
| Today's Run | | selections count, NAP score, compliance |
| Odds Quality | | sample match vs raw API |
| Recent Performance | | last 7d W/P/L, NAP hit rate |
| Code Drift | | local vs GitHub vs VPS hashes |
| Resources | | CPU, RAM, disk |
| Config | | env vars present |
| Rule Regressions | | Evens parser, odds population, /racecards/pro |

Traffic light: 🟢 All good / 🟡 Minor issues / 🔴 Needs attention

At the top of the summary, state clearly: **OK / WARN / ALERT** and whether the bot is safe to run today as-is.
