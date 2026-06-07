"""Collect public football data used by the model.

The script writes raw source snapshots under data/raw/public and produces
normalized inputs for form, Elo, and FIFA-rank metadata. FIFA ranking is
treated carefully: if the current FIFA page does not expose the full ranking
table, the model may use an Elo-rank proxy downstream with an explicit note.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from typing import Any


RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ELO_URL = "https://www.eloratings.net/World.tsv"
FIFA_RANKING_PAGE = "https://inside.fifa.com/en/fifa-world-ranking/men?dateId=FRS_Male_Football_20260119"

ELO_CODE_TO_TEAM = {
    "DZ": "Algeria",
    "AR": "Argentina",
    "AU": "Australia",
    "AT": "Austria",
    "BE": "Belgium",
    "BA": "Bosnia And Herzegovina",
    "BR": "Brazil",
    "CA": "Canada",
    "CV": "Cabo Verde",
    "CO": "Colombia",
    "CD": "Congo DR",
    "HR": "Croatia",
    "CW": "Curaçao",
    "CZ": "Czechia",
    "CI": "Côte D'Ivoire",
    "EC": "Ecuador",
    "EG": "Egypt",
    "EN": "England",
    "FR": "France",
    "DE": "Germany",
    "GH": "Ghana",
    "HT": "Haiti",
    "IR": "IR Iran",
    "IQ": "Iraq",
    "JP": "Japan",
    "JO": "Jordan",
    "KR": "Korea Republic",
    "MX": "Mexico",
    "MA": "Morocco",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "NO": "Norway",
    "PA": "Panama",
    "PY": "Paraguay",
    "PT": "Portugal",
    "QA": "Qatar",
    "SA": "Saudi Arabia",
    "SC": "Scotland",
    "SN": "Senegal",
    "ZA": "South Africa",
    "ES": "Spain",
    "SE": "Sweden",
    "CH": "Switzerland",
    "TN": "Tunisia",
    "TR": "Türkiye",
    "US": "USA",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
}


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-fball/0.1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def write_raw(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def read_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["display_name"]: row["canonical_name"]
            for row in csv.DictReader(handle)
            if row.get("display_name") and row.get("canonical_name")
        }


def canonical(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def collect_results(output_dir: Path) -> Path:
    payload = fetch_bytes(RESULTS_URL)
    path = output_dir / "international_results.csv"
    write_raw(path, payload)
    return path


def collect_elo(output_dir: Path, processed_dir: Path, teams: list[dict[str, str]], aliases: dict[str, str]) -> Path:
    payload = fetch_bytes(ELO_URL)
    raw_path = output_dir / "world_elo.tsv"
    write_raw(raw_path, payload)

    canonical_to_fifa_code = {row["team"]: row["team_code"] for row in teams}
    rows: list[dict[str, str]] = []
    for line in payload.decode("utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        rank, _, code, rating = parts[:4]
        team = ELO_CODE_TO_TEAM.get(code)
        if team in canonical_to_fifa_code:
            rows.append(
                {
                    "team": team,
                    "team_code": canonical_to_fifa_code[team],
                    "elo_rank": rank,
                    "elo_rating": rating,
                    "source": ELO_URL,
                    "source_checked_at": utc_now(),
                }
            )

    output_path = processed_dir / "public_elo_ratings.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["team", "team_code", "elo_rank", "elo_rating", "source", "source_checked_at"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def collect_fifa_metadata(output_dir: Path, processed_dir: Path) -> Path:
    payload = fetch_bytes(FIFA_RANKING_PAGE)
    raw_path = output_dir / "fifa_ranking_page.html"
    write_raw(raw_path, payload)

    source_checked_at = utc_now()
    metadata: dict[str, Any] = {
        "source": FIFA_RANKING_PAGE,
        "source_checked_at": source_checked_at,
        "last_update_date": "",
        "next_update_date": "",
        "available_dates": [],
        "full_ranking_available": False,
        "notes": "FIFA page metadata collected. Full ranking table was not exposed in static page JSON.",
    }

    text = payload.decode("utf-8", errors="ignore")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text)
    if match:
        data = json.loads(match.group(1))
        ranking = data["props"]["pageProps"]["pageData"]["ranking"]
        metadata["last_update_date"] = ranking.get("lastUpdateDate", "")
        metadata["next_update_date"] = ranking.get("nextUpdateDate", "")
        metadata["available_dates"] = ranking.get("allAvailableDates", [])[:10]

    output_path = processed_dir / "fifa_ranking_metadata.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect public football data.")
    parser.add_argument("--raw-dir", default="data/raw/public")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--groups", default="data/processed/groups.csv")
    parser.add_argument("--squad-players", default="data/processed/squad_players.csv")
    parser.add_argument("--aliases", default="config/team_aliases.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    aliases = read_aliases(Path(args.aliases))
    with Path(args.squad_players).open(newline="", encoding="utf-8") as handle:
        squad_rows = list(csv.DictReader(handle))
    seen: set[tuple[str, str]] = set()
    teams = []
    for row in squad_rows:
        key = (row["team"], row["team_code"])
        if key in seen:
            continue
        seen.add(key)
        teams.append({"team": row["team"], "team_code": row["team_code"]})

    results_path = collect_results(raw_dir)
    elo_path = collect_elo(raw_dir, processed_dir, teams, aliases)
    fifa_path = collect_fifa_metadata(raw_dir, processed_dir)
    print(f"Collected results: {results_path}")
    print(f"Collected Elo ratings: {elo_path}")
    print(f"Collected FIFA metadata: {fifa_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
