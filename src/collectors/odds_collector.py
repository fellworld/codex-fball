"""Collect bookmaker odds snapshots into SQLite.

This collector is designed for licensed odds APIs. By default it targets
The Odds API v4 because its market names map cleanly to this project:
`h2h`, `totals`, and `spreads`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "https://api.the-odds-api.com/v4"
DEFAULT_MARKETS = "h2h,totals,spreads"
DEFAULT_REGIONS = "us,uk,eu,au"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def fetch_odds(
    api_key: str,
    sport_key: str,
    markets: str,
    regions: str,
    odds_format: str,
    api_base: str,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": "iso",
        }
    )
    url = f"{api_base}/sports/{urllib.parse.quote(sport_key)}/odds?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "codex-fball/0.1"})

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at_utc TEXT NOT NULL,
                provider TEXT NOT NULL,
                sport_key TEXT NOT NULL,
                event_id TEXT NOT NULL,
                commence_time_utc TEXT,
                home_team TEXT,
                away_team TEXT,
                bookmaker_key TEXT NOT NULL,
                bookmaker_title TEXT,
                market_key TEXT NOT NULL,
                outcome_name TEXT NOT NULL,
                price_decimal REAL,
                point REAL,
                source_last_update TEXT,
                raw_event_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_odds_snapshots_event_time
            ON odds_snapshots (event_id, captured_at_utc)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_odds_snapshots_bookmaker_market
            ON odds_snapshots (bookmaker_key, market_key)
            """
        )


def iter_rows(
    events: list[dict[str, Any]],
    captured_at_utc: str,
    provider: str,
    sport_key: str,
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for event in events:
        raw_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append(
                        (
                            captured_at_utc,
                            provider,
                            sport_key,
                            event.get("id"),
                            event.get("commence_time"),
                            event.get("home_team"),
                            event.get("away_team"),
                            bookmaker.get("key"),
                            bookmaker.get("title"),
                            market.get("key"),
                            outcome.get("name"),
                            outcome.get("price"),
                            outcome.get("point"),
                            market.get("last_update") or bookmaker.get("last_update"),
                            raw_event_json,
                        )
                    )
    return rows


def save_snapshot(
    db_path: Path,
    rows: list[tuple[Any, ...]],
) -> None:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO odds_snapshots (
                captured_at_utc,
                provider,
                sport_key,
                event_id,
                commence_time_utc,
                home_team,
                away_team,
                bookmaker_key,
                bookmaker_title,
                market_key,
                outcome_name,
                price_decimal,
                point,
                source_last_update,
                raw_event_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect World Cup odds snapshots.")
    parser.add_argument("--sport-key", default="soccer_fifa_world_cup")
    parser.add_argument("--markets", default=DEFAULT_MARKETS)
    parser.add_argument("--regions", default=DEFAULT_REGIONS)
    parser.add_argument("--odds-format", default="decimal", choices=["decimal", "american"])
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--provider", default="the-odds-api")
    parser.add_argument(
        "--db-path",
        default="data/raw/odds_snapshots/worldcup_2026_odds.sqlite",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.getenv("THE_ODDS_API_KEY")
    if not api_key:
        print("Missing THE_ODDS_API_KEY environment variable.", file=sys.stderr)
        return 2

    captured_at_utc = utc_now_iso()
    events = fetch_odds(
        api_key=api_key,
        sport_key=args.sport_key,
        markets=args.markets,
        regions=args.regions,
        odds_format=args.odds_format,
        api_base=args.api_base,
    )
    rows = iter_rows(
        events=events,
        captured_at_utc=captured_at_utc,
        provider=args.provider,
        sport_key=args.sport_key,
    )
    save_snapshot(Path(args.db_path), rows)
    print(f"Saved {len(rows)} odds rows from {len(events)} events at {captured_at_utc}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
