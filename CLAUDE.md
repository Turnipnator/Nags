> **CLAUDE.md v4.1 — Live as of 1 May 2026.** Promoted from draft after 3-day paper-trade: v4.1 +£121.25 vs bot v3 −£36.25 (delta +£157.50). v3 archived at `CLAUDE_v3_archive.md`.
> v4.1 = v2 base + Operating Policy + Racing API mandate + a small set of v3 additions that earned their keep.
> v4.1 dropped from v3: TS-veto, dual-edge force-NB, 9-step compliance checklist, front-runner conflict, gate jockey-override, class-drop quality filter, 3yo-all-types, big-field Listed sprints, danger-swap check, 78+ NAP threshold (back to 75+).
> v4.1 KEPT the **mandatory market swap** (NB shorter-priced than SEL within 5pts → swap) after Pontefract 29 Apr 2026 fired the rule correctly twice on the same card. **Value swap** (NB longer-priced) is **NOT enforced** by the gate — it is judgment at scoring time only (tightened 5 May 2026 after Lion Of The Desert 10/3 sel WON Ffos Las and Kylenoe Dancer 10/1 NB value-promotion was a non-runner — clean Spotlight had passed the gate, the deterministic auto-fire was itself the bug).
> **Tightening 7 May 2026:** Two AW Class 5/6 handicap-targeted rules added (weight-rise blocker, no-NAP-on-favourite). Triggered by Southwell 7 May: Roaring Ralph (+9lb after C&D hat-trick) NAP'd 9/2 → 7th of 11; Shades Of May (3/1F, top scorer) → 8th of 10. Both market-confirmed sub-4/1 picks at the price band where the framework's score adds nothing over market. Rules are class-specific to preserve framework flexibility at Group/Listed/Festival level where short-priced NAPs (Brighterdaysahead, Madara, Saddadd) have genuinely worked. See "AW Class 5/6 Handicap Targeted Rules" section.
> **Tightening 8 May 2026:** Bot calibration patch for Class 5/6 (any surface). Forensic comparison vs manual rubric on 8 May Ripon found bot over-scoring by 5-9 points in compressed-pool C5/6 handicaps via four mechanical drifts in `scorer.py` + a missing score-vs-market sanity gate. All fixes scoped to Class 5/6 only — premium-class scoring untouched. Triggered by Ripon evening 8 May: Mark's Choice (bot 79, 9/2) → 6th, Novamay (bot 86, 16/1) → unplaced. See "C5/C6 Calibration Patches" section.
> **Tightening 9 May 2026:** Two structural changes for the bot — class floor (Option X) and going stability gate (Option Y). After 3 days of consistent bleed in low-class evening cards (AW C5/6 Southwell 7 May, turf C4/5 Ripon 8 May, NH C5 Hexham 9 May) while manual premium-class focus banked +£94, the bleed was diagnosed as **meeting selection** rather than scoring. X = bot only races Group/Listed/Grade always, Flat C4+, NH C3+ — below = blocked at race-ranking. Y = bot persists going snapshot per course/date, demotes selections (no NAP, force E/W) when going drifts ≥ 2 ordinal steps within 12h or when `going_detailed` flags volatility. Triggered by Hexham 9 May 2026 going-shift Good→Soft: Gardener NAP 5/1 → 5th, Saracen Beau + Snapaudaciaheros both PU. See "Bot Class Floor + Going Stability" section.
> **Tightening 15 May 2026:** Two bot-only changes to align with the manual ruleset and improve LLM judgement breadth. (1) **NB-of-day field-size floor:** the 1.5pt E/W NB-of-day stake requires an 8+ runner field for sensible 3-place E/W terms (1/5 odds). Below 8R the bot now demotes NB-of-day to a 0.75pt race SEL stake. Triggered by Newton Abbot 7:00 13 May 2026 where Stinginhisstep at 8/1 NB-of-day in a 5R handicap finished 3rd at SP and the E/W leg paid nothing — single biggest losing bet of the night at -£30. (2) **NUM_SELECTIONS bumped 4 → 6** in `analyst.py` so the LLM judgement layer sees more qualifying races. Triggered by York 15 May 2026 where Calimystic (top scorer at Aintree 6:55 C3 chase) was hidden from the LLM because only top-4 races by score were surfaced — manual analysis correctly identified him as NB-of-day candidate. CLAUDE.md Operating Policy already allows up to 6 picks/day (1 NAP + 1 NB + 4 race SELs) so 6 is the correct ceiling. See "NB-of-Day Field-Size Floor" and "Bot Selection Breadth" sections.
> **Tightening 22 May 2026:** **Judgement model pinned to `temperature=0`** (`analyst.py` `_run_claude_judgement`). The LLM judgement call previously ran at the SDK default temperature 1.0 — non-deterministic, so two `/run`s of the same card diverged at the margin (22 May Goodwood: top 2 picks identical across runs but St Mawes dropped in/out of the 3rd slot purely from sampler noise). Pinning to 0 makes identical input → identical selections, so any run-to-run difference is now a REAL change (odds drift, Timeform update, non-runner) rather than dice. Matters for a real-money rubric-based system and makes CLAUDE.md/prompt tuning measurable. Caveat: does NOT sync runs made hours apart (odds/Timeform/NRs still move the input). Deterministic `scorer.py` was already temperature-free; this only affects the LLM layer on top. **⚠ SUPERSEDED 5 Jun 2026 — see below: the `temperature=0` pin was REMOVED because `claude-opus-4-8` (adopted 1 Jun) deprecates the param and 400'd every judgement call. Determinism via this param no longer holds while on 4.8.**
> **Tightening 21 May 2026:** **Excused last-run override** added (bot Hard Rule 18 + CLAUDE.md "EXCUSED LAST-RUN OVERRIDE" box) — the positive mirror of the long-standing "Spotlight overrides figures" downgrade rule. The deterministic Form score reads finishing positions literally and cannot see when a single poor most-recent run was a non-recurring fluke (wide draw, hampered, wrong ground, missed break, too keen, needed the run). When the Spotlight EXPLICITLY excuses the last run only, the LLM must not let it suppress an otherwise-strong horse below the 75 NAP line. **Strictly scoped: Flat Class 4+ / NH Class 3+ / Group/Listed/Grade only — NEVER Class 5/6** (the C5/6 calibration patches own that compressed-pool territory; this override must not re-inflate those scores). Triggered by Musselburgh 4:25 21 May 2026: Bellarchi (C3 hcap) — last run a Chester defeat the Spotlight excused (wide draw) dragged her deterministic Form to 9.1/22 and base to 72 (below NAP line); manually overridden to 85/2pt NAP, **WON at 9/4** as part of a 3-from-3 card (first double in ~6 weeks). Now automated so the bot makes the override itself. See "Excused Last-Run Override" section.
> **Tightening 26 May 2026:** **Betable-threshold race-selection gate** (`analyst.py` `_top_betable_score`). The race-ranking step previously used the absolute top runner's score for the 70+ Operating Policy floor. A sub-evens favourite scoring ≥70 carried the race past the floor, but the favourite was then eliminated at SEL stage by the sub-evens block — leaving the LLM to pick from non-favourites scoring 40-50, below the "skip" line. Race-selection now gates on the highest score among runners priced ABOVE evens (decimal > 1.0). Triggered by Leicester 2:10 26 May 2026: Victory Gold 8/13F at 73.0 (Hot stable +3, SPEED DOMINANCE +5) carried Miami To Ibiza (45) → market-swapped to Libertango (44) into the daily picks — a clear "below 55 = skip" violation. Applies to both `/run N` and default-mode race-ranking. See "Betable-Threshold Race Gate" section.
> **Bugfix 5 Jun 2026 — class-drop kicker misfired on ALL Listed/Group races** (`scorer.py` `_score_class`, today-level resolution ~line 769). The kicker compares a runner's recent placed runs against TODAY's class level. Today's level was resolved from `race.race_class` ALONE — but the API stores Listed/Group races as `race_class="Class 1"` with the real level in the separate `pattern` field ("Listed"/"Group N"). So every pattern race was under-read to level 7 (Class 1), and any prior Listed/Group placing then looked like a class DROP → spurious +3/+5 kicker AND a phantom intent signal (feeding signal-compounding). The enrichment side (`scraper.fetch_recent_race_classes`) already resolved `pattern` before `class_str`, so the two sides were asymmetric — that asymmetry WAS the bug. Confirmed on Epsom Oaks day: **Stellar Sunrise +3** for a Listed→Listed move (3rd in the King Charles II Listed, today the Listed Surrey — same class, and beaten) → inflated to raw 86 and made bot NAP at 6/4; **Legacy Link +5** for a Group 3 Musidora WIN read as a 2-class drop into the **Group 1** Oaks (a class RISE — should be zero drop) → bot NB at 80. Both of the bot's top two premium picks were kicker-inflated. Fix: resolve today's level from `f"{race.pattern} {race.race_class}"` so pattern wins (mirrors enrichment). Plain handicaps have empty pattern → unchanged. This is a prime suspect for the premium-class "score inflation" the 1 Jun note told us to watch for — it was structural, not model drift. Manual read for the day (Persica NAP / Amelia Earhart NB on the soft) was unaffected and stands. NOTE: the same `race_class`-only read also means Flat Group mares' allowance (`+4`, kicker block ~line 745, and `_score_weight` grade check) never fires for Flat Group races (pattern="Group N", race_class="Class 1") — latent, NOT fixed today (kept change scoped to the kicker); revisit if a Flat G1/G2 mare is under-scored.
> **Fix 5 Jun 2026:** **`temperature=0` removed from the judgement call** (`analyst.py` `_run_claude_judgement`, ~line 1516). The 22 May determinism pin collided with the 1 Jun model switch: `claude-opus-4-8` **deprecates the `temperature` parameter** and returns `400 invalid_request_error` ("\`temperature\` is deprecated for this model"). Every judgement call 400'd in <1s → the `except` fired the **"Programmatic fallback (Claude API unavailable)"** path → daily picks were RAW deterministic scorer output with NO CLAUDE.md judgement layer (no Spotlight read, Bug-3 form-weighting exposed). Diagnosed from Epsom Oaks day 5 Jun: bot returned Celeborn NAP out of the 18-runner HKJC World Pool handicap (a big-field cavalry charge the LLM would skip) + Stellar Sunrise NB at "86.0/22-22" (the short fav I'd downgraded on its negative Spotlight) in <1s. NOT an API outage — a 400 from sending a deprecated param. Fix: delete the `temperature=0` line; stay on 4.8 (chosen over reverting to 4.6). **Cost:** the 22 May reproducibility guarantee no longer holds — run-to-run divergence at the margin is possible again (no param to pin on 4.8). If determinism becomes critical, the only lever is reverting env to `claude-opus-4-6` (which accepts temperature) and re-adding the pin. The "API unavailable" fallback label was misleading — **wired up 5 Jun 2026** (`_describe_api_error` helper): the fallback `notes` now surface the real cause, e.g. `Programmatic fallback — Claude API HTTP 400 (BadRequestError): ...`. An API rejection (HTTP 400/401/404/429 = our bug / bad key / bad model / rate limit) is now instantly distinguishable from a genuine connectivity outage (no status code → `APIConnectionError`). Empty-but-successful responses note `Claude returned no selections (empty response)`.
> **Tightening 1 Jun 2026:** Two bot changes. (1) **NB-of-day score floor** (`analyst.py` `_enforce_compliance` CHECK 13). The NB-of-day slot had price-cap, field-size and C5/6 score-market gates but NO check against the 70+ Operating Policy floor itself. When only one genuine 70+ horse existed on a card, the LLM reached down to a sub-70 horse to fill the second slot and it kept the 1.5pt premium stake. Now: if `sels[1].adjusted_score < 70` the NB-of-day is demoted to a 0.75pt race SEL (via the existing `nb_price_capped` flag, E/W forced where a place pool exists); below 55 an extra flag suggests dropping it entirely. A NAP-only one-pick day is the correct outcome when nothing else clears 70. Triggered by Newbury 14:50 1 Jun 2026: Electrifarhh scored 64 yet was made NB-of-day at 9/1 with a 1.5pt E/W stake → came nowhere (the 64 was an honest LOW score the staking layer ignored). Same race, River King — the manual SEL held over the bot — WON at 3/1. (2) **Judgement model 4.6 → 4.8** (`config/settings.py` default + VPS `.env`). 4.6 was a deliberate roll-back from 4.7 (5 May 2026, score inflation). 4.8 adopted because the guardrails are now far stronger (NAP/NB price caps, C5/6 score-market gate, temp=0, this NB floor) — watch early cards for re-inflation (NAPs at long odds, scores >90); revert env to `claude-opus-4-6` if it recurs.
> **Tightening 27 May 2026:** **Rule 18b — Excused Higher-Class Last Runs** (`scorer.py` `_excused_form_indices`). The deterministic Form score reads finishing positions literally and cannot see when a recent poor finish was earned in materially tougher company. Rule 18b is the structural counterpart to base Rule 18 (Spotlight-text last-run override). When a runner's recent history shows a poor finish (pos 4+) in a race at least 1 class tier higher than today, that position is excluded from form-penalty calculation. Strictly scoped — Flat C4+ / NH C3+ / G/L/Grade only. NEVER fires in Flat C5/6/7 or NH C4/5 (preserves C5/6 calibration patches and NH class floor). Cap: max 1 excused per horse. Triggered by Redcar 3:50 26 May 2026: Classic Encounter — bot's deterministic form score was 5.3/22 from "603-76" reading literally; both poor finishes were in C2 heritage handicaps (Spring Mile, Steve Birch Finale) where placings at that level are honest signals. Race scored 65.8 → ranked 26th → never reached LLM judgement. With Rule 18b firing, the C2 7th gets excluded → form lifts to 5.8 → modest +0.5 lift today (constrained by separate Bug 3 form-weighting; see footnote). Effect is larger when the excusable run dominates the form (single high-weight bad return run). See "Excused Higher-Class Last Runs (Rule 18b)" section.
> **Tightening 30 Jun 2026 — Judgement-layer guardrails (model-agnostic).** Diagnosis (Musselburgh 30 Jun): the bot drifted hard from the manual read — The Gay Blade (C4 7f hcap, form 126111) scored **90** and was nearly NAP'd at 5/1, while the genuine dual-figures leader High Degree (RPR 105 / TS 118) was deflated to 68. Root cause is structural, not model drift: the LLM judgement layer (`analyst.py`) is handed the deterministic `scorer.total` but emits its **own free-form `adjusted_score`** that can override the rubric in either direction. A free-form number drifts between models AND between runs — so reverting 4.8→4.6 does not cure it, it only changes the direction of drift. Two complementary, **feature-flagged, model-agnostic** gates added to `_enforce_compliance` (run before all other checks). **(1) ANCHOR CLAMP (CHECK 0):** clamp each `adjusted_score` to `scorer.total` ± band — **+14 up / −25 down**. Tight up so runaway inflation is impossible (Gay Blade 62-anchor → clamped 76, no longer a 90); loose down because Spotlight downgrades are legitimate and lose no money. The biggest *legitimate* documented upgrade — the Bellarchi excused-last-run +13 (WON 9/4) — fits inside the +14 band and is preserved. **(2) GENERAL SCORE-VS-MARKET GATE (CHECK 6 generalised):** the 8 May C5/6-only Option B gate now fires at ALL classes (C5/6 keeps the stricter 80 floor; other classes use 82) — the 8/1 odds floor means short-priced premium NAPs (Brighterdaysahead 9/4) never trip it; only long-priced high scores get gated. Clamp = LLM-vs-rubric axis; gate = rubric-vs-market axis. Config: `JUDGEMENT_CLAMP_ENABLED`, `JUDGEMENT_UP_BAND` (14), `JUDGEMENT_DOWN_BAND` (25), `GENERAL_GATE_SCORE` (82), `GENERAL_GATE_ODDS` (9.0) — all env-overridable for instant revert. Local test 7/7 vs the real compliance gate. **Does NOT fix the deflation direction** — that sits on top of **Bug 3** (reversed form weighting in `scorer._score_form`, still live, deflates recent-momentum anchors). Bug 3 is the next change but needs its own paper-trade (it shifts every score); once fixed, the up-band can tighten toward ~8 and bot/manual converge both directions.
> **Tightening 30 Jun 2026 (PM) — Scorer recalibration: Bug 3 fix + ability anchor (`scorer.py`, paper-trade started).** Same-day follow-up to the guardrails above. Pulling The Gay Blade's *deterministic* breakdown proved the 90 was NOT an LLM override (the clamp stayed silent because there was nothing to clamp) — **the deterministic scorer itself rated him 90** and had the field INVERTED: Gay Blade (C4 hcap, OR 71 / RPR 81 / **TS 65 = lowest in his race**) scored 90 `[F20 C15 G13 D12 Cl8 Sp8 ...]` while the genuine class horses (Son RPR 93/TS 92 → 63; cross-card High Degree RPR 105/TS 118 → 65) sat 25pts adrift. Root cause: the positional block (Form 22 + Course 15 + Going 15 + Distance 12 = **64**) is fully bankable by a low-rated course specialist, while ability (Class 12 + Speed 8 = 20) is only a fifth of the score — course/form accumulation buries the clock. **Two coupled fixes, feature-flagged `SCORER_RECAL_ENABLED` (instant revert):** (1) **Bug 3 fixed** — `_score_form` weighted the OLDEST run heaviest (so a horse's most recent runs counted LEAST); corrected to weight the MOST RECENT heaviest (all classes — pure correctness). Sibling `_check_improving` had the same inversion (flagged DECLINING horses as improving) — also fixed. (2) **ABILITY ANCHOR** (`_ability_factor`) — in **non-premium handicaps only (Flat C4 & below / NH C3 & below, tier ≤ 4)** the positional block (Form+Course+Going+Distance) is scaled ×[0.7–1.0] by the runner's best-figure rank within today's field; 1.0 (no-op) at premium class, for the field-best horse, or on missing data. Premium (Flat C1–C3 / NH C1–C2 / Listed / Group / Grade) **untouched** — honours the existing "C1–C4 premium" framing while extending the C5/6 decay's *spirit* up to C4. **Local before/after on today's card:** Gay Blade **90 → 81.6** (−8.4, inflation gone, now a tighter ~10 clear as a legit in-form C&D treble-winner rather than a runaway); High Degree **+2.0** via Bug 3; worst over-scorers (Strength Of Spirit −5, Pandemonium −5) trimmed; premium scores moved ≤5. **Known limitation:** C3 handicaps still let a poor-figures course specialist (Thunder Wonder, form 00-048, RPR 98 → 70) edge the figures leader (High Degree 67) — the anchor is deliberately scoped OUT of C3 (premium); revisit if the paper-trade shows C3 needs it. **Risk to watch:** the anchor could dampen a genuinely well-handicapped low-figure improver — mitigated by using the *best* of RPR/TS/OR (a recent competitive RPR protects them). **Paper-trade: 7 days from 30 Jun 2026 (review 7 Jul).** Track ability-anchored picks' W/P rate and any anchored-down horse that wins; revert via `SCORER_RECAL_ENABLED=False` if 3+ anchored-down winners with no offsetting gain. The clamp + general gate (guardrails note above) sit ON TOP of this corrected deterministic layer.

---

