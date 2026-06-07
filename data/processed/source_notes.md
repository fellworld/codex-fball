# 2026 World Cup group-stage data notes

Last checked: 2026-06-06

## Files

- `groups.csv`: 12 groups, 48 teams, one row per team.
- `group_stage_schedule_cst.csv`: 72 group-stage matches, one row per fixture.

## Time zone

`group_stage_schedule_cst.csv` keeps the source BST time and adds converted China time:

- `date_bst`, `time_bst`: British Summer Time, UTC+1.
- `date_china`, `time_china`: China Standard Time / Asia/Shanghai, UTC+8.

Conversion rule: China time = BST + 7 hours.

## Sources

- FIFA official match schedule page: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums
- FIFA final draw results page: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/final-draw-results
- FourFourTwo group-stage fixture list in BST, last updated 2026-06-05: https://www.fourfourtwo.com/competition/world-cup-2026-fixtures-day-by-day
- FourFourTwo China Standard Time calendar page, last updated 2026-04-22: https://www.fourfourtwo.com/competition/world-cup-2026-calendar-cst

## Notes

- Team names use English names for consistency with source fixtures.
- `source_order` is chronological order from the fixture list, not guaranteed to be the official FIFA match number.
- Venue fields are not included yet. Add them after verifying against the official FIFA schedule table or downloadable calendar.
