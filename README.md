# Nags — UK/Irish Horse Racing Bot

Automated selection bot for UK and Irish horse racing. Pulls race data from The Racing API, applies a rule-based scoring framework plus Claude LLM judgement, and posts selections to Telegram.

Designed to find a NAP of the day (strongest selection), a Next Best, and up to four cherry-picked race selections — never forcing picks from weak cards.

## How it works

```
┌──────────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌──────────┐
│ The Racing API   │ ──▶ │  Scraper     │ ──▶ │  Scorer          │ ──▶ │ Telegram │
│ /racecards/pro   │     │  (data pull) │     │  + Claude judge  │     │          │
└──────────────────┘     └──────────────┘     └──────────────────┘     └──────────┘
```

1. **Scraper** (`src/scraper.py`) — calls The Racing API's premium `/racecards/pro` endpoint each day. Pulls runners, form, speed figures (RPR/TS), Official Ratings, Spotlight analyst comments, trainer 14-day stats, medical/wind-op history, headgear flags, stable tour quotes, and **live Bet365 odds**.
2. **Scorer** (`src/scorer.py`) — programmatic score out of 100 per runner, broken into Form, Course, Going, Distance, Class, Speed, Weight, Jockey, Trainer, plus edge bonuses (compound intent signals, wind-op returners, first-time headgear, hot-stable, dual-edge RPR+TS, class-drop kicker).
3. **Analyst** (`src/analyst.py`) — cherry-picks the top races, passes runner blocks into Claude for final judgement (NAP/NB allocation, compliance checklist), or falls back to programmatic picks if the LLM is unavailable.
4. **Telegram bot** (`src/telegram_bot.py`) — posts the daily card to a specified chat. `/run` for on-demand analysis.

## Key rules enforced

- **NAP threshold**: 78+/100, never forced
- **Sub-evens block**: no selection at 1/1 or shorter
- **NB swap (bidirectional)**: value swap (NB 2x+ odds + within 5 pts) OR market swap (NB is shorter/favourite + within 5 pts)
- **TS-below-OR veto**: if Topspeed is 10+ below Official Rating, horse capped at NB role
- **Dual-edge bonus**: biggest RPR gap AND biggest TS gap above OR → +5 bonus, forced into NB minimum
- **Handicaps always E/W**: never win-only in a competitive handicap
- **System-resistant races**: big-field finals, Grade 2+ bumpers, early-season 3yo handicaps → half stakes, E/W only, never NAP
- **Operating Policy**: max 6 selections per day total, one-meeting focus default, skip cards with no 75+ scorer

Full rule set lives in the consuming project's `CLAUDE.md` (not in this repo — kept separate from code).

## Setup

### 1. Clone & install
```bash
git clone https://github.com/Turnipnator/Nags.git
cd Nags
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in the values:
#   TELEGRAM_TOKEN        — from @BotFather
#   TELEGRAM_CHAT_ID      — your numeric chat id
#   ANTHROPIC_API_KEY     — https://console.anthropic.com
#   RACING_API_USERNAME   — https://theracingapi.com (Pro tier required for odds)
#   RACING_API_PASSWORD   — same
```

### 3. Run locally
```bash
python main.py
```

### 4. Run with Docker (recommended)
```bash
docker compose up -d --build
docker compose logs -f horse-racing-bot
```

## Deployment

The bot runs on a VPS in a Docker container.

```bash
# From local machine — deploy updated code
scp -i ~/.ssh/id_ed25519_vps src/analyst.py src/scraper.py src/scorer.py \
    root@YOUR_VPS:/root/horse-racing-bot/src/
ssh -i ~/.ssh/id_ed25519_vps root@YOUR_VPS \
    "cd /root/horse-racing-bot && docker compose up -d --build"

# Tail logs
ssh -i ~/.ssh/id_ed25519_vps root@YOUR_VPS \
    "cd /root/horse-racing-bot && docker compose logs -f horse-racing-bot"
```

## Telegram commands

| Command | Purpose |
|---------|---------|
| `/run` | On-demand analysis for today's cards |
| `/results` | Show yesterday's result reconciliation |
| `/recent` | Show last N days of results |
| `/help` | Command list |

## Project structure

```
├── main.py                 # Entry point + scheduler
├── src/
│   ├── scraper.py          # Racing API client + data parsing
│   ├── scorer.py           # Programmatic scoring (100-point framework)
│   ├── analyst.py          # Cherry-pick + Claude judgement + compliance gate
│   ├── telegram_bot.py     # Telegram command handlers + posting
│   └── database.py         # SQLite persistence for selections/results
├── config/
│   └── settings.py         # Env-var loading + constants
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example            # Template — copy to .env and fill in
```

## Development

Any change to selection rules should be:
1. Committed with a clear message explaining what changed and why
2. Deployed to the VPS (see Deployment above)
3. Validated on at least 2–3 race days before treating as stable

Race-day results, rule validations, and learnings are recorded in the consuming project's memory system — not in this repo.

## Data source

Powered by [The Racing API](https://theracingapi.com) (Pro tier required for live odds + Spotlight). No scraping of betting sites — all data comes from the API under the standard API licence.

## Disclaimer

This is a personal analysis tool. Racing is volatile and no selection system is guaranteed. Bet only what you can afford to lose, and always verify prices against the bookmaker of record before placing bets.

## Licence

Private — not for redistribution.