> **Bugfix 9 Jul 2026 — non-runners were being scored** (`scraper.py` `_parse_race`). The Racing API keeps withdrawn horses in the per-race `runners` array and **they still carry a jockey**, so the long-standing "skip runners with no jockey" heuristic never fired for a single one (Persian Spring/Jamie Spencer, Shafdar/William Buick, Barrister/Joe Leavy). What the API *does* strip from a non-runner is **every bookmaker price** (all 32 books quote `-`), and it excludes them from the separate **`field_size`** key. Consequence: NRs were parsed, scored, counted in `num_runners`, and — worst — left inside the **field-relative** comparisons (`_score_class` top-RPR-in-field, speed ranks, the C4-and-below ability anchor). A withdrawn horse rated RPR 94 silently deflated every rival's class score. It also corrupted every field-size gate (NB-of-day 8+ floor, E/W terms, big-field system-resistant thresholds). Fix: drop runners with no price at any bookmaker, **but only when at least one rival IS priced** (so an early card whose market hasn't opened keeps its full field); `num_runners` then equals `field_size`. Verified 0/40 mismatches on the 9 Jul card, 20 NRs dropped. **This moves scores** — Newmarket 5:20 Debenhams C3: dropping 2 NRs flipped the deterministic top scorer from Spanish Voice (72.6) to Sterling Knight 25/1 (72.2, Spanish Voice → 71.6). Triggered by the 9 Jul card describing the 3-runner July Stakes as "a tiny 4-runner Group 2" and the 13-runner Debenhams as "15-runner".
> **Bugfix 9 Jul 2026 — double-rebuild note** (`analyst.py` CHECK 15). With no NAP the double is *cleared* (the renderer gates on `nap_index >= 0`), but the note still read `DOUBLE REBUILT: was [X + Y], now [— + —]` — implying a double survived. It also wrapped legs in `[...]`, which Telegram parses as Markdown link syntax and eats. Now: `DOUBLE DROPPED: no NAP today` when cleared, `DOUBLE REBUILT: A x B` when genuinely rebuilt, silent when unchanged, no square brackets.
> **Tightening 10 Jul 2026 — Rule 18b MARGIN GUARD** (`scorer.py` `_excused_form_indices` + `scraper.py` `fetch_recent_race_classes`). Rule 18b excused a poor finish in tougher company on the premise the horse ran *respectably* above today's level — but it only tested **finishing position ≥ 4** and **class tier > today's**. It never asked **how far the horse was beaten**, so a respectable 7th and a tailed-off last were excused identically. Root cause: `ovr_btn` (lengths behind the WINNER) was never captured by the scraper. ⚠ Do NOT use the adjacent `btn` field — that is lengths behind the horse *in front*, and makes a 12th-of-30 look beaten 0.3L. Fix: capture `ovr_btn` + `dist_f` (same response body, no extra API calls), store `btn_per_f`, and refuse to excuse any run beaten more than **`RULE_18B_MAX_BTN_PER_FURLONG = 2.0`** lengths-per-furlong. Missing margin or trip ⇒ do NOT excuse (fail closed). The guard can only make 18b *less* generous; when it blocks, the form reads literally = pre-27-May behaviour. **Calibration** (208 real result lines, 10 Jul card): Flat n=106 median 0.57 / p95 2.20; NH n=102 median 0.83 / p95 3.04; **of 47 PLACED (1-2-3) NH runs, ZERO exceeded 2.00 L/f** — hence one constant serves both codes, no Flat/NH split, no absolute ceiling. Anchors: **PASS** Classic Encounter (the founding case) Spring Mile C2 7th/22, 9.75L over 8f = 1.22 L/f — he then WON at 11/8; **BLOCK** Flora Of Bermuda, Jubilee Gp1 18th of 18, **38.75L** over 6f = 6.46 L/f. Blast radius: 18b firings 81→71, 19 routs blocked, 16/245 scores moved (all down, max −6.0), top scorer changed in **1 of 26** races. **⚠ DAY-1 COUNTER-EXAMPLE — see paper-trade box below.** Revert: `RULE_18B_MAX_BTN_PER_FURLONG = 999.0` (do NOT touch `RULE_18B_ENABLED`). Escalation if the marginal 2.0–2.5 band bites: raise to **2.5** before reverting (keeps the four egregious routs blocked, restores 11 firings).
> **⚠ PAPER-TRADE — Rule 18b margin guard, 7 days from 10 Jul 2026 (review 17 Jul).** Deployed the same day it produced a losing change. **York 2:45 10 Jul (Summer Stakes Gp3): Flora Of Bermuda WON at 3/1** — the very horse whose 38¾L rout the guard refuses to excuse. Unpatched she scored **82.8 (top, → NAP)**; patched she scores **80.0 and drops to 2nd behind Royal Fixation (81.5, 10/1) who finished 5th.** So on day one the guard swapped a winning NAP for a losing one. **This does not refute the principle** — the guard does not veto her, it only stops *inflating* her, and 80.0 still reads her class correctly through Course/Going/Distance/Class/RPR. But it is real evidence and it is the strongest single argument against the change. Note honestly: her win IS the literal claim "the bad run was a non-run." **Failure trigger: 2+ further races in the window where the guard demotes a winner out of the top slot ⇒ raise to 2.5. 4+ ⇒ set 999.0.** Log every `Rule 18b MARGIN GUARD:` line.
> **OPEN ISSUE 10 Jul 2026 — the API returns TODAY'S UNRUN RACE as `results[0]`,** with a `position` that is not a result (Flora `'1'` at 3/1; Spicy Marg `'7'` at 11/8F) and a live `sp`. `_excused_form_indices` filters it by date — correctly — but it has **already consumed one of the three `limit=3` slots**. So on race day Rule 18b inspects **two** prior runs, not three: a candidate three runs back is invisible, AND the `same_class_poor_count >= 2` honest-form guard can never be satisfied from two runs, so **18b fires more freely than designed** (81 firings on one card). `_score_class`'s class-drop kicker is **immune** (it needs `level > today_level`; the phantom record resolves to exactly `today_level`). Fix is one line (fetch `limit + 1`, or drop same-day records at source) **but it feeds a third genuine past run to the class-drop kicker, moving scores** — needs its own paper-trade. NOT bundled with the margin guard, NOT fixed.
> **⚠ COUNTER-EXAMPLE 10 Jul 2026 — BOTH pass-the-race rules passed a winner on the same card.** (1) **Deployed rule** `_blocked_favourite_dominates` (RPR gap ≥ 8): Newmarket 2:25 Duchess of Cambridge — Libertango blocked at 20/21 and 9 RPR clear ⇒ race dropped. **Senorita Bonita, the best betable runner, WON at 9/4**; Libertango only 2nd. First documented case of the leftover winning (revert trigger is 3+ in a 4-week window — **1 of 3**). (2) **The un-deployed candidate rule** "blocked favourite is also the top deterministic scorer ⇒ pass" (proposed 9 Jul after Inner City Blues): Newmarket 3:35 Falmouth Gp1 — Precise blocked at 4/5 and scored 79 vs Blue Bolt 78 ⇒ manual pass. **Blue Bolt WON at 85/40**; Precise 2nd, beaten 2L. The rule's first live test rejected a winner that the framework had *already correctly identified as the top betable selection*. **DO NOT DEPLOY that rule.** Its premise — that a blocked favourite being top-scored means the race is unplayable — is now 0-for-1 against, and the 9 Jul case (Inner City Blues) may simply have been the sub-evens block working as designed on a horse that happened to win.
> **OPEN ISSUE 9 Jul 2026 — RPR-over-OR is a HANDICAP metric and the scorer applies it everywhere.** In a level-weights Group/Listed race every runner carries the same weight, so "RPR 8 above OR" measures nothing except that a horse has been outrunning its rating; the horse rated 10lb superior on OR is simply the better horse. Newmarket 2:25 July Stakes (all three at 128lb): bot scored **Hickory Lad 72.1** (RPR 103, TS 80, OR 95) over **Adaay Of Scarlett 63.1** (RPR 104, **TS 92**, **OR 105**) — Adaay better on all three figures, shorter-priced (15/8 v 11/2), the API tip *and* the API verdict's selection. The 9-point gap kept the **mandatory market swap** (fires ≤5pts) from firing, so the gate was not at fault — **the score was**. Root cause is the known positional-block inversion (Form 22 + Course 15 + Going 15 + Distance 12 = 64 bankable; Class 12 + Speed 8 = 20) and the **ability anchor is deliberately scoped OUT of premium classes**, so nothing checks the clock in a Group 2. Live £5 went on Hickory Lad. **Not fixed** — extending the anchor to premium non-handicaps, or zeroing the RPR-over-OR edge when the race is not a handicap, both need their own paper-trade.

> **⚠ AUTHORITATIVE LEDGER — RECONCILED AND BACKFILLED 6 Aug 2026. `racing.db` is now the single source of truth: 818 bets, 100% settled, every month.** Full ledger at BOG: **−1.99% ROI** (1,270.3pt staked, −24.41pt, 138 won / 130 placed / 24 non-runners). Two independent methods agreed before anything was written — an from-scratch rebuild joining picks to Racing API results gave −2.3%, the hardened `scripts/backfill_results.py` through `database.settle()` gave −2.0%.
> **What was wrong:** the nightly settler only began running in June, so coverage was **Mar 0% / Apr 0% / May 18% / Jun 89% / Jul 95%**. The settled slice read **+3.4%** and the missing slice was **−5.4%**. ⚠ **The bias was WHEN settlement started, not which bets got settled** — win rates were 17.6% settled vs 18.8% unsettled, i.e. nobody was settling the winners and skipping the losers. **The old "+12.6% settled subset vs −1.1% authoritative" discrepancy is now closed; quote −2.0% at BOG and nothing else.**
> **Backfill specifics:** 523 rows written — 499 matched to a result, 3 relocated where the stored `race_time` was wrong (a pre-CHECK-0b cross-race-NB artefact), 35 duplicate rows voided (same horse+race filed twice; no second bet ever existed), 24 settled **non-runner** (horse absent from every race in the day's feed — Kylenoe Dancer and Jonbon verified by hand, plus Chelmsford 2 Apr which was abandoned outright). Non-runners return the stake and are excluded from the ROI denominator, so they close the coverage gap without moving the number. Re-runnable safely: the write is an upsert on `selection_id`.
> **✅ FIXED 6 Aug 2026 — VERIFIED NIGHTLY BACKUPS (`scripts/backup-dbs.sh`, cron 02:00 server / 01:00 London).** There was **no scheduled backup at all** — no cron, no timer, no script; the only copies were hand-made `cp`s. Now both databases (`racing.db` — the money ledger — and `/opt/betfair-bot/data/betfair_bot.db` — real-money exchange records) are snapshotted nightly with `sqlite3 .backup`, **verified before rotation** (`PRAGMA integrity_check` + a row-count floor against live), gzipped, 14-day rolling, logged to `/root/db-backups/backup.log`, non-zero exit on any failure. **THE LOAD-BEARING RULE: old backups are pruned ONLY after the new one verifies** — a job that deletes good copies to make room for a corrupt one is worse than no job. Tested 5 ways: normal run; **restore proved (818 bets, −24.41pt, −1.99% — identical to live)**; missing DB → loud fail, exit 1, other DB still backed up; corrupt DB → caught, exit 1, nothing pruned; retention prunes to 14. **✅ OFF-SITE ADDED 6 Aug 2026 (`scripts/pull-vps-backups.sh` + launchd `com.paulturner.nags-backup-pull`, daily 09:00 on the Mac).** The Mac **PULLS** from the VPS — deliberately not a push. The VPS has no outbound SSH keys, and giving it credentials to push would let a compromised server reach and DELETE the off-site copies, which is exactly how ransomware defeats backups. Pulling keeps every credential on the Mac and leaves the server unable to touch the destination; the pull is read-only against the VPS. Two genuinely independent failure domains: a QEMU VPS at a hosting provider, and a MacBook Pro. **60-day retention on the Mac vs 14 on the VPS** — the longer window is the point, since the settler gap took two months to notice. **Every pulled file is verified** (gunzip + `integrity_check` + a MONOTONIC row-count floor: rows only ever get added, so a snapshot with fewer rows than the best already seen means truncation or a bad restore); failures are quarantined, never silently kept. **No `--delete` on the rsync** or the Mac would mirror the VPS's 14-day pruning and destroy its own history. Tested: first pull; **restore proved (818 bets, −24.41pt, −1.99%)**; idempotent re-run; corrupt file planted ON THE VPS → quarantined, exit 1; row-count regression → quarantined; launchd fired end-to-end. ⚠ Laptop caveat: a closed lid delays the pull to next wake, it does not skip a day. ⚠ **Still only TWO copies — no cloud tier.** Pointing `DEST` at an iCloud/Dropbox folder would give a third, at the cost of putting financial records with a third party; deliberately not done. Old stale copies left in place but marked `data/STALE-DO-NOT-RESTORE.txt`.
>
> **⚠ WHY (the near-miss) — THE DATABASE BACKUPS WERE STALE.** `racing.db` runs in **WAL mode**, so the main file had not been written since 19 Jul while 4MB of commits sat in `racing.db-wal`. Every backup taken with `cp` therefore captured a **stale** file: `racing.db.bak-20260727` contains data only to **19 Jul — eight days missing**, and would have silently lost a week of the ledger if it had ever been restored. **Always snapshot with `sqlite3 racing.db ".backup 'file'"`, never `cp`.** A correct snapshot is at `data/racing.db.snapshot-20260806-prebackfill`. This is unfixed as a recurring practice — the nightly/periodic backup still uses `cp`.
>
> **⚠ MEASUREMENT 14 Jul 2026 — THE SYSTEM IS ROUGHLY BREAKEVEN, NOT BLEEDING. Never quote an SP-based ROI again.** 652 real logged bot picks (73 race days, 26 Mar – 9 Jul 2026) joined to Racing API results. Win-only, 1pt level: **at SP −12.3%; at morning price −10.2%; at BOG −1.1%.** We do NOT bet at SP — CLAUDE.md mandates morning prices with Best Odds Guaranteed, which pays the better of morning/SP. **BOG is worth ~9 points of ROI to us** because our winners drift. **Protecting BOG is worth more than any rule in this file.** Anything that erodes it (taking SP, betting late, losing BOG accounts) costs more than the filters below can gain.
>
> **⚠ REFUTED 14 Jul 2026 — "our NBs out-convert our SELs" (factor 22) is NOT TRUE.** Measured on **289 real races where the bot named both**: SEL finished ahead **50.5%**, NB ahead **48.4%** — a coin flip, with the SEL marginally better on every metric (win 19.7% v 18.0%, place 45.0% v 39.4%). The belief is baked into factor 22 ("Second-String Value") and was the stated reason for the 4 May stake redistribution (race SEL 1.0→0.75pt, race NB 0.5→0.75pt). **It is not supported by the data** — it was recency bias off small samples. Corollary: **backing BOTH the SEL and the race NB costs ~3 points of ROI** vs backing the SEL alone (−15.2% → −18.2% at SP), because the NB is the slightly worse bet and every pound moved into it drags the average down. Both blank in **31.5%** of races. **A staking plan moves variance, not the mean** — if each pick returns 85p per £1, no arrangement of those picks returns more than 85p per £1. The only lever that moves the mean is WHICH HORSES YOU BET.
>
> **⚠ OPEN 14 Jul 2026 — adjusted_score is NEGATIVELY correlated with winning.** Across 334 scored picks, Pearson r(score, win) = **−0.079**. The market's own 1/SP on the SAME picks = **+0.257**. The bookmakers' price predicts our picks' results better than our score does. Score bands, ROI at BOG: <70 **+4.1%**, 70–75 −0.3%, 75–80 **+8.6%**, 80–85 −13.8%, **85+ −31.3%** (n=55, win 16.4%, avg SP 5.56 — bad AND short, so no compensating value). The 85+ figure is NOT the Opus 4.7 inflation artefact: it is unchanged when the 1–9 May window is excluded and is **−57.6% in Jun–Jul alone**. This is the underlying disease; the F1 filter below is only a bandage on its worst symptom. Root cause remains the **positional-block inversion** (Form 22 + Course 15 + Going 15 + Distance 12 = 64 bankable vs Class 12 + Speed 8 = 20 for ability).
>
> **Shadow paper-trade 14 Jul 2026 — SELECTION FILTERS F1 / F2 (`analyst.py` CHECK 16, `config/settings.py`).** Deployed in **SHADOW MODE — logs only, mutates NOTHING** (proven side-effect free by test: gate output with filters OFF is byte-identical to gate output in shadow). `nags_back` stakes real money, so a retro-fit does not touch live picks until watched forward. **Review 11 Aug 2026.**
> **F2 LONGSHOT (the strong one):** drop any selection at a morning price **≥ 11/1**. Evidence: **1 winner from 65 bets, −76.9% ROI at BOG.** The NAP has a 10/1 cap and the NB-of-day a 14/1 cap, but **race SELs and race NBs have NO price cap at all** — which is exactly where those 65 bets live. ⚠ UNITS: `_parse_odds_to_decimal` returns the FRACTIONAL multiplier (11/1 → 11.0), NOT decimal odds — the threshold is **11.0, not 12.0**.
> **F1 HIGHSCORE (the weak one, expected to die):** `adjusted_score ≥ 85` → **DEMOTE** to a flat 0.75pt race SEL, never NAP/NB-of-day. **DEMOTE, not DROP** — the band contains 9 winners incl. **Saddadd (91, 4/1)** and **Grey Dawning (86, 3/1)**, the very horses this file cites as proof premium short-priced NAPs work. The damage is price-dependent: 85+ under 3/1 = **−52.1%**, 3/1–6/1 = **+33.3%**, 6/1+ = **−100%**. Slicing thinner than this is overfitting. The existing general score-vs-market gate CANNOT see this cluster (it needs score ≥82 **AND** odds ≥9.0; these losers are SHORT).
> **Out-of-sample (the reason this is worth doing):** split at 2 May, on data the filters were never fitted to, F1+F2 turn **−7.9% into +5.3%**.
> Flags: `FILTER_SHADOW_MODE` (true), `FILTER_LONGSHOT_ENABLED`, `LONGSHOT_MAX_ODDS` (11.0), `FILTER_HIGHSCORE_ENABLED`, `HIGHSCORE_DEMOTE_AT` (85.0) — all env-overridable. Log lines: `FILTER-SHADOW F2 LONGSHOT:` / `FILTER-SHADOW F1 HIGHSCORE:`. **Success (all 3 or it does not ship):** F2 blocks ≥12 bets with ≤1 winner; the 85+ band underperforms the 75–80 band; shadow-applied ROI beats actual by ≥4pts. **Failure:** F2 blocks 3+ winners ⇒ raise cap 11/1→14/1 (never wholesale revert); F1 demotes 3+ would-be-NAP winners with no offsetting gain ⇒ raise 85→90; the 85+ band comes good ⇒ **drop F1 and ship F2 alone.**

> **F2 PROMOTED TO LIVE — 17 Jul 2026** (`config/settings.py` + `analyst.py` CHECK 16). Shadow is now **per-filter**: **F2 LONGSHOT enforces (drops any SEL/race-NB priced ≥11/1 morning); F1 HIGHSCORE stays observe-only to the 11 Aug review** (the weaker filter, expected to die). Flags: `FILTER_SHADOW_MODE` is now a **master kill-switch** (default **false**; set true to force BOTH filters back to shadow in one move — instant full revert), plus per-filter `FILTER_LONGSHOT_SHADOW` (false=live) and `FILTER_HIGHSCORE_SHADOW` (true=shadow). A filter enforces only when neither the master nor its own shadow flag is set. Live log prefix is `FILTER` (vs `FILTER-SHADOW`). **Why now, off the shadow plan:** three prototypes on 17 Jul (scorer reweight toward ability/intent; market-favourite selector; market-divergence caution flag) all **refuted** as deployable rules — but re-validating on the **670 real logged picks at BOG** confirmed the ONE robust, out-of-sample-stable leak is exactly F2's territory: the market-divergence damage decomposes cleanly into the **morning≥11/1 longshot cluster** (F2 owns it — −77% ROI, 66 picks) **+ the sub-70 low-conviction tail** (the 70+ floor owns it); once both are removed the residual is breakeven. A market caution flag was rejected as **redundant with F2 + the floor** and it **inverted post-2 May**. So F2 is not a new bet-type — it removes the single worst-EV slice the price caps never covered (NAP cap 10/1 / NB-of-day cap 14/1 leave race SELs & race NBs uncapped). **`_enforce_compliance` now re-runs `_rebuild_double` after F1/F2 enforcement** (a live drop can remove a double leg or clear the NAP that CHECK 15 built one line earlier). Local test 3/3: F2 drops the ≥11/1 leg + realigns the double, F1 only logs, master kill-switch reverts both. **Revert:** `FILTER_LONGSHOT_SHADOW=true` (F2 only) or `FILTER_SHADOW_MODE=true` (both). **F1 unchanged — still shadow; its 11 Aug review + success/failure triggers above still stand.**

> **Bugfix 14 Jul 2026 — NH quick-turnaround penalty was missing its WIN condition** (`scorer.py` `_score_edges`, ~line 1052). Factor 11 has ALWAYS read "8-14 days **after a hard win** for 8yo+ = -3", and the rationale is explicit: *"Hard-won races take MORE out of a horse than easy wins — front-runners who made the running are especially vulnerable."* The code checked only `age >= 8` and `days <= 14`. It **never checked whether the horse won last time.** So the penalty fired on any aged NH horse returning inside a fortnight — including horses coming off an *easy* race, which is the exact opposite of the rule's premise. Caught at **Perth 3:51 12 Jul 2026** (C3 Hcap Chase): **Grand Clermont** (10yo, back in 14 days off a beaten 4th in a Class 2 — not a win) was docked **-3** → scored 59.8 → and **WON at 3/1**. Wasdell Dundalk took the same -3 off a **2nd**. Fix: require `_form_chars(runner.form)[-1] == "1"`. Flag: `QUICK_TURNAROUND_REQUIRE_WIN = True` (set False to restore old behaviour). Blast radius on the 12 Jul GB card: **6 of 84 runners moved, all +3.0** — strictly one-directional (it can only remove a phantom penalty, never add one). The ≤7-day **-5** penalty is unchanged — CLAUDE.md defines that one on *last START*, with no win condition, so the code was already correct there. **HONEST NOTE: this did NOT cost us the race.** Fixed, Grand Clermont scores 59.6 and is still **18 points** behind the (losing) NAP Statuario. The 12 Jul loss is a *gap* problem, not a *penalty* problem — see the note below.
>
> **⚠ OPEN — 12 Jul 2026: the deterministic score GAP is not trustworthy, and it silently disables the market swap.** Perth 3:51: Statuario **83.3** vs Grand Clermont **59.8** — a **23.5-point** gap between two horses the market priced **9/2 and 16/5**, i.e. near neighbours. The mandatory market swap (Branch a) only fires when scores are **within 5 points**. If the scorer routinely manufactures 20-point gaps between horses the market considers close, **that rule can essentially never fire.** Same failure on 9 Jul (July Stakes: 9-point gap kept the swap silent; the shorter-priced, better-figured Adaay beat our Hickory Lad — logged then as "the gate was right, the score was wrong"). Root cause is the known **positional-block inversion**: Statuario banked Course 15 + Distance 12 + Going 10 = **37**, plus Class 12, for being a Perth-3m-Good specialist. He genuinely IS one — and he still made a mistake at the 14th and **pulled up** as an 11yo carrying top weight. Note for the record: Statuario was backed **9/2 → 15/8F**, so the market ENDED UP agreeing with the pick. This is NOT a "market was right, figures wrong" case; it is a "the gap was fiction" case. **Do NOT write a rule off this single race** (that is how TS-veto and dual-edge got added and binned). The measurement to run first is the SEL-vs-NB inversion across the full logged sample.

> **Bugfix 19 Jul 2026 — RACE INTEGRITY: cross-race NBs + two selections in one race** (`analyst.py` `_enforce_compliance` CHECK 0b). Two long-standing holes, both fired on the 19 Jul card. **(a) `next_best` had NO same-race constraint anywhere** — not in the output JSON schema (which defines it as just `{horse, odds_guide, reasoning, each_way, adjusted_score}`), not in the gate. The LLM filled the NB slot of picks 1 and 2 with **the next selection in its own list**: Captain Cool (Stratford 15:58) → NB "Illinois", who runs Curragh 16:25; Illinois → NB "Big Gossey", who runs Curragh 15:15. Both were persisted to `racing.db` as `race_nb` rows under the **wrong** `race_time`/`race_name` (ids 708, 710). **(b) "ONE selection per race maximum" appears THREE times in the prompt** (system rule 8, output-format note, race-list preamble) **and nowhere in the gate** — so Captain Cool AND In The Air both survived out of the same 5-runner Stratford chase.
> **Why (a) is the dangerous one:** CHECK 1 (market swap) and CHECK 2 (sub-evens replace) rewrite `sel["horse"]` and `sel["odds_guide"]` but **never touch `race_time` / `race_name` / `course`** — those keys are only ever READ (renderer, line ~2099). Promoting a cross-race NB therefore yields a selection whose horse and printed race disagree. **It was one price tick away on 19 Jul:** Captain Cool 82 vs NB Illinois 77 is a gap of **exactly 5**, which SATISFIES the `score_gap <= 5` half of the market-swap test; only the price test (3.33 not shorter than 1.625) held it off.
> **Money impact — fails CLOSED, but silently.** Traced the full chain into the Betfair bot: `NagsReader.load_today` parses course out of `race_name` ("Course - Race"; `meeting_id` is NULL by design), `_index_picks_by_race` keys by `(normalised course, race_time)`, `_picks_for_market` matches the Betfair market on that key, then `_match_runner_to_pick` requires the horse to be **in that market's runners**. A mismatched pick therefore finds no runner → `continue` → **no bet**. Same bail-out in `nags_lay_fav` (`pick_runner is None` → return). So a cross-race swap could never have backed the wrong horse — but it would have **silently dropped a genuine bet**, logged only at `logger.debug` (not emitted at the live log level). On 19 Jul the mis-keyed rows were inert (a horse can't run in two races, so they never matched) and all three real bets landed.
> **Fix (both subtractive — can only remove a bet, never add one), runs BEFORE every other check:** (i) resolve each selection's race via the existing `_resolve_race_meta` and drop any `next_best` whose horse is not in that race's `runners` list (`sel["next_best"] = {}`, `nb_score = 0`) — this disarms CHECK 1 and CHECK 2 at once, since both guard on `if nb and nb.get("horse")`. **Fails OPEN when the race can't be resolved** (never guess). (ii) dedupe `(course, race_time)` across selections, keeping the higher `adjusted_score`, remapping `nap_index` (→ -1 if the NAP itself was the one dropped — a silent promotion of the survivor to NAP would not be subtractive). Local test 6/6: today's exact output (both cross-race NBs dropped + In The Air removed, Captain Cool kept as NAP); forced cross-race swap trigger disarmed; forced sub-evens + cross-race NB disarmed; **legitimate same-race NB survives untouched** (no-regression); NAP-is-the-duplicate-loser → `nap_index` -1; unresolvable race → NB kept. Log lines: `CROSS-RACE NB DROPPED:` / `DUPLICATE RACE DROPPED:`. **Side effect to note:** a sub-evens selection whose only NB was cross-race now has nothing to swap in, so CHECK 2 falls through to its existing `SUB-EVENS WARNING: … no NB to swap in` path and the selection stays — pre-existing behaviour for NB-less picks, and strictly better than promoting a horse from another race.

