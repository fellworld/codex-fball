# Team squad, club, and tactics data plan

Last checked: 2026-06-06

## Objective

Build team-level football profiles for prediction:

- Which clubs each squad member plays for.
- Which players are likely starters or core rotation players.
- Who the head coach is.
- How each coach/team tends to play.
- Whether a team profile leans attacking, defensive, transitional, possession-heavy, direct, or set-piece focused.

## Primary source for squads

FIFA published the confirmed final squad lists on 2026-06-02:

- FIFA media release: https://inside.fifa.com/organisation/media-releases/world-cup-2026-48-squads-confirmed
- Official squad PDF: https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf

The FIFA release states that the final squad lists contain 48 teams and 1,248 players. It also notes that replacements are only permitted for serious injury or illness up to 24 hours before a team’s first match, unless otherwise approved by FIFA.

## Output tables

### `data/processed/squad_players.csv`

One row per player.

Recommended fields:

- `team`
- `team_code`
- `position`
- `player_name_raw`
- `dob`
- `club`
- `club_country_code`
- `height_cm`
- `is_likely_starter`
- `starter_confidence`
- `role_notes`
- `source`
- `source_checked_at`

### `data/processed/team_coaches.csv`

One row per team.

Recommended fields:

- `team`
- `team_code`
- `head_coach`
- `coach_nationality`
- `source`
- `source_checked_at`

### `data/processed/team_tactical_profiles.csv`

One row per team.

Recommended fields:

- `team`
- `team_code`
- `head_coach`
- `base_shape`
- `style_tag_primary`
- `style_tag_secondary`
- `attack_defense_bias`
- `tempo`
- `pressing_height`
- `possession_preference`
- `directness`
- `transition_threat`
- `set_piece_threat`
- `defensive_line`
- `goal_expectation_bias`
- `notes`
- `confidence`
- `source_notes`

## Tactical coding rubric

Use compact numeric labels so the model can consume them:

- `attack_defense_bias`: `attack`, `balanced`, `defense`
- `tempo`: `slow`, `medium`, `fast`
- `pressing_height`: `low`, `mid`, `high`
- `possession_preference`: `low`, `mixed`, `high`
- `directness`: `short`, `mixed`, `direct`
- `defensive_line`: `low`, `mid`, `high`
- `goal_expectation_bias`: `under`, `neutral`, `over`

These tags should be evidence-backed, not just reputation-based. Use recent competitive matches, coach history, squad profile, and expected XI.

## How this helps goal prediction

For match total goals:

- High press + high defensive line can increase transition chances and defensive risk.
- Low block + low tempo often reduces total shot volume.
- Strong set-piece threat matters against teams that concede corners/free kicks.
- Club concentration helps chemistry: many players from the same club/league can raise tactical cohesion.
- Starters from high-quality clubs can improve baseline attack/defense ratings.
- Coach style can adjust expected goals even when Elo/FIFA ranking is similar.

## Important distinction

The FIFA squad list gives the official 26 players and club affiliations. It does not identify the starting XI. Likely starters should be inferred separately from:

- Recent lineups.
- Qualification matches.
- Pre-tournament friendlies.
- Injury reports.
- Local beat reports and reliable previews.

