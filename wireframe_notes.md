# Wireframe Annotations

## Dashboard — Annotated

### Header Bar
- **Client selector (dropdown)**: The analyst switches between clients. One view per client; no multi-client blending in v1.
- **Last updated timestamp**: Always visible. If > 25 hours old, turns amber. If > 48 hours old, turns red. This is non-negotiable for trust.

### Summary Metrics Row (top KPI cards)
- Shows: Spend, Conversions, CPA, ROAS
- Each card shows: current 7-day value + WoW % change with directional arrow
- Colour coding on the delta: green = improvement, red = deterioration (direction is goal-aware — a CPA increase is bad; a ROAS increase is good)
- **No absolute targets shown in v1** — WoW delta is more actionable than "vs target" when targets may be stale

### Channel Breakdown Table
- One row per active channel
- Columns: Channel name, Spend, Conversions, CPA, Status signal
- **Status signal logic**:
  - ✅ On Track: CPA within ±10% of prior week
  - ⚠️ Watch: CPA up 10–25% vs prior week
  - 🔴 Investigate: CPA up >25% vs prior week OR spend anomaly (>40% swing)
  - Thresholds are configurable per client in the config spreadsheet
- Each row's channel name is a **link to the platform** (Google Ads, Meta Ads Manager)

### Observation Banner
- Auto-generated from the data: one plain-English observation per client
- Logic (rule-based in v1, not AI):
  - Find the metric with the largest adverse WoW change
  - Format: "[Channel] [metric] [direction] [magnitude] vs prior week. [Suggested action]."
  - Suggested actions are templated strings, not generated text
- Shown only if at least one channel has a Watch or Investigate status
- Deliberately minimal — one observation only, not a list

---

## Design Decisions

### Why not traffic lights?
Traffic lights (red/amber/green) are overused and often ignored. Using labelled text signals (On Track / Watch / Investigate) forces a brief mental pause and makes the meaning clearer, especially to people who are red-green colour blind.

### Why Looker Studio and not a custom app?
- Zero infrastructure to maintain
- Native BigQuery connector (no custom API layer)
- Free
- The team can own and modify it without needing a developer
- Acceptable trade-off: less visual control, but the internal use case does not require pixel-perfect design

If the team outgrows Looker Studio's flexibility, the same BigQuery data can serve a custom React dashboard with no changes to the pipeline.

### Why one observation and not a full summary?
Dashboards with 10 insights are dashboards with zero insights. One thing, clearly stated, with an action attached — that is what drives behaviour. More can be added in v2 once the team validates what they actually act on.
