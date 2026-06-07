# 2026 World Cup odds collection plan

Last checked: 2026-06-06

## Objective

Record odds snapshots for every 2026 World Cup fixture from at least five major betting brands.

Required markets:

- Match winner / moneyline: bookmaker market key usually `h2h`.
- European odds / 1X2: home win, draw, away win; often also represented by `h2h` for soccer.
- Over/under: bookmaker market key usually `totals`.
- Asian handicap / Asian line: bookmaker market key may be `spreads`, `asian_handicap`, or provider-specific handicap markets.

## Primary bookmaker shortlist

Use at least five of these brands whenever available:

- Pinnacle
- Bet365
- Betfair Exchange
- William Hill
- Unibet
- BetMGM
- DraftKings
- FanDuel
- Caesars
- Ladbrokes

The configuration file is `config/odds_bookmakers.csv`.

## Preferred data access

Use licensed odds APIs or official bookmaker/exchange APIs. Avoid scraping public bookmaker pages unless the site terms explicitly allow it.

Candidate APIs:

- The Odds API: supports bookmaker odds, regions, and market keys such as `h2h`, `spreads`, and `totals`.
- OddsJam API: commercial odds feed with broad bookmaker coverage.
- Pinnacle API: direct source for Pinnacle odds.
- Betfair Exchange API: direct source for exchange prices.

## Snapshot schedule

Baseline:

- Record once per day for all available World Cup fixtures.

Match day:

- For fixtures played on the current China date, record every 2 hours until kickoff.
- Keep recording attempts even if a bookmaker temporarily has no odds, and store the missing coverage in run logs.

Suggested run windows:

- Daily full snapshot: 12:00 Asia/Shanghai.
- Match-day snapshots: every 2 hours from 00:00 Asia/Shanghai through kickoff.

## Storage design

Store one row per bookmaker, event, market, and outcome at each captured time.

Recommended fields:

- `captured_at_utc`
- `provider`
- `sport_key`
- `event_id`
- `commence_time_utc`
- `home_team`
- `away_team`
- `bookmaker_key`
- `bookmaker_title`
- `market_key`
- `outcome_name`
- `price_decimal`
- `point`
- `source_last_update`

For match odds, do not collapse rows into a single wide table too early. Long-format rows preserve multiple lines, alternate totals, and changing market coverage.

## Data quality checks

- At least 5 configured brands present per major fixture when markets are open.
- `h2h`/1X2 should include both teams and, for soccer, draw.
- `totals` should include over and under with the same point.
- Asian handicap/spread rows should include a `point`.
- Every run should store `captured_at_utc`, even if no odds are returned.

## Legal and compliance notes

Odds data is commercial and may be restricted by data-provider terms, jurisdiction, or licensing. This project should use an API key and provider plan that explicitly permits storage and analysis.

