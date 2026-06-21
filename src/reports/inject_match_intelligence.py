from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "processed" / "pre_match_intelligence_1_8.json"
REPORT_DIR = ROOT / "outputs" / "reports" / "prematch"

START_MARKER = "<!-- match-intelligence:start -->"
END_MARKER = "<!-- match-intelligence:end -->"


def american_to_implied(odds: int | float) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def decimal_to_implied(odds: int | float) -> float:
    return 1 / odds


def odds_to_implied(odds: int | float, odds_format: str = "american") -> float:
    if odds_format == "decimal":
        return decimal_to_implied(odds)
    return american_to_implied(odds)


def no_vig_probabilities(
    odds_by_outcome: dict[str, int | float],
    odds_format: str = "american",
) -> tuple[dict[str, float], float]:
    raw = {outcome: odds_to_implied(odds, odds_format) for outcome, odds in odds_by_outcome.items()}
    overround = sum(raw.values())
    if overround <= 0:
        raise ValueError("overround must be positive")
    return {outcome: value / overround for outcome, value in raw.items()}, overround


def format_american(odds: int | float) -> str:
    odds_int = int(odds)
    return f"+{odds_int}" if odds_int > 0 else str(odds_int)


def format_odds(odds: int | float, odds_format: str = "american") -> str:
    if odds_format == "decimal":
        return f"{float(odds):.2f}"
    return format_american(odds)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def list_text(items: list[str]) -> str:
    return ", ".join(items)


def render_market_table(item: dict[str, Any]) -> list[str]:
    latest = item.get("latest_odds", {})
    rows = [
        "| Market | Provider | Odds | No-vig market probability | Overround |",
        "| --- | --- | --- | --- | ---: |",
    ]

    moneyline = latest.get("moneyline")
    if moneyline:
        teams = item["teams"]
        odds_format = moneyline.get("odds_format", "american")
        ordered = {
            teams[0]: moneyline["home"],
            "Draw": moneyline["draw"],
            teams[1]: moneyline["away"],
        }
        no_vig, overround = no_vig_probabilities(ordered, odds_format)
        rows.append(
            "| 1X2 | {provider} | {odds} | {probabilities} | {overround} |".format(
                provider=moneyline["provider"],
                odds="; ".join(f"{name} {format_odds(odds, odds_format)}" for name, odds in ordered.items()),
                probabilities="; ".join(f"{name} {pct(prob)}" for name, prob in no_vig.items()),
                overround=pct(overround - 1),
            )
        )

    total = latest.get("total_2_5")
    if total:
        odds_format = total.get("odds_format", "american")
        total_line = str(total.get("line", "2.5"))
        ordered = {f"Over {total_line}": total["over"], f"Under {total_line}": total["under"]}
        no_vig, overround = no_vig_probabilities(ordered, odds_format)
        rows.append(
            "| Total {line} | {provider} | {odds} | {probabilities} | {overround} |".format(
                line=total_line,
                provider=total["provider"],
                odds="; ".join(f"{name} {format_odds(odds, odds_format)}" for name, odds in ordered.items()),
                probabilities="; ".join(f"{name} {pct(prob)}" for name, prob in no_vig.items()),
                overround=pct(overround - 1),
            )
        )

    asian = latest.get("asian_handicap")
    if asian:
        odds_format = asian.get("odds_format", "american")
        ordered = {
            asian["home_label"]: asian["home"],
            asian["away_label"]: asian["away"],
        }
        no_vig, overround = no_vig_probabilities(ordered, odds_format)
        rows.append(
            "| Asian handicap | {provider} | {odds} | {probabilities} | {overround} |".format(
                provider=asian["provider"],
                odds="; ".join(f"{name} {format_odds(odds, odds_format)}" for name, odds in ordered.items()),
                probabilities="; ".join(f"{name} {pct(prob)}" for name, prob in no_vig.items()),
                overround=pct(overround - 1),
            )
        )

    if len(rows) == 2:
        rows.append("| Not captured | Public previews used in this update | N/A | N/A | N/A |")

    return rows


def render_block(item: dict[str, Any]) -> str:
    teams = item["teams"]
    lines: list[str] = [
        START_MARKER,
        "## Pre-Match Intelligence",
        "",
        f"- Lineup status: {item['lineup_status']}.",
        f"- Opening odds: {item['opening_odds_note']}",
        "",
        "### Expected/Confirmed Lineups",
        "",
    ]

    for team in teams:
        lines.append(f"- {team}: {item['lineups'][team]}")
    lines.extend(["", f"Lineup note: {item['lineup_notes']}", ""])

    lines.extend(["### Injuries and Suspensions", ""])
    for team in teams:
        lines.append(f"- {team}: {item['injuries_suspensions'][team]}")
    lines.append("")

    lines.extend(["### Tactical Style Tags", ""])
    for team in teams:
        lines.append(f"- {team}: {list_text(item['tactical_tags'][team])}")
    lines.append("")

    lines.extend(["### Opening/Latest Odds and No-Vig Probabilities", ""])
    lines.append(
        "Market coverage: this update captures 1X2, total 2.5, and Asian handicap where available. "
        "Missing markets were not found in the public pages used here."
    )
    lines.append("")
    lines.extend(render_market_table(item))
    lines.append("")
    lines.append(
        "Note: no-vig probabilities normalize the listed odds after removing bookmaker overround. "
        "They are market probabilities, not the model probabilities above."
    )
    lines.append("")

    lines.extend(["### Sources", ""])
    for source in item["sources"]:
        lines.append(f"- [{source['label']}]({source['url']})")
    lines.extend(["", END_MARKER])
    return "\n".join(lines)


def inject_block(report_text: str, block: str) -> str:
    if START_MARKER in report_text and END_MARKER in report_text:
        before, rest = report_text.split(START_MARKER, 1)
        _, after = rest.split(END_MARKER, 1)
        report_text = before.rstrip() + "\n\n" + block + after
    elif "\n## Current Read\n" in report_text:
        report_text = report_text.replace("\n## Current Read\n", "\n" + block + "\n\n## Current Read\n", 1)
    else:
        report_text = report_text.rstrip() + "\n\n" + block + "\n"

    current_read = (
        "## Current Read\n\n"
        "This report now combines the Poisson model preview with public lineup, injury, tactical, "
        "and market-odds intelligence. Treat bookmaker odds as a dated public snapshot until a "
        "bookmaker API or verified historical odds feed is connected.\n"
    )
    if "\n## Current Read\n" in report_text:
        prefix, _current = report_text.split("\n## Current Read\n", 1)
        report_text = prefix.rstrip() + "\n\n" + current_read
    else:
        report_text = report_text.rstrip() + "\n\n" + current_read

    return report_text.rstrip() + "\n"


def inject_reports(data_path: Path = DATA_PATH, report_dir: Path = REPORT_DIR) -> int:
    data_path = data_path.resolve()
    report_dir = report_dir.resolve()
    items = json.loads(data_path.read_text(encoding="utf-8"))
    for item in items:
        report_path = report_dir / item["report_file"]
        if not report_path.exists():
            raise FileNotFoundError(report_path)
        updated = inject_block(report_path.read_text(encoding="utf-8"), render_block(item))
        report_path.write_text(updated, encoding="utf-8")
        print(f"updated {report_path.relative_to(ROOT)}")
    return len(items)


def main() -> None:
    inject_reports()


if __name__ == "__main__":
    main()