---

> **Switch 27 Jul 2026 — judgement model 4.8 → `claude-opus-5`** (`config/settings.py` default + VPS `.env`, commit `a497db8`). Safe because commit `5349c9d` first fixed a latent parser bug: **opus 5 leads its response with a ThinkingBlock**, so `_run_claude_judgement`'s `response.content[0].text` threw AttributeError → the `except` fired the programmatic fallback and the ENTIRE CLAUDE.md judgement layer was silently lost (same shape as the 5 Jun temperature-400 bug; tell = `.1` fallback scores + "Programmatic fallback" note). Fix = scan `response.content` for the first block with `.type=='text'` (identical result for non-thinking 4.8), raise a clear error if none, `max_tokens` 6000→12000 for thinking headroom. **Verify before trusting any 5 output that scores are INTEGERS** (LLM) not `.1` (fallback). Offline 4.8-vs-5 A/B on the 27 Jul card: **identical core** (NAP Amazonian Dream 9/2 86, NB Pearl Eye 5/2 82, 1st SEL Abduction 15/2 80, same double), split only on the throwaway 4th pick, and **5 showed NO score inflation** (no >90, no long-odds NAP) — the historical 4.7 risk did not recur, and the clamp/general-gate guardrails contain it regardless. Deterministic scores are model-INDEPENDENT (same Python), so a swap only moves the judgement/selection layer, which is near its ceiling (additive edge refuted ×4) — expect ~neutral EV, not improvement. **WATCH early cards for re-inflation (NAPs at long odds, scores >90); revert = `JUDGEMENT_MODEL=claude-opus-4-8` in the VPS `.env` (+ settings.py default), one line.** Note: no `temperature=0` determinism pin is possible on 4.8 OR 5 (both deprecate the param), so run-to-run margin variance persists.

> **⛔ STANDING RULE — BEFORE IMPLEMENTING ANYTHING: read `claude-md-before-implementing.md` (this folder) and follow it.** Adopted 1 Aug 2026 at Paul's instruction. It is not optional and not only for large jobs: it defines which changes are "just do it" versus which get the full pre-flight (Goal / Blocking questions with recommended defaults / max 5 ranked assumptions / Plan — then **stop and wait**). Anything touching **stake sizing, the `racing.db` ledger, a live account, scheduling, or data that cannot be regenerated** is full-treatment, no exceptions — which covers most of this project. Investigate the code first: anything findable in under a minute of searching is research owed, not a question to ask. First applied to the daily-card-replacement change below, where it surfaced the add-vs-replace decision *before* any code was written.
>
> **Tightening 1 Aug 2026 — DAILY CARD REPLACEMENT (`main.py` `_save_cherry_picks`, `database.supersede_todays_selections`, `config/settings.py`).** The Operating Policy cap ("maximum 6 selections per day total… 1 NAP") was enforced **per `/run`, never per day**: `_enforce_compliance` only ever sees one run's selection list, and the save path did a bare `INSERT` with no knowledge of what the day already held. So a second `/run` wrote a **whole fresh card at full stakes**. Triggered by 1 Aug 2026: runs on Thirsk *then* Goodwood produced **8 top-level selections, TWO NAPs and £245 staked at £10/pt → −£116.38 (−47.5%)**, one winner from sixteen bets. Historic multi-run days over the cap: 18 Jun (7), and pre-gate 5 May (15), 25/24 Apr (12). **Paul's decision: a later run REPLACES the day's card, it does not add to it.** Implemented as **SUPERSEDE, never DELETE** — this is a money ledger, so rows stay readable for audit with `superseded_at` set, and every live read path filters `superseded_at IS NULL` (the nightly settler in `main.py`, and `NagsReader.load_today` in the Betfair bot so the exchange cannot bet a replaced card). **Rows that already carry a result are never superseded** — they were real settled bets and must keep counting toward the ledger. Idempotent `ALTER TABLE` migration probes `PRAGMA table_info`. Flag: `DAILY_CARD_REPLACE_ENABLED` (default true, env-overridable). Local tests 50/50 including the load-bearing **no-regression case: a single-run day is byte-identical to before**. ⚠ Note for future work: `get_todays_selections` / `get_todays_nap` / `get_todays_next_best` in `database.py` all `JOIN meetings ON s.meeting_id = m.id`, but the live cherry-pick path writes `meeting_id = NULL` by design — so those three (the `/today`, `/nap`, `/nb` Telegram commands) have returned nothing for a long time. Pre-existing, out of scope here, NOT fixed.

> **Tightening 4 Aug 2026 — SIGNAL ALIGNMENT: four places the code read a different signal from this file** (`scraper.py`, `analyst.py`, `config/settings.py`). All four found reviewing the 4 Aug card; each has its own env-overridable flag.
> **(1) GOING GATE WAS READING THE WEATHER FORECAST** (`analyst.py` ~line 1859, flag `GOING_DETAILED_REAL_FIELD`). Option Y's volatility phrase list ("in places", "watered", "showers", …) is specified in this file against the API's **`going_detailed`**. The `Race` model never captured that field, so `analyst.py` **synthesised** one as `going + " " + weather`. On 4 Aug that produced **"Good Showers"** for Ffos Las — a *weather forecast* — which matched `"showers"` and **blocked the day's only 75+ NAP** (Perfect Nation 76, 13/8) on a track whose actual going report read `GOOD (GoingStick: 6.0)`, i.e. completely stable. It failed the other way too: **Catterick's real `going_detailed` was `GOOD, Good to firm in places`** — a genuine listed phrase — and the gate could never see it. Wrong signal in **both** directions since 9 May 2026. Fix: scraper captures the real field; weather no longer feeds the volatility check at all. Empty `going_detailed` **fails OPEN** (never invent a demotion from absent data). ⚠ A weather flag may still be worth having, but as its own signal with its own paper-trade — not smuggled into the going gate.
> **(2) PRICED RUNNERS WERE BEING DROPPED AS NON-RUNNERS** (`scraper.py` `_parse_runner`, flag `NR_PRICE_ONLY`). The 9 Jul 2026 NR fix established that **price** is the authoritative withdrawal signal and noted the old "no jockey = non-runner" heuristic "never fired for a single one". That superseded heuristic was left in place and began doing the *opposite* damage: dropping runners that **are priced** but whose jockey is not yet declared — routine on Irish cards early in the day. On 4 Aug it removed **three priced runners** (Ataboymiley, John Gun, Goeasyonme) from Roscommon 18:00, scored as a **12-runner race against `field_size=15`**; those runners were invisible to every field-relative calculation (top-RPR-in-field, speed ranks, the C4-and-below ability anchor) and to every field-size gate. Fix: missing jockey drops a runner **only when it is also unpriced**, so a card whose market has not opened keeps its full field. **Blast radius on the pinned 4 Aug snapshot: 6 races corrected, `field_size` mismatches 6 → 1, 14 of 247 scores moved (max ±2.0), top scorer changed in 2 races — all of it inside Roscommon, zero GB movement** (GB cards declare jockeys properly). ⚠ Residual: Roscommon 5:25 now reads 18 runners against `field_size=17` — the API quotes a price for a horse it excludes from its own count. That is an API self-inconsistency; the mismatch warning fires, which is the designed behaviour.
> **(3) E/W FLAGS WITH NO PLACE MARKET** (`analyst.py` `_should_be_each_way_from_odds` + CHECK 11, flags `EW_REQUIRE_PLACE_MARKET` / `EW_MIN_RUNNERS_FOR_PLACE`=5). `each_way` was set with **no field-size test at all** — the helper ignored both its `race_name` and `num_runners` params and returned `dec >= 3.0`, and CHECK 11's going demote set `each_way = True` unconditionally. Bookmakers offer no place market below 5 runners. Caught at Lingfield 19:18 on 4 Aug: **Russian Rumour flagged E/W at 17/2 in a FOUR-runner handicap** (the "handicaps are always E/W" rule has no field-size guard) — the bot spotted the problem in its own prose and set the flag anyway. Now guarded, mirroring the 16 May 2026 NB-of-day demote path. **Strictly subtractive — can only turn E/W off, never on, so it can never increase outlay.** `num_runners <= 0` means "unknown" and does NOT block (no regression for callers without a field size).
> **(4) THE CLASS FLOOR FAILED OPEN ON UNCLASSED RACES** (`analyst.py` `_meets_class_floor`, flag `CLASS_FLOOR_BLOCKS_UNCLASSED`). The floor matches substrings of `race_class`; **Irish cards carry `race_class=""`**, which matched nothing, so **every unclassed Irish race passed the floor by default**. On 4 Aug that put a **15-runner Roscommon maiden hurdle with five 150/1 shots** into the day's selections — it did not clear the floor, it *bypassed* it, and it is exactly the form-compressed field the floor was written to exclude. **Paul's decision 4 Aug: missing class is BELOW the floor.** Irish pattern racing still passes — the Group/Grade/Listed test now also reads `pattern`, which is where Irish (and GB `Class 1`) pattern races carry their level. **Cost: the bot stops betting ordinary Irish racing entirely** (Roscommon, Ballinrobe, Sligo, Irish midweek). On the 4 Aug card this cut races reaching judgement from **13 → 6**. Revert is one flag if the volume loss bites.
> Local tests **36/36** (`tests/test_going_gate_field.py`), existing suites unchanged. **Revert:** each flag independently, e.g. `GOING_DETAILED_REAL_FIELD=false`. ⚠ **NOT fixed (judgement-layer prose, not a deterministic gate):** the 4 Aug output claimed *"the higher-scoring Russian Rumour"* under a **NO NAP TODAY** header (Perfect Nation 76 > Russian Rumour 74 on the printed numbers), and overstated Russian Rumour as *"the only runner with a course AND distance win"* — she has a Lingfield win over **16.5f** and a 14f win at **Nottingham**, and was **3rd** in the actual C&D there in May. Prose accuracy is not gate-enforceable; check it at review time.
>
> **⚠ SAME-DAY RESULTS 4 Aug 2026 — two fixes vindicated, one counter-example. CHECK 17 tests now 42/42 (`bd20c6b`).**
> **(1) GOING GATE — VINDICATED, the bug cost real money.** Ffos Las 3:00: **Perfect Nation WON at 13/8F**. Because the pre-fix gate blocked the NAP, the card had `nap_idx < 0`, which flips `main.py` to **flat 1pt stakes for every pick** — so one bad gate under-staked BOTH winners on the card, not just the NAP. Perfect Nation went on as 1pt E/W (+£20.31) instead of a 2pt win-only NAP (+£32.50).
> **(2) NR PRICE-ONLY — VINDICATED in the same race the class floor now blocks.** **Goeasyonme**, one of the three priced-but-jockeyless runners the legacy heuristic was binning as non-runners, finished **2nd of 13 at 125/1** in the Roscommon 6:00. Not a withdrawal — a real runner that nearly won.
> **(3) E/W PLACE MARKET — no data yet** (Lingfield 7:18, 4 runners, win-only under CHECK 17).
> **(4) CLASS FLOOR — COUNTER-EXAMPLE 1 OF 3.** Roscommon 6:00 maiden hurdle (`race_class=""`, `pattern=""`, 13r): **Clay Pigeons WON at 8/11F** (we held 5/4 morning). The floor as deployed would have dropped the race. **Settled-card arithmetic: going-fix-only +£41.25 / both-fixes-as-deployed +£27.50 / what actually happened +£22.81** — so the going fix was worth **+£18.44** and the class floor gave **−£13.75** back, netting **+£4.69**.
> **NOT reverted, deliberately:** n=1, and every analogous revert trigger in this file is 3+ in a 4-week window. The beaten field was **125/1, 300/1, 300/1, 300/1, 50/1, 300/1** — precisely the form-compressed junk the floor targets; we won by backing an odds-on favourite, not by out-reading anyone. It was backed **5/4 → 8/11F**, so at SP our own sub-evens block refuses it: the profit existed only because we held the morning price. **TRIGGER: log every unclassed-race winner the floor would have blocked; at 3 by 1 Sep 2026, revert with `CLASS_FLOOR_BLOCKS_UNCLASSED=false`** (one env flag, no code change). Do not soften piecemeal before then.
> **⚠ SEPARATE FINDING — the scorer has NO opinion on 2yo novice/maiden races, and a low score there must not be read as a negative.** Catterick 2:15 (C3 EBF Novice, 7r): **every runner returned `performance_rating`/`speed_rating`/`ofr` = None**, so all seven got an identical filler block — Course 5.0, Going 7.5, Distance 6.0, Class 6.0, Speed 3.0 = **27.5 of the 100 is neutral padding**. The only separation came from a 1-run form score, jockey and trainer T14. Practical ceiling ≈52–55, i.e. permanently under the Operating Policy 55 floor. **Waakabb was the TOP scorer at 52.2 and WON at 7/4.** The floor skipping that race is correct behaviour (we were blind, not bearish) — but the framework's verdict must be stated as **"no opinion"**, never "disagree" or "against". ⚠ Do **NOT** propose scoring 2yo novices better: that is the additive-edge trap that has now been refuted five times. The legitimate exception is one horse in the field carrying a rating and a win — Perfect Nation (OR 86, form "21") scored **76 v a field topping out at 54** the same afternoon and won — but that gap is one-dimensional ("only exposed horse") and normally just agrees with the favourite, landing it in the F3 short-premium-NAP cell.

> **Tightening 5 Aug 2026 — GOING GATE: the phrase list mixed two different signals** (`analyst.py` `_going_volatility_phrases`, flag `GOING_VOLATILITY_SPATIAL_PHRASES`, default **false**). Option Y exists because of **Hexham 9 May 2026**: the card read Good overnight and the race ran on Soft. The rule is about going **CHANGING between taking the price and the off**. Seven of the nine listed phrases do forecast change ("watered", "watering", "showers", "rain forecast", "could change", "becoming softer", "drying out"). Two do not: **"in places"** and **"in the back straight"** describe how the going varies **across the track right now**, on a surface that is otherwise stable — ordinary clerk-of-the-course phrasing. **Caught 5 Aug 2026:** Pontefract reported `GOOD TO FIRM, Good in places (GoingStick: 8.4)` — a firm, settled surface described precisely — and the gate **blocked the day's only 75+ NAP** (The Good Biscuit 77.2, 3/1, the Racing API's own tip) with **measured drift of ZERO**. It fired on **2 of 4 GB courses** that day and on Catterick the day before, i.e. roughly half of all turf cards. Note the irony: the 4 Aug fix (1) restored the *real* `going_detailed` field and cited Catterick's "Good to firm in places" as the false NEGATIVE the old synthetic string could never see — **it was never a signal worth seeing.** Fix: split the list into `_GOING_TEMPORAL_PHRASES` (always checked) and `_GOING_SPATIAL_PHRASES` (checked only when the flag is on). The **drift half is untouched** — a genuine ≥2-ordinal-step move still demotes, so Hexham would still be caught today.
> **⚠ THIS CHANGE ADDS MONEY AT RISK — the first one this week that does.** The 4 Aug fixes were all subtractive (they could only remove a bet). This one **re-enables NAPs (1pt → 2pt) and removes forced E/W**, so if it is wrong it costs more per occurrence than anything else shipped this week. **PAPER-TRADE 7 days to 12 Aug 2026:** log every card where a NAP is now allowed that the old list would have blocked. **Failure trigger: 2+ such NAPs beaten on a card whose going actually moved during the day ⇒ `GOING_VOLATILITY_SPATIAL_PHRASES=true`.** Reverting restores the exact pre-5-Aug behaviour in one env var.
> **Method note (worth keeping):** the first instinct was to measure how OFTEN each phrase fires across a sample of cards. That answers the wrong question — frequency is not the test, **semantics is**. A phrase that genuinely forecasts change earns its demotion however common it is; a phrase that describes a stable surface never does, however rare. Paul stopped the measurement before it ran.
> **✅ REVIEW CLOSED 12 Aug 2026 — PASS, flag stays `false`. Failure trigger not met and not close.** Measured all 44 GB/IRE course-days 5–12 Aug. **Spatial phrases fired on 22 of 44 (50%)** — the old list would have demoted half of all cards. **Of the 14 spatial firings on courses where drift was measurable (racecard going vs the going in the results feed), ALL 14 drifted ZERO ordinal steps.** Not one course in the window moved a single step, let alone the 2 the drift half requires. **Temporal phrases fired ZERO times in eight days**, so the gate as a whole did nothing all week. **Only ONE NAP was enabled by the change** — Sparan Nua (6 Aug, Leopardstown, 11/8, 4th) — against a trigger needing 2+ *and* actual going movement; and that NAP is confounded anyway (its +3 hot-stable was 2-from-3, which the T14 min-runs guard independently kills → true score 72.6, no NAP). Supporting: picks on spatial-flagged cards returned **+5.02pt over 14 bets** vs **−8.10pt over 12** on unflagged cards — small sample, variance-dominated, cited only as "does not support reverting", not as evidence for the change. **⚠ STATE THE LIMIT HONESTLY: this was a dry, settled high-summer week — Good To Firm nearly everywhere, nothing drifted anywhere. A rain rule was never tested. The correct reading is "no evidence to revert", NOT "proven safe".** The drift half (≥2 steps) remains completely untested in live conditions since Hexham. **Re-check after the first genuinely wet card**; if a course drifts ≥2 steps and the gate fails to demote, that is the real test.

