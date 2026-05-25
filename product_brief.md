# Task 1: Product Brief
## Marketing Performance Intelligence Tool — v1 Scope

---

## The Problem

Every week, someone on the team gets asked:
> "How is our marketing performing right now, and where should we be focusing?"

Today, answering that question means:
1. Logging into 3–5 separate tools (Google Ads, Meta, GA4, etc.)
2. Manually pulling numbers for each channel
3. Stitching them together in a spreadsheet or Slack message
4. Writing a narrative explaining what it all means

The result is **inconsistent** (different people frame things differently), **slow** (30–90 minutes per ask), and **fragile** (if the one person who knows how to do it is unavailable, the question just waits).

This is not a data problem. The data exists. It is an **access and assembly problem**.

---

## The Tool: What It Is

A lightweight internal dashboard — built on top of tools the team already uses — that answers the core question in under 30 seconds, without needing an analyst to manually pull anything.

**One-line definition:**
> A read-only, auto-refreshing summary view that shows cross-channel marketing performance for the current period, with a clear signal for where attention is needed.

---

## Primary User

**The internal analyst / account manager** — not the client.

This is a deliberate v1 decision.

Clients have different contexts, different metric literacy, and different trust thresholds. Building for them first makes the scope unmanageable and raises presentation/accuracy questions that are not worth solving yet.

The internal user already understands the metrics. They just need the assembly done for them. Solving it well internally first creates a foundation for a client-facing layer in v2.

---

## What a Successful Interaction Looks Like

A team member opens the tool on Monday morning. In one view, they see:

- **This week vs last week** across each active channel (spend, clicks, conversions, CPA)
- A **simple status signal** per channel: `On Track` / `Watch` / `Investigate`
- **One highlighted observation** per client: the single most notable thing happening right now

They walk away knowing:
- Which clients need a conversation today
- Which channels are under/over-performing vs the recent baseline
- What they would say if a client emailed them right now

No digging. No manual pulling. No waiting.

---

## Data Requirements

### What the Tool Needs

| Data Point | Source | Refresh |
|---|---|---|
| Spend by channel | Google Ads API, Meta Ads API | Daily |
| Clicks / Impressions | Same | Daily |
| Conversions / CPA / ROAS | Same + GA4 Data API | Daily |
| Channel targets | Internal config (spreadsheet) | Manual |
| Client ↔ channel mapping | Internal config | Manual |

### How It Gets There

The team is not changing their tools. So the integration strategy is:

1. **Pull from existing APIs** — Google Ads API, Meta Marketing API, GA4 Data API. All are free-tier accessible and well-documented.
2. **Store a daily snapshot** in BigQuery (already in use by the team).
3. **Serve a dashboard** on top — Looker Studio (free, native BigQuery connector) or a simple internal web app.

The pipeline runs on a nightly schedule (Cloud Scheduler). If it fails, it sends an alert to a Slack channel. The dashboard always shows a **last-refreshed timestamp** so users know if something is stale.

### Reliability

Raw API data is imperfect. The tool handles this explicitly:

- Shows a `data incomplete` flag if a channel's pull failed that day
- Displays the last-good date alongside any metric
- **Never silently shows zeros** — zeros are marked as unconfirmed

**Trust is the most critical product feature.** A dashboard that shows wrong numbers confidently is worse than no dashboard at all.

---

## v1 Scope: What Is In

- Single-page summary view per client
- Date range: current 7-day rolling vs prior 7-day rolling
- Channels: Google Ads + Meta Ads (GA4 as secondary conversion layer)
- Metrics: Spend, Clicks, Impressions, Conversions, CPA, ROAS
- Status signals based on configurable thresholds
- Auto-refresh: once per day (overnight)
- Last-refreshed timestamp on every view
- Slack alert if the pipeline errors
- Internal access only (no client-facing login)

---

## v1 Scope: What Is Explicitly Out

| Excluded | Reason |
|---|---|
| Client-facing login | Adds auth, design, and trust overhead. Solve internally first. |
| AI-generated narrative | The signal needs to be trusted before the interpretation. Phase 2. |
| TikTok / LinkedIn / Pinterest | Low priority for most clients. Add on demand. |
| Custom date range picker | Rolling 7-day covers 80% of use cases. Custom ranges add UI complexity. |
| Automated client alerts | Internal team must be the filter. Wrong automation sends clients unexplained anomalies. |
| Budget pacing / forecasting | Different problem, scope creep risk. |
| Historical trends beyond 4 weeks | Needs more storage design. Phase 2. |

---

## What Would Make Users Trust It

1. **Show the source.** Every metric links to the originating platform report.
2. **Show freshness.** Timestamp on every data point — staleness is the biggest dashboard trust killer.
3. **Flag incomplete data explicitly.** A missing pull must never silently become a zero.
4. **Pre-launch reconciliation.** Before go-live, compare dashboard output against what an analyst would have manually pulled for 3 clients. Document deltas. Fix them. Then ship.

---

## What I Would Revisit With More Time

- **Config UI**: Channel mappings and targets currently live in a spreadsheet. Fragile. A simple admin form would make this robust.
- **Anomaly detection**: Statistical baseline thresholds (is this metric outside its normal range?) would beat fixed-threshold status signals.
- **Deeper GA4 integration**: v1 uses only conversion counts. The API offers full funnel data, user behaviour, and more.
- **Multi-client overview**: A team-lead view comparing performance across all clients, not just within one.

---

## Decisions Made Without Full Information

- **Looker Studio vs custom UI**: Assumed Looker Studio is acceptable — zero maintenance overhead, native BigQuery connector. If the team needs custom interactivity or has strong UI opinions, a React app on the same BigQuery data is the alternative.
- **Daily refresh is enough**: Assumed near-real-time is not required. If the team needs intraday updates for active campaign management, the pipeline runs hourly, which changes cost and complexity.
- **Google + Meta as starting channels**: Covers the majority of spend for most marketing clients. Would validate against actual client mix before building.
