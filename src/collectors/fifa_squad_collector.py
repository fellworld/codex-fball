"""Parse FIFA World Cup 2026 squad PDF into CSV tables.

The official PDF is the source of truth for squad members, clubs, and head
coaches. Parsing PDF tables is imperfect, so this collector preserves a
`player_name_raw` field for review instead of pretending every name column is
cleanly recoverable from text extraction.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path
from typing import Iterable

import pdfplumber
import requests


DEFAULT_PDF_URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
TEAM_RE = re.compile(r"(?:SQUAD LIST)?\s*(.+?)\s*\(([A-Z]{3})\)")
PLAYER_RE = re.compile(
    r"^\d+\s+(GK|DF|MF|FW)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{3})$"
)
COACH_RE = re.compile(r"^Head coach\s+(.+?)\s+([A-Z][A-Za-zÀ-ÿ' -]+)$")
COACH_OVERRIDES = {
    "Head coach PETKOVIC Vladimir Vladimir PETKOVIĆ Switzerland": ("Vladimir PETKOVIC", "Switzerland"),
    "Head coach SCALONI Lionel Lionel Sebastián SCALONI Argentina": ("Lionel SCALONI", "Argentina"),
    "Head coach POPOVIC Tony Tony POPOVIC Australia": ("Tony POPOVIC", "Australia"),
    "Head coach RANGNICK Ralf Ralf Dietrich RANGNICK Germany": ("Ralf RANGNICK", "Germany"),
    "Head coach GARCIA Rudi Rudi José GARCIA France": ("Rudi GARCIA", "France"),
    "Head coach BARBAREZ Sergej Sergej BARBAREZ Bosnia And Herzegovina": ("Sergej BARBAREZ", "Bosnia And Herzegovina"),
    "Head coach ANCELOTTI Carlo Carlo ANCELOTTI Italy": ("Carlo ANCELOTTI", "Italy"),
    "Head coach BUBISTA Pedro LEITÃO BRITO Cabo Verde": ("Pedro BUBISTA", "Cabo Verde"),
    "Head coach MARSCH Jesse Jesse Alan MARSCH USA": ("Jesse MARSCH", "USA"),
    "Head coach LORENZO Nestor Nestor Gabriel LORENZO Argentina": ("Nestor LORENZO", "Argentina"),
    "Head coach DESABRE Sebastien Sebastien Serge Louis DESABRE France": ("Sebastien DESABRE", "France"),
    "Head coach FAE Emerse Emerse FAE Côte D'Ivoire": ("Emerse FAE", "Côte D'Ivoire"),
    "Head coach DALIC Zlatko Zlatko DALIĆ Croatia": ("Zlatko DALIC", "Croatia"),
    "Head coach ADVOCAAT Dick Dirk Nicolaas ADVOCAAT Netherlands": ("Dick ADVOCAAT", "Netherlands"),
    "Head coach KOUBEK Miroslav Miroslav KOUBEK Czech Republic": ("Miroslav KOUBEK", "Czech Republic"),
    "Head coach BECCACECE Sebastian Sebastián Andrés BECCACECE Argentina": ("Sebastian BECCACECE", "Argentina"),
    "Head coach HOSSAM HASSAN Hossam Hassan Hassanein HASSAN Egypt": ("Hossam HASSAN", "Egypt"),
    "Head coach TUCHEL Thomas Thomas TUCHEL Germany": ("Thomas TUCHEL", "Germany"),
    "Head coach DESCHAMPS Didier Didier Claude DESCHAMPS France": ("Didier DESCHAMPS", "France"),
    "Head coach NAGELSMANN Julian Julian NAGELSMANN Germany": ("Julian NAGELSMANN", "Germany"),
    "Head coach CARLOS QUEIROZ Carlos Manuel BRITO LEAL DE QUEIROZ Portugal": ("Carlos QUEIROZ", "Portugal"),
    "Head coach MIGNE Sebastien Sébastien Bernard Henri C MIGNÉ France": ("Sebastien MIGNE", "France"),
    "Head coach GHALEHNOY Amir Ardeshir GHALEHNOY IR Iran": ("Amir GHALEHNOY", "IR Iran"),
    "Head coach ARNOLD Graham Graham James ARNOLD Australia": ("Graham ARNOLD", "Australia"),
    "Head coach MORIYASU Hajime Hajime MORIYASU Japan": ("Hajime MORIYASU", "Japan"),
    "Head coach SELLAMI Jamal Jamal SELLAMI Morocco": ("Jamal SELLAMI", "Morocco"),
    "Head coach HONG Myungbo Myung Bo HONG Korea Republic": ("Myungbo HONG", "Korea Republic"),
    "Head coach AGUIRRE Javier Javier AGUIRRE ONAINDIA Mexico": ("Javier AGUIRRE", "Mexico"),
    "Head coach OUAHBI Mohamed Mohamed OUAHBI Morocco": ("Mohamed OUAHBI", "Morocco"),
    "Head coach KOEMAN Ronald Ronald KOEMAN Netherlands": ("Ronald KOEMAN", "Netherlands"),
    "Head coach BAZELEY Darren Darren Shaun BAZELEY New Zealand": ("Darren BAZELEY", "New Zealand"),
    "Head coach SOLBAKKEN Stale Ståle SOLBAKKEN Norway": ("Stale SOLBAKKEN", "Norway"),
    "Head coach CHRISTIANSEN Thomas Thomas CHRISTIANSEN TARIN Spain": ("Thomas CHRISTIANSEN", "Spain"),
    "Head coach ALFARO Gustavo Gustavo Julio ALFARO Argentina": ("Gustavo ALFARO", "Argentina"),
    "Head coach MARTINEZ Roberto Roberto MARTÍNEZ MONTOLIU Spain": ("Roberto MARTINEZ", "Spain"),
    "Head coach LOPETEGUI Julen Julian LOPETEGUI ARGOTE Spain": ("Julen LOPETEGUI", "Spain"),
    "Head coach DONIS Georgios Georgios DONIS Greece": ("Georgios DONIS", "Greece"),
    "Head coach CLARKE Steve Stephen CLARKE Scotland": ("Steve CLARKE", "Scotland"),
    "Head coach THIAW Pape Pape Bouna THIAW Senegal": ("Pape THIAW", "Senegal"),
    "Head coach BROOS Hugo Hugo Henri BROOS Belgium": ("Hugo BROOS", "Belgium"),
    "Head coach DE LA FUENTE Luis Luis DE LA FUENTE CASTILLO Spain": ("Luis DE LA FUENTE", "Spain"),
    "Head coach POTTER Graham Graham Stephen POTTER England": ("Graham POTTER", "England"),
    "Head coach YAKIN Murat Murat YAKIN Switzerland": ("Murat YAKIN", "Switzerland"),
    "Head coach LAMOUCHI Sabri Sabri LAMOUCHI France": ("Sabri LAMOUCHI", "France"),
    "Head coach MONTELLA Vincenzo Vincenzo MONTELLA Italy": ("Vincenzo MONTELLA", "Italy"),
    "Head coach BIELSA Marcelo Marcelo Alberto BIELSA Argentina": ("Marcelo BIELSA", "Argentina"),
    "Head coach POCHETTINO Mauricio Mauricio Roberto POCHETTINO TROSSERO Argentina": ("Mauricio POCHETTINO", "Argentina"),
    "Head coach CANNAVARO Fabio Fabio CANNAVARO Italy": ("Fabio CANNAVARO", "Italy"),
}


def checked_at() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def download_pdf(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)


def parse_team_header(lines: list[str]) -> tuple[str, str]:
    for line in lines[:8]:
        match = TEAM_RE.search(line)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return "", ""


def parse_player_line(line: str) -> dict[str, str] | None:
    match = PLAYER_RE.match(line.strip())
    if not match:
        return None

    pos, raw_name_block, dob, club, height_cm = match.groups()
    club_country = ""
    country_match = re.search(r"\(([A-Z]{3})\)\s*$", club)
    if country_match:
        club_country = country_match.group(1)

    return {
        "position": pos,
        "player_name_raw": raw_name_block.strip(),
        "dob": dob,
        "club": club.strip(),
        "club_country_code": club_country,
        "height_cm": height_cm,
    }


def parse_coach_line(line: str) -> tuple[str, str] | None:
    if not line.startswith("Head coach"):
        return None
    if line in COACH_OVERRIDES:
        return COACH_OVERRIDES[line]
    parts = line.split()
    if len(parts) < 5:
        return None

    nationality = parts[-1]
    name_tokens = parts[2:-1]
    if len(name_tokens) >= 2:
        display_name = f"{name_tokens[1]} {name_tokens[0]}"
    else:
        display_name = " ".join(name_tokens)
    return display_name.strip(), nationality.strip()


def iter_pdf_rows(pdf_path: Path, source_url: str, source_checked_at: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    players: list[dict[str, str]] = []
    coaches: list[dict[str, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            team, team_code = parse_team_header(lines)

            for line in lines:
                player = parse_player_line(line)
                if player and team:
                    player.update(
                        {
                            "team": team,
                            "team_code": team_code,
                            "is_likely_starter": "",
                            "starter_confidence": "",
                            "role_notes": "",
                            "source": source_url,
                            "source_checked_at": source_checked_at,
                        }
                    )
                    players.append(player)

                coach = parse_coach_line(line)
                if coach and team:
                    head_coach, nationality = coach
                    coaches.append(
                        {
                            "team": team,
                            "team_code": team_code,
                            "head_coach": head_coach,
                            "head_coach_raw": line,
                            "coach_nationality": nationality,
                            "source": source_url,
                            "source_checked_at": source_checked_at,
                        }
                    )

    return players, coaches


def write_csv(path: Path, rows: Iterable[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect FIFA World Cup squad data.")
    parser.add_argument("--pdf-url", default=DEFAULT_PDF_URL)
    parser.add_argument("--pdf-path", default="data/raw/fifa/SquadLists-English.pdf")
    parser.add_argument("--players-output", default="data/processed/squad_players.csv")
    parser.add_argument("--coaches-output", default="data/processed/team_coaches.csv")
    parser.add_argument("--skip-download", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf_path)
    if not args.skip_download:
        download_pdf(args.pdf_url, pdf_path)

    source_checked_at = checked_at()
    players, coaches = iter_pdf_rows(pdf_path, args.pdf_url, source_checked_at)

    write_csv(
        Path(args.players_output),
        players,
        [
            "team",
            "team_code",
            "position",
            "player_name_raw",
            "dob",
            "club",
            "club_country_code",
            "height_cm",
            "is_likely_starter",
            "starter_confidence",
            "role_notes",
            "source",
            "source_checked_at",
        ],
    )
    write_csv(
        Path(args.coaches_output),
        coaches,
        [
            "team",
            "team_code",
            "head_coach",
            "head_coach_raw",
            "coach_nationality",
            "source",
            "source_checked_at",
        ],
    )
    print(f"Parsed {len(players)} players and {len(coaches)} coaches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