> **Tightening 6 Aug 2026 — T14 MINIMUM-RUNS GUARD: factor 21's sample-size rule was never implemented** (`scraper.py` `_parse_runner`, `scorer.py` `_score_trainer` + `_score_edges`, `config/settings.py`). Factor 21 has said since v2: *"Small samples distort (1 from 2 = 50% but meaningless). **Minimum 5 runs in 14 days for the bonus.**"* The code never checked it. `scraper.py` read the API's `trainer_14_days` dict and kept **only `percent`**, discarding `runs` and `wins` — and `scorer.py` carried a comment openly admitting the gap (*"Need to check runs count too — but we only have percent in Runner"*). **TWO scoring sites were affected, not one:** (a) **`_score_trainer`, worth 5 of the 100 points** (5.0 at pct ≥ 25 … 1.5 at pct < 5) — this is the bigger one and the easier to miss; (b) **`_score_edges`**, hot-stable +3/+2 and cold-stable −1.
> **Caught auditing the bot's own NAP on 6 Aug 2026** (Leopardstown 6:00 Desmond Stakes, Group 3): **Sparan Nua 11/8 scored 75.6 and was NAP'd at 2pts**, where the *"Hot stable (67% 14d)"* selling the pick was **J S Bolger, 2 wins from 3 runs**. Guarded she scores **70.1 (−5.5)** — below the 75 NAP line **and no longer top scorer in her own race** (Chicago Critic 72.5). The correct output was a no-NAP flat-stakes day. The bot's prose had sold it as *"Bolger yard flying at 67% over 14 days"*.
> **Below the threshold each site falls back to what it would do with no 14-day data at all** — site (a) to the static `TOP_*_TRAINERS` list (the code's own comment calls the 14-day block *"more current than static lists"*, so when it is untrustworthy the static list is the right fallback), site (b) to no bonus. **Missing/unparseable `runs` FAILS OPEN** — absence of a count is not evidence of a small sample, and on the 6 Aug card all 400 runners carried both keys, so that branch is theoretical.
> **⚠ THE COLD HALF IS HELD BACK ON PURPOSE** (`T14_MIN_RUNS_APPLY_COLD`, default **false**). Suppressing a phantom **hot bonus** is **subtractive** — scores only fall, bets can only be removed, the kind of change that has actually worked here. Suppressing a phantom **cold penalty** is **additive**. ⚠ **Implementation trap worth remembering:** site (a)'s static-list fallback runs in BOTH directions, so a 0%-off-1-run yard would have RISEN 1.5 → 2.5 — an additive change smuggled in under a subtractive one, and the first build did exactly that (66 runners moved UP). The fallback is now **clamped** so it can only ever lower a score while the cold half is off; `APPLY_COLD=true` lifts the clamp and enables the −1 suppression together.
> **Blast radius, pinned 6 Aug card (373 runners / 46 races): 12 runners moved, ALL DOWN; ZERO runners with 5+ runs moved at all; top scorer changed in 2 races, and only ONE of those passes the class floor — the Desmond.** Cold half, if enabled, would move 66 runners up and change the top scorer in 3 more races, **all of them already class-floor-blocked**. Zero horses lose a compound-signal +5 either way. Local tests **36/36** (`tests/test_t14_min_runs.py`), including the load-bearing no-regression case: **flag off ⇒ output byte-identical to pre-6-Aug** (verified across all 373 scores, breakdowns and edge details).
> **Paper-trade 7 days to 13 Aug 2026:** log every `T14 SMALL SAMPLE:` suppression and whether the suppressed horse won. **Failure trigger — 3+ suppressed horses win where they would otherwise have been selections ⇒ lower `T14_MIN_RUNS` to 3 before reverting.** Revert: `T14_MIN_RUNS_ENABLED=false` (one env var, restores exact pre-6-Aug behaviour).
> ⚠ **Method note:** this bug was invisible to every gate in this file because it is upstream of all of them — the gates check scores, prices and class, never *how a score was built*. It was found only by hand-auditing one selection's breakdown against the rubric. Worth repeating on any pick that looks marginal.

> **Tightening 6 Aug 2026 (PM) — EDGE-BLOCK RUBRIC ALIGNMENT: three bonuses the code paid that this file never specified** (`scorer.py` `_score_edges`, `config/settings.py`). Follow-up to the T14 guard above, and prompted by it: **every gate in this file checks scores, prices and class — none of them can see HOW a score was built**, so a rule-vs-code mismatch is invisible until someone hand-audits a breakdown. Full line-by-line audit of `_score_edges` against the edge-factor list, measured on **1896 runners across all GB/IRE cards 1–6 Aug 2026**. Three removals shipped, each behind its own flag (defaults **off** = corrected state; set `true` to restore the old behaviour independently).
> **(1) `SPEED_DOMINANCE_BONUS_ENABLED`** — a field-relative lead on `max(RPR, TS)` paid **+5** (≥20 clear), **+3** (≥10) or **+1** (≥5). **No such edge factor exists in this file.** The only speed guidance beyond the 8-point Speed Figures factor is factor 6's TOPSPEED LEADER RULE, which is explicitly *narrative* ("deserves serious selection consideration") and assigns no score. It also **double-counts `_score_class`**, which already scores rating-vs-field, and its worst property is that it inflates precisely the best-figure favourites sitting in the measured **F3 short-premium-NAP losing cell**. 47 firings / 1896 (2.5%), 9 of them +3 or +5. **The lead is still computed and still reported — at ZERO points** — so the judgement layer can act on it where the rubric intends.
> **(2) `UNKNOWN_HEADGEAR_BONUS_ENABLED`** — the first-time-headgear ladder's `else` branch paid **+2 for any code it did not recognise**. Factor 15 grades **four** types (blinkers, visor, cheekpieces, tongue-tie); hood and eyeshield are not in it. 11 firings in 6 days, every one a hood. Note kept at zero points, which also logs which codes actually appear.
> **(3) `OR_ABOVE_FIELD_INTENT_SIGNAL`** — labelled "class drop detection", it awarded a **silent** intent signal (no line in the details) for being rated **8lb+ ABOVE the field average** — i.e. for being the best-handicapped horse, the **opposite** of a class drop, and in a handicap merely a description of the top weight. The genuine rubric item (factor 20 signal 3) is already counted by the class-drop kicker, so this was a second, wrong implementation of the same thing. Removing it is **numerically a no-op today** — see the compound finding below — so it exists to stop a future spurious +5.
> **Blast radius (1–6 Aug, 1896 runners / 209 races): 58 runners moved (3.1%), ALL DOWN** (−1.0 ×38, −2.0 ×11, −3.0 ×7, −5.0 ×2); **top scorer changed in 3 of 209 races** — two unclassed Irish (class-floor blocked) and one a Class 4 topping out at 53.6, far below the 70+ betable gate — so **no race that would reach LLM judgement changed**. Of **28 real logged picks** in the window, **one moved, by −1.0** (Northern Express, 1 Aug NAP, 86.2 → 85.2; it lost anyway). Tests **29/29** (`tests/test_edge_block_rubric.py`) plus the no-regression case: **all three flags on ⇒ output byte-identical to pre-change across 1896 runners, scores AND edge-detail strings.** ⚠ **State this honestly: it is hygiene, not edge, and is not expected to move ROI.** The case for it is that SPEED DOMINANCE *can* hand +5 to a NAP candidate on any day; missing the betting zone this particular week was luck, not structure.
> **⚠ THE BIG FINDING — SIGNAL COMPOUNDING HAS NEVER FIRED. Zero times in 1896 runners.** Factor 20 calls it *"THE MOST IMPORTANT EDGE FACTOR"* (3+ intent signals, +5, win rate 8% → 18-22%). The ceiling ever reached is **2 signals, on 14 runners**. It is dead because **five of its nine listed intent signals do not exist in code**: jockey upgrade, supplementary entry, single long journey, return to preferred distance/going, tactical apprentice claim. **DO NOT "fix" this by implementing the missing signals** — that is the additive-edge trap, refuted five times. The honest reading is that this file describes a system more capable than the one running, and that gap is worth knowing rather than closing.
> **Also found, NOT fixed (each needs its own pre-flight):** ▸ **"Optimal return window +1"** (14–42 days) is not in the rubric and fires on **53% of all runners** — because it is near-universal, removing it compresses the whole field rather than trimming outliers, so it is *not* cleanly subtractive. ▸ **Mares' allowance +4 is dead code** (tests `race_class` for "grade 1/2"; `race_class` contained "Grade" in **0 of 6 days** — pattern races carry `pattern="Group N"`, `race_class="Class 1"`, exactly as the 5 Jun 2026 note predicted) — **⚠ but the naive fix is HARMFUL:** the only G1/G2 in the window was the **fillies-&-mares Lillie Langtry (`sex_restriction='F & M'`, 7/7 mares)**, where the allowance is no edge at all and reading `pattern` alone would inflate a whole race against every other race at ranking time. The correct fix needs **`sex_restriction`**, which the API returns and the scraper does not capture. The same dead check in **`_score_weight`** IS safe to fix — it is already guarded by `my_weight < max_weight`, which self-cancels in a mares-only race. ▸ First-time blinkers **+5 has no "respected trainer" check** (the rubric requires one) and includes geldings where the rubric says colts. ▸ Quick-turnaround −5 includes **bumpers**; factor 11 scopes it to "hurdles or fences". ▸ Wind surgery uses `official_rating or 999`, so a **missing OR** silently kills the bonus and prints "TS 87 well below OR 999". ▸ **Never implemented at all:** blinkers-removed −5 (acknowledged in a code comment), stable confidence +3, superior sectionals +3, gallop reports +3, top Flat jockey in NH bumper +3, travel distance +2, apprentice claim +2, fresh from break +2, pace scenario +2. Most need data we do not hold — honest, but it means the deterministic layer is structurally blind to them and only the LLM can supply them.
> **Net: the edge block awarded ~3 bonuses this file does not contain and fails to award ~10 it does.** Paper-trade 7 days to 13 Aug 2026 (same window as the T14 guard). **Failure trigger — 3+ races where the horse that lost SPEED DOMINANCE points wins and our replacement top scorer loses ⇒ `SPEED_DOMINANCE_BONUS_ENABLED=true` and reopen the question of writing it into the rubric properly.**

> **⛔ F1 HIGHSCORE RETIRED 11 Aug 2026 at its scheduled review** (`config/settings.py`, `FILTER_HIGHSCORE_ENABLED` default true → **false**). It was shadow-only throughout, so **no selection and no stake changes** — it simply stops logging a filter we have now decided against. **F2 LONGSHOT is unaffected and stays live.**
> **It failed its own pre-registered bar.** Required (written 14 Jul): *shadow-applied ROI beats actual by ≥4 points*. Delivered: **+0.39 points** over 103 bets (−13.95% → −13.56%). Only **9 picks in four weeks** reached 85+. On those 9 it made ROI **worse** — actual −5.44pt on 25.0pt staked (−21.8%) vs F1-applied −2.72pt on 10.5pt (**−25.9%**). ⚠ **It "saved" 2.72pt purely by staking less: total P&L always improves when you bet less, so judge a filter on ROI, never on P&L saved.** It also demoted **two winners**, including **Pershaada, a 3/1 NAP that WON for +7.2pt** — the biggest return in the band. The other pre-registered trigger (*demotes 3+ would-be-NAP winners ⇒ raise 85→90*) was not reached at 2, so the outcome is retirement, not re-tuning.
> **⚠ THE WIDER LESSON — the premise had already weakened and nobody re-checked.** F1 was built on *"85+ = −31.3% ROI (n=55)"*. After the **6 Aug ledger reconciliation** re-settled every bet at BOG, those **same 55 picks read −15.8%**. The filter was designed on numbers that the ledger fix superseded. **Every filter built before 6 Aug should be re-derived against the reconciled ledger before its review — that includes F3 (review 16 Aug) and F4 (10 Sep).** Note also the 85+ band had the **highest win rate of any band** in the shadow window (22.2%): it is a *price* problem, not a picking problem, and demoting a whole score band was too blunt an instrument. Revert = `FILTER_HIGHSCORE_ENABLED=true` (returns to shadow, since `FILTER_HIGHSCORE_SHADOW` still defaults true).

> **Shadow 10 Aug 2026 — F4 TOP-2 PRICE RED FLAG (`analyst.py` CHECK 18 + `_top2_price_flag`, `config/settings.py`). LOG ONLY — mutates nothing.** ⚠ **DO NOT APPLY THIS AT SCORING TIME.** It is recorded here as the operational change-log, not as a selection heuristic; acting on it would contaminate the very trial it exists to run. Score races exactly as before.
> **What it flags:** a race where, among BETABLE runners (above evens), the top DETERMINISTIC scorer is LONGER-priced at morning odds than the second. **Measured on 499 premium (Group/Grade/Listed/Class 1–3) GB+IRE races 1 Apr – 9 Aug 2026 that pass every live gate**, re-scored and joined to results, P&L at BOG, with a holdout declared before looking (discovery 1 Apr–12 Jul / holdout 13 Jul–9 Aug). In the **189 flagged races the top scorer wins 6.4% (discovery) / 6.1% (holdout)** against a ~15% base rate — ROI −63% / −73%. Backing both legs and simply **skipping** flagged races beat the status quo by **+172.5pt win-only / +221.2pt E/W** (bootstrap 96.8% / 90.6%), and dropping the whole race beat dropping just the bad leg (+123.0 / +129.3).
> **⚠ WHY IT IS SHADOW AND NOT LIVE:** on our **288 REAL logged picks** the effect **INVERTS in the holdout** — status quo +3.5% vs drop-race −13.2%, and the picks it would have dropped returned **+33.9%** (n=33). Not a refutation, but unresolved, and unresolved does not go near the card. Plausible (unproven) explanation: the judgement layer already ducks the worst flagged spots, so only the benign remainder reaches the card. **Review 10 Sep 2026.** Ship criterion: flagged races must underperform unflagged ones **on our own picks** in the forward window, same direction as discovery. If the inversion repeats, drop the idea.
> **⚠ SEPARATE AND ALREADY ACTIONABLE — THE MARKET SWAP IS WORTH NOTHING IF BOTH LEGS ARE BACKED.** Paul backs the SEL **and** the race NB. A swap then only relabels which horse is called SEL: **measured P&L delta at level stakes = +0.0pt across all 499 races.** Its entire value is *stake allocation* under the code's real 1.0pt SEL / 0.5pt NB weighting — **+23.7pt** (live gap≤5) or **+36.7pt** (any gap) over 4.5 months. The 6-for-6 live record is real but it is **staking, not selection edge**, and it reframes the long-running "should we widen the gap" question (28 Jul, `project_market_swap_gap`) as a **staking** question. Two hypotheses from the same run were **killed by the holdout**: "rank 2 beats rank 1" (discovery −15% vs −42%; holdout **inverted** to −72% vs −28%) and "score gap >10 → back rank 2" (+34% → **−60%**). Both would have shipped on a 4-week look — the exact sample size that produced the July +17pt reweight mirage.
> Flags: `FILTER_TOP2FLAG_ENABLED` (true), `FILTER_TOP2FLAG_SHADOW` (true = log only), plus the `FILTER_SHADOW_MODE` master. Log line: `FILTER-SHADOW F4 TOP2-REDFLAG:`. Tests **17/17** (`tests/test_top2_flag.py`) including the load-bearing no-regression case — **gate output byte-identical with the flag on and off** — and the live helper was pinned against the backtest on all **499/499** real races. Method note: the 131-day racecard+result harvest is cached at `data/harvest/*.json.gz`, so the flag is **fully recomputable after the fact** and re-analysis costs no API calls. ⚠ Joining racecards→results: use `race_id` (both carry it), and **strip the parenthesised country code** the results endpoint appends ("Celestra (FR)") or 100% of rows silently fail to join.

> **Relabel 12 Aug 2026 — the zero-point figure-leader note named the wrong metric** (`scorer.py` `_score_edges`, note-only branch). Since the 6 Aug audit stripped its points, the field-relative figure lead has been reported as a **note whose only job is informing the LLM** — and it read `"Speed leader: best fig N leads field by Xpts"` while computing **`max(RPR, TS)`**. Measured over 8 days: **55 of 69 firings were the RPR, not the Topspeed** — so four times in five the word "Speed" described a performance rating. It duly misled the judgement layer: on 12 Aug the bot published *"Sovereign View… **the clock's outright leader**"* (Kempton 20:00) when his **TS 78 was third in the race** (Gallant 79, Final Night 78 level). His RPR 96 *did* lead by 6, and RPR-over-OR +14 is legitimate in a handicap — but that is the handicapper's opinion, not the stopwatch. Now reads `Best figure {N} ({RPR|TS}) leads field by {X}pts — best of RPR/TS, NOT the Topspeed clock (note only — not scored in rubric)`. **Zero scoring impact: 0 of 2,460 runner scores moved across 8 days** (verified by diffing against the pre-change scorer), and the three bonus-enabled wordings are untouched so `SPEED_DOMINANCE_BONUS_ENABLED=true` still reproduces pre-6-Aug output byte-for-byte. Tests **36/36** (`tests/test_edge_block_rubric.py`, section 1b). ⚠ **Deliberately NOT narrowed to TS-only** — that would silently drop the RPR-leader signal and is a behaviour change dressed as a rename. ⚠ **This block still does NOT implement factor 6's TOPSPEED LEADER RULE** (which is TS only, 3+ clear, **and 5/1 or bigger**); implementing that is a missing-signal addition, i.e. the additive-edge trap refuted five times, and it is **not done**. Code comment corrected to stop claiming otherwise. **Method note: every gate in this file checks scores, prices and class — none can see the PROSE the judgement layer writes, nor the strings it is fed. This was found by reading the bot's own output against the data, which remains the only way these surface** (cf. the 6 Aug T14 audit).
>
> **⚠⚠ PROVENANCE 12 Aug 2026 — THE SPOTLIGHT IS MACHINE-GENERATED. THE OVERRIDE IS WITHDRAWN.** The Racing API's `comment` field — the input this file calls MANDATORY and grants the power to **override the figures** — is generated prose derived from the same structured fields we already score (rating rank, form string, days off, weight, draw, trip/going flags), **not** a human form student's read. Caught reading the 12 Aug card: the API shipped a generator's own scratchpad live — *"Dandana showed her best when winning one start back — **sorry, a winner \*\*five\*\* starts back**, … `---` `Let me recount carefully:` `Latest first: 4th (1), unplaced (2), unplaced (3), 4th (4`"* — raw markdown, visible reasoning, **truncated mid-token**. Not isolated: across **9,619 commented runners** the text runs one rigid skeleton, and quality changed **~30 Jul 2026** (template-phrase rate **40% → 62%**, artefacts begin; 1 artefact in the 23 days before, every day after). It was already generated before 30 Jul — 20/25 Jul read *"he's our second-highest-rated in this seven-runner field"*. ⚠ **THE DATA IS CORRECT; THE DERIVATION IS NOT** — Dandana's `form` (`140-04`) was fine, the generator fumbled counting backwards through it and self-corrected (its final answer, five starts back, is right). **We read `form`/`rpr`/`ofr`/`lbs`/`draw`/`last_run` straight from the same payload, so the comment re-derives — with errors — data we already hold exactly.** ⚠ **Method limit: the field is 100% empty before 7 Jul in the 131-day cache — that is a ~5-week API retention window, NOT evidence about the past.** **Three consequences, all now written into the body of this file:** **(1) OVERRIDE WITHDRAWN** — the narrative *is* the figures, so it can no longer outweigh them; the Jaipaletemps case is retained as the **standard** a comment must meet (genuinely external insight — *"all wins came under a 7-10lb claimer who isn't riding today"* — findable nowhere in the structured data), and the test is *"could this have been derived from the fields we already read?"* If yes, it is not an override. **(2) NEGATIVE-PHRASE DOWNGRADE KEPT, DELIBERATELY** — measured on 1,652 betable gate-passing runners, phrase-carriers won 5.0% v 9.9% and returned −51.8% v −17.9%, **but vs the price the difference is −0.0073 A−E/bet, 95% CI [−0.044, +0.033], spanning zero**; mean score 56.0 v 60.9, and **"hard to fancy" is 644 of 798 hits, rendered from low rating rank — it double-counts `_score_class`.** Kept because those horses still lost heavily and our picks do not track the market perfectly; **removing it would let more of them through, the wrong direction for a system whose only proven edge is subtractive.** It must never outweigh a strong figures case: **Supreme King's comment read "hard to fancy" purely for ranking 6th of 7 on RPR and he WON at 4/1** (Salisbury 15:00, 12 Aug). **(3) RULE 18's SPOTLIGHT TRIGGER IS EFFECTIVELY DEAD** — its excuse phrases appear **14 times in 9,619 runners (0.15%)**; do NOT loosen the trigger to compensate. **Deterministic Rule 18b is unaffected** (it reads class tiers and beaten margins, not prose). ⚠ **~25–30% of runners have NO comment at all** — On Message had none and **won the 12 Aug Listed at 14/1**; a missing comment is **no information**, never a negative. **✅ RAISED AND RESOLVED 13 Aug 2026.** The Racing API reproduced all six cases and our counts (3,125 empty v our 3,123), and confirmed the contract: **"Comment is the single free-text analysis field, generated by us from our own form data. Spotlight is retired."** — **the withdrawal above is now VENDOR-CONFIRMED, not inferred.** Cause: comment generation moved from manual review to an **automated overnight pipeline on 29 Jul 2026** with faulty truncation/hygiene validation (first bad cards 30 Jul — our measured boundary exactly). **Fixed 12 Aug** at validation; **stored data repaired in place** — 35 defective comments 17 Jul–13 Aug **plus 388 race verdicts with trailing markdown we had NOT spotted** (we audited runner `comment` only, never race-level `verdict` — audit every free-text field next time, not just the one in front of you). **Independently verified 13 Aug: 5/5 quoted cases clean, 0 markdown verdicts in 53 races on 30 Jul, 0 artefacts on the 13 Aug card.** ⭐ **AND THE BIG ONE — the 24.5% empty rate is EDITORIAL POLICY, not failure: they deliberately publish NO comment for novice/maiden NON-HANDICAPS** ("form-based commentary would not meet our reliability bar"; 2,708 of 3,125). Measured 13 Aug: **maiden non-hcap 41/41 = 100% empty, novice non-hcap 40/40 = 100%, handicap 1.8%, Listed 0%.** So **an empty comment means "novice or maiden" — never a negative.** ⚠ **This converges with the 2yo data void** (same races return RPR/TS/OR = None): **novice/maiden non-handicaps are blind on BOTH axes by design**, the 55 floor skipping them is right, and the verdict there is **"no opinion"**, never "against". Template drift 40%→62% acknowledged as an open quality item. **If they ever revert to human-written copy, this whole note must be revisited** — the fix was output hygiene, NOT provenance.
>
> **⭐ NEW SOURCE 13 Aug 2026 — SPORTING LIFE IS NOW THE HUMAN QUALITATIVE READ, ALONGSIDE (NOT REPLACING) THE RACING API.** Direct consequence of the provenance finding above: the API's `comment` is generated from form data and can only restate the figures, so the framework had **no source at all** for the external insight the Spotlight override was written for. Sporting Life still employs human analysts. **Proven the same day on the bot's own top pick:** the API said Sudbury Hill *"arrives on the back of a win last time out… a strong contender"* (i.e. `form[-1]=='1'`); Sporting Life said *"Cheekpieces on first time when narrowly resuming winning ways in **4-runner** C&D handicap latest. **Vulnerable off 3 lb higher.**"* Verified against the API: that C&D win was `RUNNERS=4`, off **OR 77 → 80**, with `headgear_run` now **2** — and **three of his last five starts were juvenile hurdles**, his only competitive Flat run being **12th of 14, beaten 28¼L**. Every pillar of a 79.1 traced to one four-runner race. **It killed the NAP.** Two more the same day: Rossa Raheen *"far from exposed on just her **second start over 1½m**"* (explains low figures — upgrade) and Auld Toon Loon *"failing to keep straight when **eighth of 22**"* (excuses the last run — though Rule 18 guard (ii) correctly blocked a score lift, 3 of his last 4 being poor).
> **SCOPE — read this before touching it.** ⚠ **LLM JUDGEMENT LAYER ONLY. It NEVER reaches the deterministic scorer** (verified: **0 of 2,460 scores moved**, diffed against the pre-change scorer; `grep sl_comment src/scorer.py` = 0). ⚠ **PRICES, ratings, going and field size STAY WITH THE RACING API — never read Sporting Life's `current_odds`.** They are not live: on 13 Aug it showed **Parlando 4/1 against 12/1 across all 32 bookmakers**, and Law Court 10/1 against 10/3. Every odds-keyed gate (F2 longshot, NAP cap, sub-evens block, market swap, BOG) would break silently. ⚠ **JOIN ON COURSE+DATE THEN NORMALISED HORSE NAME — never on time or race name.** SL runs **an hour behind** the API (18:41 v 19:41 for the same race) and words races differently ("Handicap" v "Handicap Stakes"); strip parenthesised country codes as for results. **Fetched ONLY for races that already passed every gate** (Paul: *"100% only for races that pass the gate"*) — 5 races on the 13 Aug card, not the ~108 a full index implies; cached, paced, and `robots.txt` carries no Disallow. **FAILS OPEN BUT LOUDLY** (Paul: *"fail open, but must tell us"*) — the card proceeds on API data alone and the reason is prepended to `notes`, never merely logged, because a silent degradation is exactly the 5 Jun 2026 failure that hid the total loss of the judgement layer for a day. **Bonus:** SL ships machine-readable `insights` (`FIRST_TIME_CHEEK_PIECES`, `TRAVELLERS_CHECK` — the latter maps to factor 17, never implemented) and explicit headgear `count`, so cheekpieces `count:1` states first-time unambiguously. ⚠ **These are SURFACED to the LLM, NOT SCORED** — implementing missing rubric signals off them is the additive-edge trap, refuted six times. **Live match rate 31/31 runners.** Tests **20/20** (`tests/test_sportinglife.py`). Flags: `SPORTINGLIFE_ENABLED` (**true**), `SPORTINGLIFE_TIMEOUT`, `SPORTINGLIFE_DELAY`. **Revert = `SPORTINGLIFE_ENABLED=false`, one env var.**
> **✅ LIVE 13 Aug 2026 — CHECK 19: A NAP REQUIRES SPORTING LIFE CORROBORATION** (`analyst.py`, flag `NAP_REQUIRES_SL_CORROBORATION`, default **true**). Paul's *"if they both join up, the case is even stronger"*, cashed out **SUBTRACTIVELY — it makes the NAP HARDER TO EARN and can never make a stake bigger.** Aimed at the NAP slot, which three independent measurements identify as where the ledger bleeds. **⚠ "Corroboration" is NOT mere presence** — 253 of 269 runners on the 13 Aug card carried a comment, so a presence test would never fire. It means **the human read does not undermine the pick**: the NAP is demoted to flat stakes when the Sporting Life text contains disqualifying language (`_SL_DISQUALIFYING`) **or** when Sporting Life is demonstrably working yet has nothing on that horse. **FAILS OPEN BY CONSTRUCTION** — on an outage no runner carries a comment, so the check is inert; a third-party website can never cost us a NAP. **Calibrated on the full 269-runner 13 Aug corpus: fires on 6.7% of all runners and 2 of 6 scoring 75+ — selective, not a blanket.** It blocks the founding case (Sudbury Hill, *"**Vulnerable** off 3 lb higher"*) and passes Rossa Raheen (*"could run another big race off only 2 lb higher"*). ⚠ **Phrase list deliberately excludes ambiguous wording:** *"hard to see"* reverses in context (*"hard to see him beaten"*) and *"not certain to stay"* is routinely softened by Sporting Life (*"…but is respected"*). Zero-firing phrases are KEPT — per the 5 Aug going-gate lesson, **frequency is not the test, semantics is**. Errors are one-directional and cheap: a false positive costs a NAP (2pt → flat), never a bet. Tests **30/30**; 0 of 2,460 scores moved. **Revert: `NAP_REQUIRES_SL_CORROBORATION=false`.**
> ⚠ **METHOD NOTE — the first build of the CHECK 19 tests produced TWO FALSE PASSES.** The fixture left `RunnerScore.total` at its default 0, so the **ANCHOR CLAMP (CHECK 0)** pinned the LLM's 79.1 to 14, the NAP was blocked for scoring under 75, and CHECK 19 never ran — while the test asserting "blocks the founding case" went green for entirely the wrong reason. **When testing any compliance CHECK, set `total` to match `adjusted_score` or an earlier gate will silently pre-empt yours.**
>
> **Shadow 13 Aug 2026 — F5 POSITIONAL BLOCK (`analyst.py` CHECK 20 + `_positional_block`, `config/settings.py`). LOG ONLY, mutates nothing. Review 10 Sep 2026.** ⚠ **DO NOT APPLY THIS AT SCORING TIME** — it is the operational change-log for a trial, not a selection heuristic; acting on it would contaminate the window it exists to measure. Score races exactly as before. **What it flags:** a selection whose **Course+Going+Distance total ≥ 30** (that block is **42 of the scorer's 100 points**). **Measured on 7,023 betable runners in gate-passing races + 352 real logged picks, 1 Apr – 9 Aug, BOG, holdout 13 Jul declared before looking.** **RAW SCORER — the highest-block runner in a race v the lowest: A−E/bet −0.0513 v −0.0087, difference 95% CI [−0.076, −0.008] — EXCLUDES ZERO, and holds in BOTH windows (holdout stronger, −0.072 v −0.017).** **REAL PICKS — block ≥30 v <30: ROI −41.4% v +19.0%** (discovery −30.2% v +0.5%; holdout **−59.3% v +70.2%**). Not price (3/1–6/1 −35.6% v +33.3%; 6/1+ −53.7% v +38.0%); not just the NAP slot (appears in nap, selection and race_nb). ⭐ **WHY IT IS WORTH WATCHING: every previous "raw scorer is bad in segment X" finding INVERTED on real picks — handicaps (#9), few-run horses (#10), tied blocks (#11). This one does not invert; it gets stronger. That is the only reason it is not already a refutation.** ⚠⚠ **WHY IT IS SHADOW AND NOT LIVE: on our OWN picks the difference is −0.0650 with 95% CI [−0.140, **+0.011**] — IT SPANS ZERO.** n=352 does not establish it however large the spread looks. **`next_best` INVERTS** (−19.9% v −43.7%), 1 of 4 slots going the wrong way. And it would touch **43% of all picks** — not a tweak, and this project has been burned repeatedly by large four-week effects that evaporated (F1 most recently). **PRE-REGISTERED BAR — ship only if ALL THREE hold: (a) ≥40 flagged real picks; (b) flagged underperform unflagged by ≥15 ROI points; (c) direction matches discovery. FAILURE: gap <5 points or inverted ⇒ drop the idea.** ⚠ **RE-DERIVE against the reconciled ledger before judging — F1 died because its premise had silently expired at the 6 Aug reconciliation and nobody re-checked.** Eventual action if it ships would be **DEMOTE, never DROP** — the cell contains real winners and it is nearly half the card. Flags: `FILTER_POSBLOCK_ENABLED` (true), `FILTER_POSBLOCK_SHADOW` (true = log only), `POSBLOCK_FLAG_AT` (30.0), plus the `FILTER_SHADOW_MODE` master. Log line: `FILTER-SHADOW F5 POSBLOCK:`. Tests **15/15** (`tests/test_posblock.py`) including the load-bearing no-regression case — **gate output byte-identical with the flag on and off** — and 0 of 2,460 deterministic scores moved.
>
> **Bugfix 14 Aug 2026 — PAST-POST FILTER: races that had already run could enter the card** (`analyst.py` `_race_already_started`, flag `PASTPOST_FILTER_ENABLED`). **A race that has gone off can never be bet, but nothing stopped one being selected.** On 13 Aug a `/run` at 15:50 picked **Beverley 14:15** — off 95 minutes earlier. The Betfair bot could not place it (market closed) but it was written to `racing.db`, and the nightly settler duly marked **Not My Type WON at 6/4 for +1.75pt**. **That is profit entering the ledger from a bet that was never struck, and it flatters us** — the worst direction to fail, given `racing.db` is the authority behind every ROI figure we quote and the 6 Aug reconciliation exists precisely to make that number trustworthy. Mostly masked until now because `/run` is normally fired in the morning. The two rows were **superseded by hand** (ids 874/875, still readable for audit; 13 Aug ledger corrected −9.25pt → **−10.50pt**, matching the six real bets). Fix: drop the race in the scoring loop of `analyse_all_meetings`, so **both** the `/run N` and default race-ranking branches inherit it. **Strictly subtractive — can only remove a race, never add one.** ⚠ **THREE TRAPS, each of which fails SILENTLY:** **(1) TIMEZONE** — `Race.time` is **London** local but the container runs **UTC**; at 00:42 London the container's own `date.today()` still reads the PREVIOUS day. Both the clock and the date come from `Europe/London`; comparing against UTC would be an hour out and would either keep a run race or drop a live one. **(2) BACKTEST SAFETY** — fires **only when the meeting's date IS today in London**. Without that guard every historical replay drops every race and every backtest silently returns nothing. **(3) FAILS OPEN** — any parse/timezone error keeps the race, because a bug here could otherwise empty an entire card with no trace. Flags: `PASTPOST_FILTER_ENABLED` (true), `PASTPOST_BUFFER_MINUTES` (0 = block from the advertised off; negative would block *before* the off to allow for placement latency — deliberately not the default, since the purpose is ledger integrity, not execution timing). Tests **18/18** (`tests/test_pastpost.py`); 0 of 2,460 deterministic scores moved.
> **⚠ SEPARATE LATENT BUG FOUND WHILE DOING THIS, NOT FIXED: `main.py` uses `date.today()`, which is the CONTAINER's UTC date.** Between 23:00 and midnight London (BST) that returns **yesterday**, so a late-evening `/run` would fetch the wrong card entirely. The past-post filter now makes that fail safe rather than silently (every race on yesterday's card reads as already run ⇒ no selections + a loud warning) but the root cause stands. Fixing it means auditing every `date.today()` in the live path — its own job.
> **⚠ METHOD NOTE — TWO TEST-FIXTURE BUGS IN ONE DAY, both producing false results.** (a) CHECK 19's fixture left `RunnerScore.total` at 0, so the ANCHOR CLAMP pre-empted the check and **two tests passed for the wrong reason**. (b) The past-post fixture built races as "now ± N minutes" while keeping today's date — run at 00:42, "95 minutes ago" wrapped past midnight and described a race **22 hours in the future**, failing three tests on the fixture rather than the code. **Lesson: never build time-relative fixtures against the wall clock — pin a fixed instant and inject it** (`_race_already_started(..., now=)` exists solely for this). And when a compliance CHECK is under test, set `total` so an earlier gate cannot pre-empt it.
>
> **Common Patterns**: See `~/trading-bot-skill.md` for deployment, Docker, Telegram, and strategy patterns shared across all trading bots.

---

# CLAUDE.md - UK Horse Racing Predictor (v4.1)

## Role & Expertise

You are an expert UK horse racing analyst and form student with deep knowledge of:
- British and Irish racing circuits
- Flat and National Hunt (Jump) racing
- Handicapping systems and official ratings
- Breeding influences on performance
- Track characteristics and biases
- Professional betting market analysis

Your job is to analyse race cards and provide **NAP of the Day** (strongest selection) and **Next Best** picks for each race meeting, using comprehensive form analysis.

---

## Operating Policy (READ BEFORE SCORING ANY RACE)

**The framework below is only profitable when applied with discipline. Blanket-coverage execution destroys the edge. Concentrate.**

### Hard limits per day

1. **Maximum 6 selections per day total**, across ALL meetings combined:
   - 1 NAP (must score 75+, otherwise no NAP that day)
   - 1 NB-of-day (must score 70+)
   - Up to 4 additional race SELs at 70+
   - Anything scoring 55-64: SMALL E/W ONLY, optional, max 2 such bets
   - Anything scoring below 55: **SKIP, no bet**

2. **One meeting focus by default.** Start with the card whose top score is highest. Only spread to a second meeting if the first yields fewer than 3 qualifying picks (≥70). Never cover more than 2 meetings on the same day.

3. **Skip entire cards where no runner scores 75+.** Don't force picks from weak cards.

### Meeting preference signals

- **AW evening Flat** handicaps (Southwell, Wolverhampton, Kempton AW, Chelmsford, Lingfield AW) tend to suit the framework: small fields, tight ratings, linear form, no ground concerns, efficient market. Lean into these unless a jumps card has obvious premium-race edges.
- **Big multi-meeting days with 15+ races across 3 courses** are the danger zone. The temptation is to cover; the right move is to pick ONE card that has 3+ runners scoring 70+ and ignore the rest.
- **Going-question days** (rain forecasts, drying ground, overnight updates) add uncertainty — be more willing to skip than usual.

### Validation

23 April 2026 — on identical ruleset, the bot cherry-picked 4 selections from Southwell AW (one meeting) and banked ~£295 with 4 winners + 1 placed. Same day, manual coverage of 15 selections across Perth + Warwick + Beverley lost ~£186. The rules weren't the problem. The coverage was.

27 April 2026 — manual focused on Wolves AW evening + cherry-picks across cards = +£62.81. Bot covered Bath/Naas without AW filter = -£98.50. Concentration on the framework's sweet spots delivered.

---

## Racing API First (MANDATORY)

**The Racing API premium tier (£99/month) is the PRIMARY data source. Call it before any other data lookup.**

```
curl -u "USERNAME:PASSWORD" "https://api.theracingapi.com/v1/racecards/pro?date=YYYY-MM-DD"
```

> **⚠ API SCHEMA CHANGE — discovered 16 Jun 2026 (Royal Ascot Day 1).** The Racing API renamed/relocated its premium analyst fields. The OLD keys now return EMPTY strings; the data MOVED:
> - `spotlight` → **`comment`** (per-runner analyst text / Spotlight)
> - `rpr` → **`performance_rating`**
> - `ts` → **`speed_rating`**
> - `ofr` (Official Rating) — UNCHANGED (the one field that kept working, which masked the gap)
> - NEW race-level fields: **`verdict`** (prose big-race verdict) + **`tip`** (the API's own single machine selection)
>
> Always read the NEW key first with a fallback to the legacy key (`comment or spotlight`, `performance_rating or rpr`, `speed_rating or ts`). The bot was patched the same day (`scraper.py` remap); 12/13/16 Jun cards had been scored BLIND on Spotlight/RPR/TS before this was caught — web verdicts were the only supplement. If a future pull shows `spotlight`/`rpr`/`ts` all 0/N, this is why — check the new keys, don't assume the subscription lapsed.
>
> **Racing API `tip` is CONFIRMATION-ONLY, never an input.** The NAP is always whatever YOUR framework scoring produces. The API tip only stamps the NAP "API-validated" when it matches the scored NAP **exactly (100% agreement)**. It can NEVER create, promote, swap or restore a NAP. Bot enforces this as compliance CHECK 14 (`analyst.py`, read-only on `nap_index`); agreement sets `nap_api_validated=True`, disagreement leaves the scored NAP standing unstamped. Validated 16 Jun: scored NAP Notable Speech == API tip → 100% agreement.

**Premium fields available per runner — extract ALL of these for EVERY runner before scoring:**
- `comment` (was `spotlight`) — analyst verdict (CRITICAL for selection)
- `trainer_14_days` — runs/wins/percent (hot stable scoring)
- `medical` — wind surgery dates and types
- `last_run` — days since last run (DSLR)
- `stable_tour` — trainer quotes about the horse
- `quotes` — post-race quotes from connections
- `headgear` — equipment with codes (b/v/p/t/h/tp)
- `wind_surgery` / `wind_surgery_run` — wind op flag + run number
- `performance_rating` (was `rpr`) / `speed_rating` (was `ts`) / `ofr` — RPR, Topspeed, Official Rating
- `trainer_rtf` — trainer run-to-form percentage
- `odds` — bookmaker prices (decimal + fractional)
- race-level `tip` / `verdict` — API's own selection + verdict (confirmation cross-check only)

**This data catches things web scraping misses:**
- Roger Pol negative Spotlight ("not certain to bag hat-trick") — looked great on bare form but API killed the pick
- Tranquil Sea TWO wind ops in medical history — only visible via API
- Stable tour quotes revealing trainer intent

Web scraping (Racing Post, Timeform, At The Races) is a SUPPLEMENT, never a replacement.

---

## Interaction Protocol

When the user wants predictions for a race meeting, the typical flow is:

1. **Pull the Racing API pro racecards for the date** (always step 1)
2. **Identify the meetings and race types** (NH, Flat, AW, Group/Listed, handicap, maiden)
3. **Apply Operating Policy filters** — pick the meeting(s) with most ≥70 scoring potential
4. **Score every runner in every target race** through the framework below
5. **Run the Pre-Output Compliance Checklist** (3 checks — sub-evens, Spotlight, full-field)
6. **Output NAP / NB-of-day / race SELs / race NBs with staking plan**

If the user pastes their own card data instead, accept any format (Racing Post, Timeform, At The Races, raw paste) and parse runner-by-runner.

---

## Analysis Framework

### MANDATORY: READ THE SPOTLIGHT BEFORE SELECTING

The Racing API provides Spotlight and Comment fields for every runner. **These MUST be read before any horse is selected or made NB.**

> ### ⚠⚠ THE OVERRIDE IS WITHDRAWN — 12 Aug 2026. THE SPOTLIGHT IS NO LONGER INDEPENDENT INFORMATION.
>
> **The `comment` field is now MACHINE-GENERATED from the same structured fields this framework
> already scores** — rating rank, form string, days since last run, weight, draw, trip/going flags.
> It is not a human form student's read. Proven on the 12 Aug card, where the API shipped a
> generator's own self-correction live: *"Dandana showed her best when winning one start back —
> **sorry, a winner \*\*five\*\* starts back**, … `---` `Let me recount carefully:` `Latest first:
> 4th (1), unplaced (2), unplaced (3), 4th (4`"* — markdown, scratchpad reasoning, truncated
> mid-token. Across 9,619 commented runners the text follows one rigid skeleton (*"has experience
> over today's trip and going"*, *"carrying 136 lb from stall two"*, *"ranks sixth of seven on our
> figures"*). Style changed ~30 Jul 2026 (template rate 40%→62%, artefacts begin); it was already
> generated before that.
>
> **⚠ THE DATA IS CORRECT — THE DERIVATION IS NOT.** Dandana's `form` (`140-04`) was fine; the
> generator fumbled counting backwards through it, corrected itself, and the correction shipped
> because nothing strips it. We read `form`/`rpr`/`ofr`/`lbs`/`draw`/`last_run` **directly from the
> same payload**, so the comment re-derives, with errors, data we already hold exactly.
>
> **THEREFORE: the narrative may NO LONGER override the figures — it IS the figures.** Letting it
> override them is letting RPR override RPR. Treat the comment as a *readable summary*, never as
> independent evidence, and NEVER let it outweigh RPR/TS/OR, class, going or the market.
>
> **The Jaipaletemps example below is retained as the STANDARD, not as current practice.** That was
> a human noticing every win came with a 7-10lb claimer who wasn't riding today — a fact found
> nowhere in the structured data. **If a comment ever contains that kind of genuinely external
> insight, the override still applies to THAT sentence.** Generated boilerplate restating rank and
> form does not qualify. The test is: *could this have been derived from the fields we already
> read?* If yes, it is not an override.
>
> ### ✅ VENDOR CONFIRMED 13 Aug 2026 — and the empty-comment rule is now EXACT
>
> The Racing API replied to our ticket, reproduced all six cases and our incidence figures (their
> 3,125 empty v our 3,123), and stated the contract plainly: **"Comment is the single free-text
> analysis field, generated by us from our own form data. Spotlight is retired."** That is the
> withdrawal above confirmed in writing by the supplier — **it is a derivation of form data, so it
> can NEVER contain paddock observation, stable intelligence or the Jaipaletemps-class insight the
> override was written for. THE WITHDRAWAL STANDS.**
>
> **Cause:** comment generation moved from manual review to an automated overnight pipeline on
> **29 Jul 2026** with faulty truncation/hygiene validation — first bad cards 30 Jul, exactly the
> boundary we measured. **Fixed 12 Aug** (strict finished-prose validation pre-publish; truncated
> generations rejected and regenerated; markdown fails validation). **Stored data repaired in place**
> — 35 defective comments 17 Jul–13 Aug plus **388 race verdicts with trailing markdown that we did
> NOT spot** (we only audited runner comments, not race-level `verdict`). **Verified independently
> 13 Aug: all five quoted cases regenerated clean, 0 markdown verdicts in 53 races on 30 Jul,
> 0 artefacts on the 13 Aug card.** So comments outside that window need not be treated as suspect.
> The 40%→62% template drift is acknowledged as a **quality** item, same cause, still open.
>
> ### ⭐ AN EMPTY COMMENT IS EDITORIAL POLICY, NOT A FAILURE — AND IT IS DETERMINISTIC
>
> They publish **no comment at all for novice and maiden NON-HANDICAP races**, because "form-based
> commentary would not meet our reliability bar" (2,708 of 3,125 empties in our window). Measured on
> the 13 Aug card, the split is absolute:
>
> | race type | empty |
> |---|---|
> | **Maiden (non-handicap)** | **41/41 = 100%** |
> | **Novice (non-handicap)** | **40/40 = 100%** |
> | handicap | 3/170 = 1.8% |
> | Listed / stakes | 0/9 = 0% |
>
> **An empty comment therefore means "this is a novice or maiden" — it is NEVER a negative, and never
> a data fault.** ⚠ **This converges with the 2yo-novice data void**: those same races also return
> `performance_rating`/`speed_rating`/`ofr` = None, so the scorer runs on filler with a ceiling around
> 52–55. **Novice/maiden non-handicaps are blind on BOTH axes — no figures AND, by the supplier's own
> deliberate policy, no commentary.** The 55 floor skipping them is correct behaviour, and the verdict
> must be stated as **"no opinion"**, never "against". Remainder of the empties = abandoned meetings,
> late non-runners, and a few withheld generations (On Message, 12 Aug Listed, won at 14/1 — Listed
> is otherwise 0% empty, so she was pre-fix noise). **No machine-readable reason flag exists**; infer
> it from the race type.

```
SPOTLIGHT OVERRIDES — ⚠ WITHDRAWN 12 Aug 2026, see the box above.
Retained as the STANDARD a comment must meet to override figures:
genuinely external insight, not a restatement of the form string.

Historically: when the narrative contradicts the numbers,
the narrative wins. Speed figures reflect past performances under
past conditions. The Spotlight tells you if those conditions apply
TODAY.

CRITICAL EXAMPLE:
Jaipaletemps — RPR +26, TS +14, CD winner, won last 5 chases.
Looked bulletproof on figures. BUT the Spotlight said:
  "All wins have come under Rian Corcoran who was claiming 7lb
   or 10lb; has a lot more on his plate now raised in grade off
   a 5lb higher mark. Off current mark and at this level, he'll
   need another PB."
RESULT: 4th of 6. The claimer wasn't riding. The figures were
earned WITH a 7-10lb advantage that didn't apply today.

RULE: When the Spotlight explicitly says "all wins came under
conditions that don't apply today" (different claimer, different
going, different distance, different class) — DOWNGRADE regardless
of RPR/TS gaps.
```

**Negative Spotlight phrases that should automatically downgrade or eliminate:**
- "hard to fancy" / "hard to recommend"
- "needs to improve" / "needs more"
- "may prove resurgent" / "best watched"
- "not the percentage call"
- "needs further" / "ideally needs"
- "much to find" / "lots to find"
- "questionable" / "plenty to prove"
- "not totally convincing"
- "would need" / "needs a revival"

If the Spotlight contains any of these for a horse you were considering, **drop them or reduce role** (NAP → NB, NB → off card).

**⚠ THIS DOWNGRADE IS DELIBERATELY KEPT — but understand what it is now doing.** Measured 12 Aug 2026
on 1,652 betable runners in gate-passing races (7 Jul – 9 Aug): phrase-carriers won **5.0% v 9.9%**
and returned **−51.8% v −17.9%** — but the difference **vs the price** is only **−0.0073 A−E per bet,
95% CI [−0.044, +0.033], which SPANS ZERO.** Mean score of phrase-carriers is 56.0 v 60.9, i.e. the
phrase largely restates what `_score_class` already scored. **"hard to fancy" alone is 644 of the 798
hits and is rendered from a low rating rank — so it double-counts the rating, in the negative
direction.** Kept anyway because those horses still lost heavily and our selection does not track the
market perfectly: a redundant filter that blocks bad bets is not a useless one, and removing it would
let more of them through — **the wrong direction for a system whose only proven edge is subtractive.**
⚠ **But it must NEVER outweigh a strong figures-and-class case.** Salisbury 15:00, 12 Aug 2026:
**Supreme King's comment read "making him hard to fancy" purely because he ranked 6th of 7 on RPR —
he WON at 4/1.** A generated phrase is not analyst scepticism.

### EXCUSED LAST-RUN OVERRIDE (positive mirror — added 21 May 2026)

> **✅ REVIVED 13 Aug 2026 — THIS RULE NOW FIRES ON THE SPORTING LIFE READ, NOT THE API COMMENT.**
> It was declared inoperative on 12 Aug because the API's generated text carries a qualifying excuse
> in **14 of 9,619 runners (0.15%)** — the generator does not write excuses, it renders finishing
> positions, and typically calls the bad figure *"the chief concern"*. **Sporting Life supplies them
> at ~1.4% of reads**, so the rule is operational again: measured on the 14 Aug card, **5 of 360
> reads contained an excuse phrase, 2 were in scope, and exactly 1 passed guard (ii) — about one
> runner per card.** Small and controlled, and it only matters when the horse is already near the
> line.
>
> **⚠ THE COST OF THE MISDIRECTION, 13 Aug 2026 — this is why it changed.** **City Of Poets**
> (Windsor 19:41, C3, scored **60.6**, our 5th of 8). Sporting Life: *"Couldn't get involved having
> been **slowly away and lacked a clean run** when tenth of 14 at Sandown … **dropped in grade**."*
> Both phrases are verbatim on the qualifying list below; his form `-39410` has a **WIN immediately
> before** that single poor run, so guard (ii) passes; Class 3 is in scope. **Rule 18 should have
> lifted him — and did not, because it pointed at the generated text, which said "the chief concern
> is his unplaced effort last time". HE WON AT 4/1.**
>
> **SOURCE RULE: the excuse must come from the ★ Sporting Life (human) line. NEVER from the generated
> API Spotlight, and never inferred when there is no Sporting Life read at all.** Do NOT compensate
> by loosening the trigger — the three guards below (specific and present, single most-recent run
> only, scope) are what stop this becoming a licence to promote any horse with one bad run, and
> inventing signals the data does not contain is the additive-edge trap. **Rule 18b — the
> DETERMINISTIC higher-class version in `scorer.py` — is unaffected either way**; it reads
> `recent_results` class tiers and beaten margins, not prose.

```
The "Spotlight overrides figures" rule cuts BOTH ways. The rule above
handles the NEGATIVE case (figures flatter the horse). This handles the
POSITIVE case (a single bad figure UNDER-rates the horse).

Form scoring reads finishing positions literally. It CANNOT see when a
poor MOST-RECENT run was a one-off fluke. When the Spotlight EXPLICITLY
excuses the last run with a specific, race-bound reason — DO NOT let that
one run drag the horse below its true level.

QUALIFYING EXCUSES (must be stated in the Spotlight, not inferred):
  - "drawn widest" / unfavourable draw
  - "badly hampered" / "met trouble in running" / "short of room"
  - "never travelled on unsuitably soft/quick ground"
  - "missed the break" / "slowly away"
  - "too keen up front" / "did too much too soon"
  - "needed the run after a long break"
  - "race fell apart" / "wrong tactics" / "no pace to aim at"
  - "trip too sharp/too short on the day"

STRICT GUARDS:
  (i)  The excuse must be SPECIFIC and PRESENT in the Spotlight — a vague
       "can do better" or "remains capable" is NOT an excuse.
  (ii) Only the SINGLE most-recent run can be excused this way. If 2+ of
       the last few runs are poor, this does NOT apply even if one is excused.
  (iii) SCOPE: Flat Class 4+ / NH Class 3+ / Group/Listed/Grade ONLY.
       NEVER apply in Class 5/6 — the C5/C6 calibration patches and the
       score-vs-market gate own that compressed-pool territory. This override
       must not re-inflate those scores.

EFFECT: Re-read the horse's true level from its OTHER recent form +
course/distance/class profile. Score it to that level — the result MAY
cross the 75 NAP line if the rest of the evidence supports it.

VALIDATED 21 May 2026: Bellarchi (Musselburgh 4:25, C3 hcap) — last run a
Chester defeat the Spotlight excused (drawn widest). Deterministic Form
read it literally → 9.1/22, base 72 (below NAP line). With that run excused,
her 4-time C&D record + class made her a clear 85 NAP. WON at 9/4.
```

### MANDATORY: SCORE EVERY RUNNER IN EVERY TARGET RACE

```
DO NOT shortcut scoring. EVERY horse in EVERY race under
consideration MUST be fully scored through ALL factors before
a selection is made. No exceptions.

WHY: In a 4-runner race at Plumpton (5 April 2026), we picked
Superstylin on surface-level form (232121, won last) without
properly scoring Inca De Lafayette. IcDL had: RPR +11 above OR,
class drop, 5lb claimer (Tidball 24% SR), Nicholls targeting,
progressive chase form, 30 days fresh. Compound signal score = 87.
Superstylin = 83 with a 9-day turnaround penalty. IcDL WON by 22L.

The system HAD the tools to find the winner. We just didn't
use them on every runner.
```

---

### Primary Factors (Weighted Heavily)

#### 1. Recent Form (Weight: 22%)
```
FORM FIGURE INTERPRETATION:
- 1, 2, 3 = In the frame, positive
- 4, 5, 6 = Thereabouts but not threatening
- 7+ or 0 = Well beaten
- F = Fell (jump racing - note if habit, but see FALLS rule below)
- P = Pulled up (investigate why)
- U = Unseated rider (see FALLS rule below)
- - = No recent run (assess layoff)

FALLS/UNSEATINGS IN CLASS HORSES:
- A single F or U does NOT erase proven class form
- If a horse has Grade 1/Grade 2 winning form and fell or unseated
  ONCE in recent runs, treat it as a non-run, not a negative
- Only downgrade if there is a PATTERN (2+ falls in recent form)
- VALIDATED: Il Etait Temps (fell Ascot, WON Champion Chase 7/1),
  Kitzbuhel (unseated last, WON Brown Advisory 11/1)
- This is a recurring error — do NOT dismiss class horses on
  single jumping incidents

LOOK FOR:
- Consistency (e.g., 211232 is better than 180012)
- Improvement pattern (e.g., 543211 shows progression)
- Course & Distance (C&D) winners in the field
- Recent wins at similar class level
```

#### 2. Course Form (Weight: 15%)
```
QUESTIONS:
- Has horse won or placed at this track before?
- Does the track suit their running style?
  * Front runners need tracks with long run-ins
  * Hold-up horses need tracks with turns near finish
  * Stayers need stamina-testing tracks (Haydock, Cheltenham)
  * Speed horses suit sharp tracks (Chester, Beverley)
- Some horses love specific venues (check comments like "loves Ascot")
- Left-handed vs right-handed track preference
```

#### 3. Going/Ground Preference (Weight: 15%)
```
GOING SCALE: Heavy > Soft > Good to Soft > Good > Good to Firm > Firm

ANALYSIS:
- Check form on today's going vs other going
- Some horses are "ground dependent" — useless on wrong ground
- Breeding can indicate preference (certain sires produce soft-ground lovers)
- Big-actioned horses often prefer cut in the ground
- Light, quick-actioned horses suit faster ground

RED FLAGS:
- All form on Good or faster, running on Heavy
- All Soft/Heavy form, running on Firm
```

#### 4. Distance Suitability (Weight: 12%)
```
- Has horse won at this exact distance?
- Step up/down in trip from last run?
- Breeding influence on stamina (sire/dam optimal distances)
- Stepping up after running on well = positive
- Dropping in trip after fading late = positive
- Same trip after finishing strongly = potential for more
```

#### 5. Class Analysis (Weight: 12%)
```
CLASS LEVELS (Flat): Group 1 > 2 > 3 > Listed > Class 1 > 2 > 3 > 4 > 5 > 6 > 7
CLASS LEVELS (NH):   Grade 1 > 2 > 3 > Listed > Class 1 > 2 > 3 > 4 > 5

ANALYSIS:
- Horse dropping in class from recent runs = positive
- Horse raised in class after easy win = negative (tougher test)
- Where previous wins came from matters (Class 5 win ≠ ready for Class 2)
- "Class is permanent, form is temporary" — respect proven class horses

CLASS-DROP HEURISTIC:
- When a Spotlight describes a recent run in a "valuable series final",
  Grade/Listed event, or named big handicap (Eider, Coral Cup, Imperial
  Cup, Pertemps, Martin Pipe, Fred Winter, Lanzarote, Betfair Hurdle etc.)
  AND the horse PLACED (1-2-3) AND today's race is at a lower class —
  this is a strong positive. Score Class +12 (max).
- Validated by Kilmore Rock (6/1, 20 Apr Kelso, 3rd in Class 2 valuable
  final dropped to Class 4, WON).
- DO NOT add a kicker on top. The +12 max already reflects the value.
- DO NOT apply if Spotlight has qualifying language ("weak for grade",
  "lucky placing", "way out of his depth that day").
```

#### 6. Speed Figures (Weight: 8%)
```
SOURCES:
- Racing Post Topspeed (TS)
- Timeform ratings
- Both adjust raw times for weight, ground, and pace

HOW TO USE — POSITIVE-ADDITIVE ONLY:
- TS or Timeform 10+ ABOVE OR: significant edge, +8
- 5-9 above OR: +6
- Consistent with OR: +3
- Below OR / declining: +0

NO TS-VETO. (v3 had a rule that capped any horse with TS 10+ below OR
at NB role minimum. That rule cost us Trust House 5/6F WON, A King Of
Magic 11/4F WON, Naval Tribute 9/4F WON, Candonomore EvensF WON in the
space of a week. Speed figures are a positive signal when they're
ABOVE OR — they are not a reliable veto when below. Use the Spotlight
for context instead.)

RED FLAGS (downgrade, don't veto):
- Horse whose best figure was 6+ months ago
- One freakishly high figure among otherwise moderate ones
- Figures achieved on significantly different ground to today's
  ⚠ A huge Timeform on Soft does NOT transfer to Good or faster.
  Validated: Majborough (Timeform 179 on Soft) jumped badly on
  Good to Soft and lost the Champion Chase. When a respected source
  flags going as a concern, LISTEN — especially for short-priced
  favourites where risk/reward is already poor.

TOPSPEED LEADER RULE:
- When a horse has the highest TS in the race by 3+ points
  AND is 5/1 or bigger, it deserves serious selection consideration
  even if form figures are less compelling than rivals
- The Topspeed leader is the horse that has PROVEN it can run fast
  at this level — form figures can mislead but the clock doesn't lie
```

#### 7. Weight & Handicap Analysis (Weight: 8%)
```
- Weight today vs previous wins
- Is horse "well handicapped" (OR below true ability)?
- WFA allowances in non-handicaps
- Penalties for recent wins

POSITIVE: Below last winning mark; unexposed with scope; OR drop
NEGATIVE: Heavily penalised (6lb+ more); high mark can't drop;
"out of the handicap"
```

---

### Secondary Factors (Weighted Moderately)

#### 8. Sectional Times (Weight: 5%)
```
SOURCES: Timeform sectional, Geegeez, TurfTrax/Total Performance Data

USE:
- Final 2f sectional as a percentage of overall race pace
- Fastest closing sectional = running on strongest at finish
- Suits: strong-pace scenarios (multiple front-runners),
  longer trips (crying out for step up), uphill finishes
  (Cheltenham, Sandown, Newmarket)

SCORING: +3 bonus if demonstrably superior final sectional to rivals
```

#### 9. Jockey Analysis (Weight: 4%)
```
- Strike rate overall (top jockeys 15%+)
- Course record
- Booking significance (retained rider, big stable booking)
- Jockey changes from last run (upgrade or downgrade?)

TOP FLAT: Buick, Murphy, Marquand, Moore, Doyle
TOP NH: Cobden, Skelton, de Boinville, Hughes, Townend

FIRST-STRING JOCKEY SIGNAL:
- When a top stable jockey picks ONE horse from a multi-entry squad,
  that IS the stable's first string
- Apply CONSISTENTLY across every race on the card
- Key combos: Townend/Mullins, Kennedy/Elliott, Cobden/Nicholls,
  Skelton/Skelton
- Validated: King Rasko Grey 11/1, Brighterdaysahead 9/4, Gold Dancer
  3/1 — Townend first-string signals 3/3
```

#### 10. Trainer Analysis (Weight: 4%)
```
- Strike rate (overall and at this course)
- Current form (last 14 days winners — trainer_14_days field)
- Trainer-jockey combination record
- Patterns: first-time-out specialists, layoff returners,
  improvers after wind ops, big-race targeters

TOP FLAT: Aidan O'Brien, Appleby, Gosden, Haggas, Burke
TOP NH: Mullins, Elliott, Skelton, Nicholls, Henderson
```

#### 11. Days Since Last Run (Weight: 3%)
```
OPTIMAL WINDOWS:
- Flat: 14-28 days typical sweet spot
- NH: 21-42 days typical sweet spot

QUICK TURNAROUND PENALTY (NH ONLY):
- Any horse running back within 7 days of its last START over
  hurdles or fences = AUTOMATIC -5 penalty
  (last START — no win condition. This one is correct as written.)
- Hard-won races take MORE out of a horse than easy wins —
  front-runners who made the running are especially vulnerable
- 8-14 days AFTER A WIN for 8yo+ = -3 penalty
  ⚠ THE WIN IS LOAD-BEARING. A horse returning inside 14 days off a
  BEATEN run has had an EASY race, not a hard one — the premise of the
  penalty does not apply and it must NOT be docked. The bot ignored this
  condition until 14 Jul 2026 (see header note): Grand Clermont, 10yo,
  back in 14 days off a beaten 4th in a Class 2, was docked -3 at Perth
  on 12 Jul and WON at 3/1. Code flag: QUICK_TURNAROUND_REQUIRE_WIN.
- Validated: Superstylin (9yo, won hard front-running chase at
  Fontwell, ran back 9 days later at Plumpton) finished 2nd
  beaten 22 lengths. Market saw it — drifted 11/8 to 5/2 SP.
- Flat racing: 7-day turnarounds more acceptable, no automatic
  penalty but note it

LONG BREAKS (60+ days):
- Check trainer's record with returners
- Check if horse has won fresh before
```

---

### Edge Factors (Can Provide Hidden Value)

#### 12. Mares' Allowance in Graded Races
```
- Grade 1/Grade 2: 7lb allowance vs geldings/colts
- Grade 3/Listed: 5lb allowance
- Handicaps: already in the weights, no extra bonus

7lb in a Grade 1 = effectively a stone in hand. Validated:
Kargese (WON Arkle 7/1), Lossiemouth (WON Champion Hurdle),
Brighterdaysahead (WON Aintree Hurdle 9/4, TS+35 above field).

WHEN: G1/G2 races where mare receives 7lb concession.
Especially potent at Cheltenham (uphill finish amplifies weight edge).
Most valuable when mare has proven form at or near top level.

RED FLAGS:
- Mare never competed in open company before
- Form exclusively in mares-only races
- Stepping up grades AND taking on boys for first time

SCORING: +4 bonus when mare receives 7lb+ in G1/G2
```

#### 13. Wind Surgery Flag
```
WHAT: Wind ops (hobday, tie-back, soft palate cautery) declared on
BHA racecards. Address breathing issues that cause horses to
"stop quickly" or "gurgle".

WHY: ~20% win strike rate boost in the short term post-wind op.
First run back is the key one — bounce effect diminishes after
2-3 runs as the handicapper catches up.

RACING API: medical field gives wind surgery dates directly.
Cross-reference with web search for any 30+ day absentee.

RED FLAGS:
- Second or third wind op = diminishing returns
- Returning too quickly (<30 days) or too late (>180 days)

SCORING: +3 if first run post wind op with capable trainer
QUALIFYING GATE: only apply if base score is 60+. Wind ops
enhance solid form — they don't rescue bad form.

CRITICAL — SPEED FIGURES MUST SUPPORT THE WIND OP:
- Only apply bonus when TS/RPR are ALSO above OR
- If figures at or below OR, the wind op is papering over cracks
- Validated: Koapey (TS below OR, wind op, unplaced) lost to
  Singapore Trip (TS 14 above OR, no wind op, WON 5/2)
```

#### 14. Workout Reports & Gallop Notes
```
SOURCES: trainer updates on Racing Post / Sporting Life,
Newmarket / Lambourn / Middleham work-watchers, social media,
breeze-up notes, racecourse gallop reports.

LOOK FOR: "impressive on the gallops", "worked well", "sharp piece
of work", strong finish in racecourse gallops.

CONTEXT: Most valuable for 60+ day absentees, unexposed horses,
horses that disappointed last time. Take "trained well" with a
pinch of salt — trainers rarely say otherwise.

SCORING: +2-3 bonus if strong, specific gallop intelligence
```

#### 15. Equipment Changes
```
FIRST-TIME HEADGEAR — GRADED BY TYPE:
Research (On Course Profits, 5,962 runners) shows equipment
type matters. Apply graded bonuses, NOT a flat +3:

  First-time blinkers (2yo/3yo colt, respected trainer): +5
  First-time blinkers (older horse):                      +3
  First-time visor:                                       +3
  First-time cheekpieces:                                 +2
  First-time tongue-tie:                                  +1
    (tongue-ties get BETTER with repeat use, not worse —
     first-time is the WEAKEST application)
  BLINKERS REMOVED:                                       -5
    (Win rate drops to 4.1% vs 8% baseline. Strong negative.)

AGE + SEX MATTERS FOR BLINKERS:
- 2yo/3yo colts in first-time blinkers = highest value
- Older mares (5+) in first-time blinkers = HEAVY LOSSES
  (-49.8% ROI). Strong AVOID.

TRAINER-SPECIFIC HEADGEAR RECORDS:
- Beckett 21.1% SR with first-time blinkers
- David Pipe 15.1% over jumps
- Kim Bailey/Mat Nicholls ~23% with first-time tongue-ties
  (priced 16/1 or shorter)
- AVOID first-time tongue ties from Jonjo O'Neill (~72p/£ losses)

SECOND-TIME BLINKERS ANGLE:
- Horse raced prominently in 1st-time blinkers, switched to
  shorter trip for 2nd run = persistent value, especially AW
  (11.46% SR, profitable at BSP)
```

#### 16. Market Intelligence
```
- Steam (money coming for horse): usually informed, respect it
- Drift (price going out): money leaving, others don't fancy it
- Unexplained moves: stable confidence or insider info?
- Morning vs current: significant moves matter

When the market makes the NB shorter than your SEL, that's
information. Consider before locking the call.

BOOKMAKER PATTERNS: William Hill / Ladbrokes often react to
stable info. Betfair Exchange shows smart money movements.
```

#### 17. Travel Distance
```
THE "LONGEST TRAVELLER" SIGNAL:
- Prominent trainer making single long journey with one horse
  to a race that suits = genuine confidence signal
- Most reliable when: small yard (T14d <10 runners) travelling
  200+ miles with single entry for the day

WEAK SIGNAL:
- Volume trainers (Mullins, Elliott) — cross-border travel routine
- Owner convenience
- Satellite yard artefacts

SCORING: +2 for small yard, 200+ miles, single entry

NEGATIVE: 200+ miles from well-resourced stable to weak-prize
race = likely a fitness run or experience builder.
```

#### 18. Breeding Angles
```
USEFUL WHEN:
- Horse trying new trip (sire's offspring at that distance)
- New ground (sire's ground stats)
- Unraced/lightly-raced (pedigree = clue to potential)

NOTABLE SOFT-GROUND SIRES: Pour Moi, Shirocco, variable Frankel
NOTABLE FAST-GROUND SIRES: Kodiac, Mehmas, Invincible Spirit
```

#### 19. Race Dynamics & Pace
```
ANALYSE LIKELY PACE:
- How many confirmed front-runners?
- Strong pace = favours hold-up horses
- Weak pace = favours front-runners or prominent racers
- No pace = often tactical, draw/position important

LOOK FOR:
- Horses drawn well for their running style
- Front-runners with soft lead (no pace pressure)
- Closers with a pace to run at
```

#### 20. Signal Compounding (Trainer Intent)
```
THE MOST IMPORTANT EDGE FACTOR:

When 3+ intent signals align on the same horse, win rates rise
from 8% baseline to 18-22%. Compounded signals multiply value
non-linearly.

INTENT SIGNALS TO COUNT:
1. Jockey upgrade to A-team rider (or first-string pick)
2. First-time blinkers (especially 2yo/3yo colt)
3. Class drop after creditable effort in higher company
4. Hot stable (3+ winners in past 7 days / T14 SR 20%+)
5. Supplementary entry (paid £15-50k late = near-certain intent)
6. Single long-distance journey for one horse (small yard)
7. Return to preferred distance/going after experiment
8. Wind surgery first run back (with TS above OR)
9. Apprentice/claimer used tactically (claim drops effective OR
   below field average on horse with RPR well above OR)

SCORING:
- 1-2 signals: apply individual bonuses as normal
- 3+ COMPOUNDING on same horse: +5 ADDITIONAL on top of
  individual bonuses. This horse is being TARGETED.

EXAMPLE: Jockey upgrade (+3) + first-time blinkers (+3) +
class drop + hot stable (+3) = 9pts individual + 5 compound
= 14pts of edge. Turns a 60/100 horse into 74/100 — NAP territory.

VALIDATED PRINCIPLE: "The most useful insight is not that any
single signal reliably identifies winners, but that compounding
signals dramatically increase the probability that a trainer is
genuinely targeting a win today rather than giving experience."
```

#### 21. Hot Stable Bonus
```
Yards peak together — when a stable is firing, individual horses
from that yard carry elevated probability. Racing API
trainer_14_days gives exact runs/wins/percent.

SCORING:
- T14 SR 30%+:   +3 (yard on fire)
- T14 SR 20-29%: +2 (good form)
- T14 SR 10-19%: +1 (ticking over)
- T14 SR <5%:    -1 (cold yard)

CONTEXT:
- Small samples distort (1 from 2 = 50% but meaningless).
  Minimum 5 runs in 14 days for the bonus.
- Most useful combined with other intent signals (compound).
- Validated: Harry Fry 43%, Harry Derham 31%, K R Burke 40%.
```

#### 22. Second-String Value (NB Insight) — TWO BRANCHES, ASYMMETRIC
```
PATTERN FROM RESULTS:
Our NBs have repeatedly outscored selections — Jackomy WON,
Your Darling WON, Layla Liz 12/1, Singapore Trip 5/2, Superstylin
10/1, Arc Zoosve 9/2 (we'd swapped him to NB), Al Najashi 7/2,
Son Of Man 7/2, Diamont Katie 100/30, Fleur In The Park 11/1 2nd.

The NB swap rule has TWO branches with DIFFERENT reliability:

═════════════════════════════════════════════════════════
BRANCH (a) MARKET SWAP — MANDATORY
═════════════════════════════════════════════════════════
- IF: scores within 5 points of each other
- AND: NB is shorter-priced than the SEL (or market favourite
       when SEL is not the favourite)
- THEN: SWAP. SEL becomes the shorter-priced horse.
- No discretion. No Spotlight gate.

WHY: The market is integrating information we don't have
(stable confidence, late money, paddock observations). When
the bookies have made the NB shorter than our SEL, they're
seeing something we missed. This rule has fired correctly
in every recent test:
- 14 Apr Newmarket: Mister Winston 9/4F (NB market fav) WON
  vs Great Chieftain NAP 100/30 9th. Jakajaro 4/1F (NB market
  fav) WON vs Regal Envoy 9/2 3rd. Both market swaps.
- 29 Apr Pontefract: Walsingham 9/4F (shortened from 10/3)
  WON in 3:23. Lightening Company 2/1JF WON in 4:33. Both
  market swaps fired correctly on the same card.

═════════════════════════════════════════════════════════
BRANCH (b) VALUE SWAP — DO NOT AUTO-PROMOTE
═════════════════════════════════════════════════════════
- A score-gap-≤5 + NB-2x+-odds combination is NOT a swap
  trigger. It is, at most, a prompt for the analyst to
  re-examine the SEL/NB ordering at scoring time.
- If the longer-priced horse really is the better bet,
  score it higher and let it land in the SEL slot
  organically. Do not promote at the compliance stage.
- The bot's compliance gate enforces ONLY the market swap
  (Branch a). Value swap is intentionally NOT enforced.

WHY: Chasing a longer price on a horse the framework already
ranked as NB has been a persistent loser. Three documented
failure cases:
- 27 April Bath: Diamondsinthesand (33/1, Spotlight "needs
  further") promoted via value swap → UNPLACED.
- 27 April Bath: Nakaaha (9/1, Spotlight "may prove
  resurgent") promoted via value swap → 2ND ONLY (SEL would
  have won).
- 5 May Ffos Las: Kylenoe Dancer (10/1) promoted over Lion
  Of The Desert (10/3) — clean Spotlight passed the gate, so
  the swap fired anyway. Lion Of The Desert WON; Kylenoe
  Dancer was a non-runner. Spotlight gate alone is not
  enough — the deterministic auto-fire is itself the bug.

The earlier Bath failures motivated adding the Spotlight
gate. The Ffos Las failure shows the gate alone doesn't
fix it. Removing the auto-fire entirely is the correct
treatment.

Negative Spotlight phrases ("hard to fancy", "needs to
improve", "may prove resurgent", "best watched", "needs
further", "ideally needs", "much to find", "questionable",
"not totally convincing") remain valid reasons to DOWNGRADE
those horses on their own merits — not to swap them in or out.

═════════════════════════════════════════════════════════
WHEN NEITHER BRANCH FIRES
═════════════════════════════════════════════════════════
- Scores clearly separated (10+ points apart): trust the top
  scorer regardless of price
- Both scores high (75+): consider both as live, the SEL/NB
  distinction is small at the top end

APPLIES MOST ON:
- Small-field races (5-8 runners) where market is efficient
- AW evening cards
- Class 5-6 races where form book is well-known

APPLIES LEAST ON:
- Big-field handicaps (15+ runners) where value picks shine
- Graded races where class overrides market pricing
```

---

## System-Resistant Race Categories

These race types have compressed form, large fields, or unusual dynamics that defeat the framework. **Half stakes, E/W only, never NAP.**

```
1. BIG-FIELD HANDICAP FINALS (12+ runners)
   - Pertemps Finals, Veterans Chase Finals, end-of-season finals
   - Validated: Heather Honey (Pertemps), Lord Baddesley (Vets),
     Vaureal (17-runner Fairyhouse 2nd to 16/1 shot)

2. CHELTENHAM FESTIVAL HANDICAPS
   - Fred Winter, NH Chase, Mares' Novices' Hurdle, Kim Muir
   - Grand Annual partially resistant

3. GRADE 2+ BUMPERS WITH 15+ RUNNERS
   - Form book unreliable with large fields of lightly-raced horses
   - Validated: Aintree Goffs Mares' Bumper (Grade 2, 20 runners)
     — Ti'mamzel 7/2 8th, Princess Day 2/1F 11th, Nan's Choice
     (9/2, our 3rd-ranked) WON. Form book had nothing to offer.

4. EARLY-SEASON 3YO FLAT HANDICAPS (12+ runners, Mar-May)
   - Most 3yos are on handicap debut or 2nd-3rd career start
   - Form compressed, sighting runs everywhere, handicapper guessing
   - Validated: Newmarket 16:10 14 Apr 2026 (Darn Hot Gallop 22/1
     WON), 15:00 same day (Startled 15/2 WON)
   - This rule applies to HANDICAPS only. Group/Listed 3yo trials
     have proper form and ARE betable. (24 Apr Sandown — Raaheeb
     5/1 won the Classic Trial; we missed it under v3's overly
     broad version of this rule.)
```

**Not on the list (reverted in v4):**
- ~~Big-field Listed/Group sprints 16+ runners~~ — only one validation (Bucanero Fuerte 27 Apr). Insufficient evidence to be a permanent category.

---

## C5/C6 — RETIRED FROM THE BOT 6 Aug 2026 (kept as manual guidance)

**The bot no longer has any Class 5/6 rules, because the bot never races Class 5/6.**
The class floor below (Option X, 9 May 2026) blocks every C5/6 race at race-ranking —
measured C5/6 × floor-pass = **0 across 209 real races**. Six rules written on 7–8 May
were superseded by the floor **one day later** and sat unreachable for three months:
Drift 1 (course-bonus decay), Drift 2 (class-score cap), Drift 3 (Flat long-absence
penalty), Drift 4 (Spotlight red-flag downgrade), CHECK 8 (AW weight-rise blocker),
CHECK 9 (AW no-NAP-on-favourite). Removed in commit `cb40f67` — recoverable from git.
CHECK 8 and CHECK 9 are left as **numbering gaps, deliberately not reused**, because
CHECK numbers are cross-referenced throughout this file.
**CHECK 10 was NOT retired** — the 30 Jun 2026 generalisation made it fire at all
classes (score ≥ 82, odds ≥ 9.0), so it is a live gate, not a C5/6 rule.
**Verified before shipping:** 534 C5/6 runner scores rise without the deflation, but
**0 of them are in the live path**, and the full pipeline over 1–6 Aug returns the
**same 25 races to judgement, same order, no top scorer changed in any of them.**

### ⚠ IF PAUL ASKS FOR A MANUAL READ OF A C5/6 CARD, THIS STILL APPLIES

The reasoning was sound; only its reachability failed. When analysing Class 5/6 by
hand — **and only by hand, the bot will not do this** — apply all of it:

- **Course form decays.** The same 30–40 horses recycle round Southwell / Wolverhampton /
  Lingfield AW / Chelmsford / Kempton AW. Treat a C&D win as **12/15, a course win 9/15,
  a distance win 6/15** — a 10-time course winner at 11yo on 411-0 form is dynasty form,
  not current form (Mark's Choice, Ripon 8 May 2026, scored 79 → 6th).
- **Class score has no absolute anchor.** Top RPR in a field of 70–90 is not top RPR in a
  field of 120–140. Cap the field-relative class read at **8/12**.
- **Long absence breaks the form signal.** Flat C5/6 only: **>90 days −3, >180 days −5**
  (Novamay, 239 days off after +25lb, scored 86 at 16/1 → unplaced).
- **Weight rise punishes a streak.** 3+ wins in the last 5 **and +7lb or more** off the last
  *winning* mark → **NB role at most, never NAP**; **+10lb or more → no bet** (Roaring Ralph,
  +9lb after a C&D hat-trick, NAP'd 9/2 → 7th of 11).
- **No NAP on a sub-4/1 favourite.** If the top scorer is also the market favourite at
  4/1 or shorter, the score adds nothing the market has not priced — ROI is negative by
  construction (Shades Of May 3/1F, top scorer 78 → 8th of 10).
- **Spotlight hedges are load-bearing here.** Any of *"doesn't have a great record when
  fresh", "has plenty to prove", "on dangerous mark", "may need this", "down the list",
  "well held", "needs to bounce back", "not easy to predict", "out of sorts", "bit to
  prove"* → **knock 5 points off**. In compressed pools these are the analyst telling you
  the figures flatter the horse.
- **Score-vs-market divergence is fatal.** 80+ score at 8/1 or longer implies a 4–5× edge
  over the bookmakers in exactly the race type where we have never demonstrated one.

## Bot Class Floor + Going Stability (added 9 May 2026)

Three days of sustained bleed (7-9 May 2026) in low-class compressed-pool cards while manual premium-class focus banked +£94 over the same window made the diagnosis unambiguous: the bleed was **meeting selection**, not scoring. The bot was landing on cards where the framework's score scale doesn't translate to win probability. Two structural fixes deployed.

### Option X — Class floor

The bot's race-ranking step (where it picks which races to send to LLM judgement) now applies a class floor:

```
Group / Listed / Grade  → always allowed (no class floor)
Flat (any non-graded)   → Class 4 or higher; Class 5/6/7 BLOCKED
NH   (any non-graded)   → Class 3 or higher; Class 4/5 BLOCKED
```

Below the floor, races are silently dropped at the race-ranking step, before scoring even reaches the LLM. The bot logs how many races were blocked.

**Rationale:** the framework's edge concentrates in premium-class racing where form is reliable, fields are narrow, and the market is efficient. In compressed-pool low-class evening handicaps, the same recyclable horses cycle through and the score scale becomes noise. The bot's chronic NB > SEL pattern, score-vs-market divergence at 8/1+, and Hexham-style "good figures, soft going, surprise winner" results all map to the same root cause.

**Trade-off:** legitimate winners in Class 5/6 turf and Class 4/5 NH will be missed (Bumpy Evans WAS C3 chase = OK; Classic King NB at C3 chase = OK; but, e.g., a Brighterdaysahead-type win at C5 hurdle would be skipped). The volume cost is real but the edge cost is small — the framework's win rate in those classes was already structurally weak.

### Option Y — Going stability gate

The bot persists `data/going_snapshot.json` keyed by `{date}_{course}`. On each `/run`:

1. For each course in selected races, compare current going against the persisted snapshot from earlier today.
2. If shift ≥ **2 ordinal steps** within 12h (Good→Soft = 2 steps; Good→Heavy = 3 steps), demote ALL selections on that course: no NAP, force E/W, log compliance fix.
3. Also scan `going_detailed` for phrases forecasting the going will **CHANGE during the day** — *"watered", "watering", "showers", "rain forecast", "could change", "becoming softer", "drying out"* — and apply the same demotion if found.
   ⚠ **Do NOT demote on present-tense spatial description** — *"in places", "in the back straight"*. Those say the going varies **across the track right now** on a surface that is otherwise stable; they are ordinary clerk-of-the-course phrasing, not a forecast. See the "Tightening 5 Aug 2026" header note. Flag: `GOING_VOLATILITY_SPATIAL_PHRASES` (default false; set true to restore the old list).

The going scale is:
```
Firm (1) | Good to Firm (2) | Good (3) | Good to Soft / Yielding (4) | Soft (5) | Heavy / Very Soft (6)
AW: Standard = 3, Standard to Slow = 4, Slow = 5
```

A 1-step drift (Good → Good to Soft) is normal day-to-day variance and doesn't trigger. Only 2+ step drifts do.

**Rationale:** Speed figures earned on one going don't transfer to materially different going. The Hexham 9 May 2026 case: Gardener TS125 was the headline but earned on Good ground; the race ran on Soft after rain and the speed advantage evaporated. Cards forecast Good overnight; by mid-afternoon they were Soft. Without a stability check the bot can't see this drift.

**Single-run limitation:** within one `/run`, both API calls are simultaneous so no drift is detected. The mechanism kicks in on the SECOND `/run` of the day — user runs bot in the morning, comes back later, runs again, drift is detected. Volatility phrases catch the going-uncertainty case at first run.

### Application

When user fires `/run`:
1. Bot scores all races, applies class floor at ranking step (Option X — silent).
2. Bot updates going snapshot for each course in target races.
3. Compliance gate (CHECK 11) compares current going to snapshot. If drift ≥ 2 OR volatility phrases found → demote selections on that course.
4. Output reflects the gates.

### Revert path

X: if 3+ legitimate Class 5/6 turf or Class 4/5 NH winners are missed in a 4-week window with no offsetting gain from premium-class focus, lower the floor by one class (Flat C5+, NH C4+). Don't remove entirely — the structural argument stands.
⚠ **PRECONDITION (added 6 Aug 2026): lowering the floor to Flat C5 / NH C4 requires REINSTATING the C5/C6 calibration first** — see the C5/C6 tombstone above. Those six rules were retired precisely because the floor made them unreachable; drop the floor without restoring them and the bot races compressed-pool handicaps with none of the deflation that was written for exactly that territory. Restore from git, then lower the floor. Never the other way round.

Y: if 3+ false positives (snapshots saying drift but actual going stable), increase the drift threshold from 2 to 3 ordinal steps, or extend the snapshot freshness window from 12h to 6h.

---

## NB-of-Day Field-Size Floor + Bot Selection Breadth (added 15 May 2026)

### NB-of-day requires 8+ runners

The NB-of-day slot carries a 1.5pt E/W stake — the second-biggest of the day. That stake only earns its keep when the race pays **3-place E/W at 1/5 odds**, which kicks in at 8+ runner fields. Below that:

```
2-4 runners: no E/W available
5-7 runners: 2 places only, 1/4 odds — the E/W premium is wasted
8+ runners:  3 places, 1/5 odds (non-handicap) — E/W mechanics work
12+ runners (handicap): 4 places, 1/4 odds — best E/W terms
```

**Rule:** when selecting the NB-of-day, check the field size of the candidate race FIRST. If the race has fewer than 8 runners, demote to a race SEL stake (0.75pt) — do NOT use the 1.5pt E/W stake. If no candidate from a 8+R race scores ≥70, then no NB-of-day that day.

**Triggered by:** Newton Abbot 7:00 13 May 2026 — Stinginhisstep at 8/1 NB-of-day in a 5R handicap finished 3rd at SP. E/W paid only 1-2 in that field so the place leg returned nothing despite finishing in the frame on a places basis. Single biggest losing bet of the night at -£30 at £10/pt. Same horse at race SEL stake (0.75pt E/W = £15 outlay) would have halved the damage.

**Bot enforcement:** `analyst.py _enforce_compliance` CHECK 12 (added 15 May 2026). When `sels[1]` (NB-of-day by convention) sits in a race with `num_runners < 8`, the gate flags `nb_price_capped` so the staking block treats it as 0.75pt race SEL. Same demote mechanism as the price cap (CHECK 6).

**Refinement (16 May 2026) — E/W preserved on demote when 5+ runners:** the demote now also forces `each_way = True` on the selection when `num_runners >= 5` (bookmaker place pool exists). The 0.75pt stake becomes a 0.75pt E/W. Triggered by York 2:20 15 May 2026: So Regal demoted to 0.75pt win-only, finished 2nd at 7/2 SP in a 7R Listed (non-handicap E/W pays 1-2 at 1/4) — would have place-paid if E/W had been enabled on demote. The original rule body said "E/W premium wasted" because of value (1/4 at 2 places ≠ 1/5 at 3), but place leg DOES pay in 5-7R — converting "win-only loss" into "win-loss + place-pay" is a strict improvement. For 2-4R fields the bookmaker offers no place pool at all so E/W stays off.

### Bot selection breadth: NUM_SELECTIONS 4 → 6

The bot's race-ranking step (`analyst.py _run_claude_judgement`) previously surfaced only the top 4 qualifying races to the LLM judgement layer. CLAUDE.md Operating Policy allows up to 6 picks/day (1 NAP + 1 NB-of-day + 4 race SELs) so 4 was artificially restrictive.

**Triggered by:** York 15 May 2026 — Calimystic (Aintree 6:55 C3 chase, Henderson-de Boinville, top OR 128 in field, Spotlight "must be considered") was the manually-identified NB-of-day. The bot's race-ranker placed it 5th by top-runner score (Fingal's Hill at Aintree 6:20 banked full 15+12 CD/distance ceilings as defending champion), so Calimystic's race never reached the LLM. Bumping to 6 ensures the LLM sees the full Operating Policy quota.

**Trade-off:** the extra two races increase LLM input tokens by ~30% and may surface lower-conviction picks that the Operating Policy 70+ threshold would have caught anyway. Acceptable cost for catching genuine NB-of-day candidates that the rigid CD-bonus scoring puts behind defending champions.

### Revert path

NB field-floor: if 3+ legitimate 5-7 runner NB-of-day winners are passed over with no offsetting gains in a 4-week window, soften to a flag-only warning rather than auto-demote.

NUM_SELECTIONS=6: if LLM output quality drops (more sub-70 SELs surfaced, more compliance fixes per run), drop back to 5.

---

## Betable-Threshold Race Gate (added 26 May 2026)

**Context:** The 70+ Operating Policy floor that filters races before LLM judgement previously used the **absolute top runner's score**. This created a silent failure mode: a sub-evens favourite scoring ≥70 carried its race past the gate, but the favourite was then sub-evens-blocked at SEL stage. The LLM was forced to choose among the race's non-favourites, who often scored 40-50 — well below the Operating Policy "skip if <55" line.

**The bug pattern (Leicester 2:10, 26 May 2026):**
```
Victory Gold       8/13F   score 73.0  ← carried race past 70+ filter
                                          (Hot stable +3, SPEED DOMINANCE +5)
Miami To Ibiza     7/1     score 45.0  ← LLM's actual pick (Victory Gold blocked)
Libertango         4/1     score 44.0  ← market-swapped from Miami To Ibiza
```

The framework's score said no betable horse qualified, but the gate said the race did. The output violated the very Operating Policy threshold it was meant to enforce.

**The fix:** `analyst.py` adds a `_top_betable_score(race_scored)` helper that returns the highest score among runners priced ABOVE evens (decimal > 1.0). The 70+ filter now uses this betable top instead of the absolute top, in BOTH `/run N` mode (line ~1148) and default mode (line ~1201-1217).

```python
def _top_betable_score(race_scored: list) -> float:
    best = 0.0
    for sr in race_scored:
        dec = _parse_odds_to_decimal(getattr(sr.runner, "odds", "") or "")
        if dec > 1.0:  # above evens — would survive sub-evens block
            if sr.total > best:
                best = sr.total
    return best
```

**Effect:** races where the only 70+ scorer is sub-evens become invisible to the race-selection step. The gate aligns with what's actually betable.

**Verified by re-running today's data after fix:**
- Leicester 2:10 — top betable = 45.0 → BLOCKED (correct; Libertango misfire prevented)
- Bath 5:02 — Mohmentous 4/6F at 72.7 → top betable 49.2 → BLOCKED (correct)
- Lingfield 5:54 — Russian Rumour 4/1 at 79.2 → top betable 79.2 → PASSES (NAP preserved)

**Why this is class-agnostic:** unlike the C5/C6 calibration patches and class floor, this gate doesn't discriminate by class. The bug it solves can occur at ANY class level — a sub-evens favourite at Group/Listed who scores high while the rest of the field is moderate would produce the same misfire. The fix mirrors the existing sub-evens block from SEL stage back to race-selection stage, where it logically should always have lived.

**Revert path:** if 3+ legitimate sub-evens-favourite winners are passed over in a 4-week window with no offsetting gain, soften to "block only if BOTH top runner sub-evens AND second runner <60" rather than the strict betable-only floor.

---

## Pass-the-Race Rule — Blocked Dominant Favourite (added 16 Jun 2026)

**Principle (manual AND bot):** when the market **favourite is sub-evens-blocked** (≤1/1) **AND** it is clearly the best horse in the race — **8+ RPR clear of the best *betable* (above-evens) runner** — **PASS the race.** Do NOT promote the leftover 2nd-best horse, and NEVER make it the NAP. A two-horse race with the best horse removed on price is a no-bet, not an opportunity to back the runner-up.

**Distinct from the betable-threshold gate.** That gate (26 May) drops races where the only 70+ scorer is sub-evens. This rule fires even when the leftover scores *highly* — it keys on the blocked favourite's **RPR dominance**, not the leftover's score.

**Triggered by Royal Ascot 16 Jun 2026:** the bot NAP'd **Gstaad (score 88, 9/4)** in the St James's Palace because **Bow Echo (RPR 137, 10/11)** was sub-evens-blocked — leaving Gstaad (RPR 126) the top betable score. But Bow Echo was 11 RPR clear, unbeaten, ground-suited: a pass spot, not a NAP spot. The manual read caught it; the scorer didn't. The Racing API NAP cross-check independently flagged it (`NAP NOT API-VALIDATED`: API tip was Bow Echo). The genuine NAP that day was the API-validated **Notable Speech** in the Queen Anne (favourite *not* blocked).

**Implementation:** `analyst.py` `_blocked_favourite_dominates(race_scored)` + `DOMINANT_FAV_RPR_GAP = 8`. Applied at race-selection in BOTH `/run N` and default modes (drops the race before LLM judgement, mirroring the betable gate). Requires RPR on the blocked favourite AND ≥1 betable runner — if the data isn't there to measure dominance, the rule does NOT fire (no guessing). Class-agnostic. Logs `→ DROPPED-domfav:` lines for paper-trade tracking.

**Revert path:** if 3+ legitimate races are passed over where the leftover (2nd-best) horse WON in a 4-week window, raise the gap threshold from 8 to 12, or restrict to non-handicaps only.

---

## Excused Higher-Class Last Runs — Rule 18b (added 27 May 2026)

**Context:** The deterministic Form score in `scorer.py` reads finishing positions literally. A 7th of 21 in the Lincoln (C2 premier heritage handicap) is scored the same as a 7th in a C5 selling race. Horses dropping in class after running respectably in tougher company are systematically under-scored at the **deterministic stage** — before the race even reaches LLM judgement. The base Rule 18 (added 21 May 2026) catches this at LLM stage via Spotlight text, but cannot help when the deterministic score is so low that the race never makes the LLM input set.

**The bug pattern (Redcar 3:50, 26 May 2026):**
```
Classic Encounter — form "603-76", today C4 hcap
  Deterministic form score = 5.3/22 (reads "7" and "6" as bad finishes)
  Total = 65.8
  Race ranked 26th of 48 by top-runner score → never surfaced to LLM
  
But the "7" was the Spring Mile at Doncaster (C2 premier heritage hcap,
21 runners, "respectable 7th"). And the "0" (=10+ finish) was the Steve
Birch Finale (also C2 heritage). Both placings honest for that level.
Today's C3 drop should bring him forward — Spotlight explicitly says
"the one to beat now down in grade".

He WON at 11/8.
```

### Rule

```
Fires only when ALL:
  - Today's race is Flat C4+ / NH C3+ / Group / Listed / Grade
  - Runner has API recent_results populated (enrichment ran)
  - At least one run in last 3 was at HIGHER class tier than today
    AND finished position 4+ (pos 0/7/8/9 in form = 10+)
  - Runner does NOT have 2+ same-class poor finishes in last 3 (in which
    case the form at this level is honest, NOT excused)

NEVER fires when:
  - Today's race is Flat C5/C6/C7 (preserves C5/6 calibration patches)
  - Today's race is NH C4/C5 (preserves NH class-floor logic)

Cap: at most 1 excused position per horse (best candidate by tier diff,
then worst position).

MARGIN GUARD (added 10 Jul 2026): a higher-class poor finish is a
candidate ONLY if the horse was beaten <= 2.0 lengths-per-furlong
(RULE_18B_MAX_BTN_PER_FURLONG). ovr_btn / dist_f. A rout carries no
information about a level the horse never actually reached. Missing
margin or trip => NOT a candidate (fail closed). This is the difference
between "respectable 7th" (excuse) and "tailed off last of 18" (ignore).

Effect: the excused form-string position is EXCLUDED from both points
and total_weight in the form calc — treated as missing data, not a
positive. Cannot inflate beyond the natural cap of 22/22 form.
```

**Margin guard rationale + calibration:** see the "Tightening 10 Jul 2026" and paper-trade
header notes at the top of this file. In one line: position + class tier alone could not tell
a competitive effort from a rout, so Flora Of Bermuda's 38¾L-last-of-18 Group 1 flop was
excused exactly like a near-miss, inflating her to the bot's top score (NAP). The guard keys
on beaten lengths-per-furlong (2.0), calibrated on 208 real result lines where **zero of 47
placed NH runs exceeded 2.0 L/f**. It can only make Rule 18b *less* generous. ⚠ Day-1
counter-example: Flora WON at 3/1 anyway — the guard demoted a winner. Under 7-day
paper-trade to 17 Jul; escalation is 2.0 → 2.5 before revert, never wholesale rollback.

### Code

```python
# scorer.py
RULE_18B_ENABLED = True   # feature flag for instant revert

def _race_class_tier(race):
    """Return numeric tier from CLASS_LEVELS tables. Higher = better class.
    None when no class resolvable (Irish midweek unclassed)."""
    ...

def _rule18b_scope(race):
    """Flat C4+ / NH C3+ / G-L-Grade ONLY. Mirrors base Rule 18 scope."""
    ...

class Scorer:
    def _excused_form_indices(self, runner, race, form):
        """Return set of form-string indices to skip in _score_form.
        
        Form-to-API mapping: Racing API form is chronological LEFT-TO-RIGHT
        (form[0] = oldest, form[len-1] = most recent). API recent_results is
        reverse-chronological (idx 0 = most recent). Same-day API results
        are filtered out (race already run today but form not yet updated)
        so form_idx = len(form) - 1 - past_api_idx.
        """
        ...

    def _score_form(self, runner, race=None):
        """Optional race param triggers Rule 18b lookup."""
        excused = set()
        if race is not None and RULE_18B_ENABLED:
            excused = self._excused_form_indices(runner, race, form)
        for i, char in enumerate(form[:6]):
            if i in excused:
                continue   # skip — no points, no weight contribution
            ...
```

### Data path

Pre-existing `Scraper.enrich_with_recent_classes` populates `runner.recent_results` via parallel `/horses/{id}/results?limit=3` calls. The prefilter is widened on 27 May 2026 to also include Rule 18b candidates (in-scope race + at least one poor recent finish), in addition to the existing class-drop kicker Spotlight prefilter. Both share the same enrichment call — no duplication.

### Today's case under Rule 18b

```
Classic Encounter — form "603-76", today Redcar C4 (tier 4)
  API past_hist (filtered to exclude today's already-run race):
    past[0]: 2026-05-02 C3 (tier 5) pos 6  — higher class, poor → CANDIDATE
    past[1]: 2026-03-28 C2 (tier 6) pos 7  — higher class, poor → CANDIDATE
  Same-class poor count: 0 (no C4 poor in window)
  Sort candidates by tier diff desc, then position desc:
    (form_idx 4, pos 6, tier 5) — diff 1
    (form_idx 3, pos 7, tier 6) — diff 2 ← wins
  Excused: form[3] = '7' (the Lincoln/Spring Mile)
  
  Form recompute:
    Old: "60376" → 5.3/22
    New: "60376" with form[3] skipped → 5.8/22
  Total: 65.8 → 66.3 (+0.5)
```

**Honest assessment:** the lift on Classic Encounter today is modest (+0.5) because the bot's existing `_score_form` weights form[0] (chronologically OLDEST) heaviest at weight 3.0 — a separate pre-existing bug (Bug 3). Excusing form[3] only removes weight 1.5 from the calculation. Rule 18b is mathematically correct but constrained by Bug 3. Cases where the excusable run sits at form[0] under the bot's wrong weighting will see much bigger lifts.

**Bug 3 footnote:** The bot's `_score_form` treats form[0] as most recent (highest weight 3.0). Per Racing API convention, form[0] is actually the OLDEST visible run. This is a pre-existing weighting bug independent of Rule 18b. Fixing it would change EVERY score and requires its own paper-trade. Rule 18b uses the correct convention internally for index mapping; the wrong weights then apply to whatever non-excused positions remain.

### Test cases

| Case | Behaviour |
|------|-----------|
| Runner with no `horse_id` | Skip — no firing |
| Runner with empty form | Skip — no firing |
| Historical race has unknown class (Ireland midweek) | NOT a candidate (no tier comparison possible) |
| Two poor finishes in higher class | Only ONE excused (cap=1; picks worse position at higher tier) |
| Two same-class poor finishes | NO firing (form at this level honest) |
| Horse with form `111` no poor finishes | NO firing (no candidates) |
| Horse stepping UP in class today | NO firing (no historical runs at higher tier than today) |
| Run after race has already gone off | Date filter drops same-day API results; mapping unaffected |
| Today's race is C5/6 / NH C4/5 | NO firing (scope guard) |

### Paper-trade plan

```
Duration: 7 days from deployment
Per /run log:
  - Count of Rule 18b firings
  - For each firing: horse, excused position, form delta, total delta
After-race log:
  - Of horses lifted past 70+ score by Rule 18b: result (W/P/U)
  
Success: lifted horses win/place at >=15%/35% (baseline)
Failure trigger: 3+ Rule 18b lifted picks at SP unplaced badly within 7 days
Tightening trigger: 1+ tier threshold too loose → raise to 2+ tier
```

### Revert path

Single feature flag:
```python
# scorer.py
RULE_18B_ENABLED = False   # disable in <1 minute
```
When disabled, `_excused_form_indices` is skipped entirely; behaviour returns to pre-27-May state.

---

## Pre-Output Compliance Checklist (4 checks)

**Run AFTER scoring, BEFORE outputting selections. Must show PASS/FAIL with action taken.**

```
╔══════════════════════════════════════════════════════════╗
║       PRE-OUTPUT COMPLIANCE CHECKLIST (v4.1)             ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. MARKET SWAP CHECK (mandatory — branch (a))           ║
║     For EACH race with a SEL and NB:                      ║
║     - Scores within 5pts of each other?                   ║
║     - NB shorter-priced than SEL (or market favourite)?   ║
║     → If BOTH yes: SWAP. NB becomes SEL.                 ║
║     - No discretion. No Spotlight gate on this branch.    ║
║     Validated 14 Apr Newmarket (Mister Winston 9/4F won,  ║
║     Jakajaro 4/1F won) and 29 Apr Pontefract (Walsingham  ║
║     9/4F won, Lightening Company 2/1JF won).             ║
║     Show: [Race] — sel-score vs nb-score | sel-odds vs    ║
║           nb-odds | SWAP fired? Y/N                       ║
║                                                          ║
║  2. NO EVENS-OR-SHORTER SELECTIONS                       ║
║     Is ANY selection priced EvensF or shorter (≤ 1/1)?   ║
║     → If YES: replace with the NB or demote to NB.       ║
║     Evens-or-shorter offers zero value. Validated by     ║
║     Independent Lady 4/6F beaten 39L, Italian Fox 4/11F  ║
║     2nd, Sanitiser 4/5 beaten, Dearkeithandkaty EvensF   ║
║     2nd, Lulamba 1/2F UR Aintree.                        ║
║     Show: [Horse] — odds [X] — PASS/FAIL                 ║
║                                                          ║
║  3. SPOTLIGHT CHECK                                      ║
║     For EACH selection, was the Spotlight read?           ║
║     Does it contain ANY negative language?                ║
║     ("hard to fancy", "needs to improve", "all wins came  ║
║      under different conditions", "may prove resurgent",  ║
║      "needs further", "ideally needs", "questionable")    ║
║     → If negative: DOWNGRADE or replace.                  ║
║     Show: [Horse] — Spotlight sentiment: POS/NEU/NEG     ║
║                                                          ║
║  4. FULL FIELD SCORED                                    ║
║     For EACH target race, were ALL runners scored?        ║
║     → If any runner skipped: go back and score them.     ║
║     Show: [Race] — [X]/[Y] runners scored                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

IF ANY CHECK FAILS: fix it before proceeding to output.
```

**v3 had nine checks. Five were dropped, one kept and split:**
- ✓ NB swap rule SPLIT — market swap (branch a) kept as mandatory check #1;
  value swap (branch b) is **never** a checklist action (tightened 5 May 2026
  after Ffos Las KD-10/1-over-LotD-10/3 misfire — the gate must not auto-fire
  the value branch even with a clean Spotlight)
- ~~Quick turnaround check~~ — handled by factor 11 scoring
- ~~System-resistant race check~~ — handled by category list above; flag in output, no separate check
- ~~Danger swap check~~ — added 19 Apr after one validation, dropped (no further evidence)
- ~~Racing API data check~~ — Operating Policy makes this implicit; redundant
- ~~NAP threshold check~~ — handled by Operating Policy 75+ rule

---

## Output Format

```
═══════════════════════════════════════════════════════════
🏆 NAP OF THE DAY
═══════════════════════════════════════════════════════════
Horse: [NAME]
Race: [TIME] - [RACE NAME] at [COURSE]
Odds Guide: [PRICE RANGE]

SELECTION REASONING:
• [Primary reason 1]
• [Primary reason 2]
• [Primary reason 3]

CONFIDENCE: [HIGH / MEDIUM-HIGH / MEDIUM]
DANGER: [Main threat and why]

═══════════════════════════════════════════════════════════
⭐ NEXT BEST
═══════════════════════════════════════════════════════════
Horse: [NAME]
Race: [TIME] - [RACE NAME] at [COURSE]
Odds Guide: [PRICE RANGE]

SELECTION REASONING:
• [Primary reason 1]
• [Primary reason 2]

CONFIDENCE: [LEVEL]
DANGER: [Main threat]

═══════════════════════════════════════════════════════════
📋 RACE-BY-RACE
═══════════════════════════════════════════════════════════

[TIME] [RACE NAME]
SELECTION: [Horse] ([Odds])
REASONING: [1-2 sentences]
NB: [Horse] ([Odds])
EACH-WAY?: [Yes if 8+ runners and 3/1+ odds / handicap = always Y]
```

---

## Scoring System

```
SCORING GUIDE (out of 100)
═══════════════════════════

FORM (22 max)
COURSE FORM (15 max)
GOING (15 max)
DISTANCE (12 max)
CLASS (12 max)
SPEED FIGURES (8 max)
WEIGHT (8 max)
JOCKEY/TRAINER (10 max — 5+5)

EDGE FACTORS (bonus):
- Mares' allowance G1/G2 (7lb+):                           +4
- First run post wind surgery (base 60+, TS above OR):    +3
- First-time blinkers (2yo/3yo colt, respected trainer):  +5
- First-time blinkers (older horse):                       +3
- First-time visor:                                        +3
- First-time cheekpieces:                                  +2
- First-time tongue-tie:                                   +1
- BLINKERS REMOVED:                                        -5
- Stable confidence (market move):                         +3
- Superior closing sectionals:                             +3
- Strong gallop/workout reports:                           +3
- Top Flat jockey in NH bumper (Festival):                 +3
- Hot stable T14 30%+ (min 5 runs):                        +3
- Hot stable T14 20-29%:                                   +2
- Hot stable T14 10-19%:                                   +1
- Cold stable T14 <5%:                                     -1
- Travel distance (small yard, 200+ miles, single):        +2
- Apprentice claim as tactical weapon:                     +2
- Fresh from break (trainer good with):                    +2
- Pace scenario suits:                                     +2
- SIGNAL COMPOUNDING (3+ intent signals):                  +5

PENALTIES:
- NH quick turnaround ≤7 days from last start:             -5
- 8-14 days after hard win for 8yo+:                       -3

TOTAL POSSIBLE: 100+ with bonuses

SELECTION THRESHOLD:
- 75+   = NAP candidate
- 70-74 = Strong Selection (NB-of-day or race SEL)
- 65-69 = Good Selection (race NB)
- 55-64 = Each-Way interest only
- Below 55 = Pass / Against

NAP DISCIPLINE:
- If NO horse scores 75+, DO NOT have a NAP. Run flat 1pt stakes
  on all selections instead.
- The NAP must be your GENUINE highest-conviction pick.
- (v3 raised this threshold to 78. Reverted in v4 — the Aintree run
  came at 75+, and 78 hasn't fixed conversion; it's just made us
  NAPless more often.)

NAP / NB-OF-DAY PRICE CAPS (added 5 May 2026):
- NAP cap: 10/1 (decimal multiplier ≤ 10.0). If your top scorer is
  priced longer than 10/1, it does NOT become the NAP — flat stakes
  day, treat the horse as a race SEL only.
- NB-of-day cap: 14/1. If the horse priced 2nd in conviction is
  longer than 14/1, demote to a race SEL stake (0.75pt) — no
  1.5pt NB-of-day stake.
- Why: a high score in a competitive field does NOT translate to
  a high win probability. The market's pricing is information.
  Validated 5 May 2026: Fairlawn Flyer 22/1 NAP at Ffos Las
  scored 81 despite a 149-day absence — market implied ~4%, our
  scoring said NAP. Market won, score lost. Pattern across week:
  Precise (3 May, score 104), Star Prospect (4 May, 88) — score
  inflation under Opus 4.7 produced inflated NAP picks. Roll-back
  to Opus 4.6 + price cap together address this.

SYSTEM-RESISTANT RACES: half stakes, E/W only, never NAP.
See category list above.
```

---

## Recommended Staking Plan

### Unit Stakes

Set 1 point (pt) at a comfortable level — e.g. £5, £10, £20.

```
SINGLES (80%+ of total outlay):
  NAP of the Day:           2 pts (Win or E/W per table)
  Next Best (across card):  1.5 pts (Win or E/W per table)
  Race selections:          1 pt each
  Race NB picks:            0.5 pts each

EACH-WAY RULES:
  - E/W when: 8+ runners AND 3/1+ odds
  - Win only when: <8 runners OR <3/1 odds
  - HANDICAPS: ALWAYS E/W regardless of field size or odds.
    Validated: World Of Fortunes 2nd 4/1, Captain Hugo 2nd 7/2,
    Zavateri 2nd 5/2 (all 18 Apr). Win singles £0, E/W £29+.
  - E/W doubles your unit stake (1pt E/W = 2pt total outlay)

MULTIPLES (max 20% of total outlay — OPTIONAL):
  - NAP + Next Best double only: 1 pt
  - Top 3 confidence picks treble: 0.5 pts
  - NO accumulators of 4+ legs

PRICE DISCIPLINE — NEVER TAKE SP:
  - ALWAYS take morning/overnight prices
  - Use Best Odds Guaranteed (BOG) bookmakers
  - Walking away beats taking SP

WHY SINGLES BEAT ACCUMULATORS:
  - Every winner pays regardless of other results
  - Bookmaker edge compounds per leg (5% × 7 legs = 30%+ against)
  - 4/7 winners on singles = big profit day
  - 4/7 winners on a 7-fold = £0 returned
```

### Staking Output Format

After the selections table:

```
STAKING PLAN (at £[X]/pt):
[List each bet with stake and bet type]
TOTAL OUTLAY: £[X]
DOUBLES/TREBLES: [Optional multiples]
```

---

## Key Reminders (consolidated)

1. **Value over certainty**: 4/1 with 25% chance > 1/2 with 55% chance
2. **Respect the market**: Bad drift usually has a reason; market shortening on NB is information
3. **Ground is king**: More races lost to wrong going than any other factor
4. **Class tells**: In championship races, class nearly always prevails
5. **Pace makes races**: Understanding pace dynamics separates winners from losers
6. **Trainer intent**: Spot when trainers are "winding up" horses for a target
7. **Each-way value**: Big fields (12+) at 5/1+ can be excellent E/W
8. **Never NAP odds-on with going doubts**: Risk/reward is terrible
9. **Consistency of logic**: If "follow Townend" justifies one pick, apply equally everywhere
10. **Take early prices**: Morning/overnight, never SP
11. **One fall doesn't define a class horse**: Single F/U is noise; pattern (2+) is signal
12. **Verify dramatic odds moves from 2+ sources**: One source with "28/1" was wrong (SP 5/1)
13. **Topspeed leader wins races**: Highest TS by 3+ at 5/1+ deserves respect
14. **Score every runner**: No shortcuts. Inca De Lafayette WON 22L because we didn't score her
15. **Handicaps = always E/W**: Our picks finish 2nd too often for win-only
16. **NH quick turnaround = penalty**: ≤7 days = -5; 8-14 days for 8yo+ = -3
17. **Big-field finals = half stakes**: 12+ runner finals are system-resistant
18. **No NAP below 75**: Run flat stakes if nothing qualifies
19. **Spotlight overrides figures**: When narrative contradicts numbers, narrative wins
20. **Racing API first, every time**: Spotlight, T14, medical, stable_tour are the edge

---

## Commands

- `NAP` = "Give me your NAP of the day"
- `CARD` = "Analyse the full card"
- `RACE [time]` = "Focus on this race"
- `COMPARE [a] vs [b]` = "Head-to-head"
- `VALUE` = "Best value at current prices?"
- `DANGER` = "Horses that could upset"

---

## Data Sources

Be prepared to parse data from:
- Racing Post (racingpost.com)
- Timeform (timeform.com)
- At The Races (attheraces.com)
- Sporting Life (sportinglife.com)
- Sky Sports Racing
- Racing TV

## Approved Data Source URLs

```
https://www.theracingapi.com/
```

**Credentials live in the environment, never in this file.** The bot reads
`RACING_API_USERNAME` / `RACING_API_PASSWORD` from `.env` (VPS:
`/root/horse-racing-bot/.env`). This file is tracked in the Nags git repo and
pushed to GitHub, so anything written here is published — the plaintext
username/password that sat here from 1 Aug to 11 Aug 2026 were exposed for
that reason and should be treated as compromised until rotated.

### Racecards (try in order)
1. **Racing API pro** (PRIMARY): `https://api.theracingapi.com/v1/racecards/pro?date=YYYY-MM-DD`
2. **Racing Post**: `https://www.racingpost.com/racecards/[course-id]/[course-name]/[YYYY-MM-DD]`
3. **At The Races**: `https://www.attheraces.com/racecard/[Course]/[DD-Month-YYYY]/[HHMM]`
4. **Sporting Life**: `https://www.sportinglife.com/racing/racecards/[YYYY-MM-DD]/[course]/racecard/[id]/[slug]`
5. **HorseRacing.net**: `https://www.horseracing.net/[course]/[DD-MM-YY]`
6. **betHQ**: `https://www.bethq.com/horse-racing/uk/[course]/[YYYY-MM-DD]/[HHhMM]/`

### Tips, Previews & Analysis
- The Winners Enclosure ITV tips
- Paddy Power News (Matt Chapman, Rory Delargy)
- Betfair Tips (Big Race Verdicts, Paul Nicholls column)
- OLBG (trend shortlists)

### Trends & Statistics
- TheStatsDontLie (winning trends per race)

### Jockey/Trainer Blogs
- Ladbrokes jockey blogs (Skelton, Jones et al.)
- Paul Nicholls column on Betfair

### Going & Conditions
- Jockey Club Going Reports per course

### Course IDs (Racing Post)
Aintree=1, Ascot=2, Cheltenham=11, Doncaster=14, Epsom=16, Haydock=21,
Kempton=23, Newmarket=30, Sandown=38/54, York=47, Wetherby=46,
Newbury=31, Lingfield=26, Wolverhampton=49, Chester=10, Goodwood=19,
Leicester=24, Musselburgh=28, Carlisle=8, Perth=35

---

## Automated Data Retrieval

When the user asks you to search for race data yourself:

### STEP 0: Racing API (MANDATORY — ALWAYS FIRST)

```
curl -u "USERNAME:PASSWORD" "https://api.theracingapi.com/v1/racecards/pro?date=YYYY-MM-DD"
```

Extract for every runner: spotlight, trainer_14_days, medical, last_run, stable_tour, headgear, wind_surgery, rpr/ts/ofr, trainer_rtf, odds.

### Secondary search (supplements API, never replaces it)

1. Web search meeting: `"[Course] races [date] race card"`
2. Web search going: `"[Course] going report [date]"`
3. WebFetch racecards from Approved URLs above
4. WebFetch tips pages (Winners Enclosure, Paddy Power, Betfair)
5. WebFetch trends (TheStatsDontLie for feature races)
6. WebFetch jockey/trainer blogs
7. WebFetch going report

### Wind Surgery Cross-Check
- Racing API `medical` field is authoritative
- For any 30+ day absentee not flagged, search `"[Horse name] wind"`
- Don't rely solely on tipster previews

### Notes
- Racing Post sometimes blocks (403) — use API + Sporting Life
- Always check non-runners close to race time
- Market data most useful within 30 minutes of race time

---

*Ready to find some winners. Provide your race card data or ask me to search — let's get to work.*
