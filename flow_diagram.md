# Flow Diagrams

## 1. User Flow

```mermaid
flowchart TD
    A([Team member opens tool]) --> B{Select client}
    B --> C[View 7-day summary dashboard]
    C --> D{Status signals}
    D -->|On Track| E[No action needed]
    D -->|Watch| F[Note for next check-in]
    D -->|Investigate| G[Drill into channel detail]
    G --> H[Click → opens source platform]
    H --> I[Verify in Google Ads / Meta / GA4]
    I --> J[Take action or escalate to client]
```

---

## 2. Data Flow

```mermaid
flowchart LR
    subgraph Sources
        A[Google Ads API]
        B[Meta Ads API]
        C[GA4 Data API]
    end

    subgraph Pipeline ["Pipeline (runs nightly via Cloud Scheduler)"]
        D[Fetch raw data]
        E[Validate & clean]
        F[Compute derived metrics\nCPA, ROAS, WoW delta]
        G[Write to BigQuery]
    end

    subgraph Config
        H[Client–channel mapping\nspreadsheet]
        I[Performance thresholds\nspreadsheet]
    end

    subgraph Serving
        J[Looker Studio dashboard]
        K[Internal users]
    end

    subgraph Alerting
        L[Slack alert on failure]
    end

    A --> D
    B --> D
    C --> D
    H --> D
    I --> F
    D --> E --> F --> G --> J --> K
    Pipeline -->|on error| L
```

---

## 3. Pipeline State Machine

```mermaid
stateDiagram-v2
    [*] --> Triggered : Cloud Scheduler (nightly)
    Triggered --> Fetching : Start API calls
    Fetching --> Validating : Raw data received
    Fetching --> Failed : API error / timeout
    Validating --> Transforming : Data passes checks
    Validating --> PartialSuccess : Some channels missing
    Transforming --> Loading : Derived fields computed
    Loading --> Success : BigQuery write confirmed
    Loading --> Failed : Write error
    Failed --> Alerting : Send Slack notification
    PartialSuccess --> Loading : Mark incomplete channels
    PartialSuccess --> Alerting : Send Slack warning
    Success --> [*]
    Alerting --> [*]
```

---

## 4. Dashboard Layout (Wireframe Sketch)

```
┌─────────────────────────────────────────────────────┐
│  [Client Name ▼]          Last updated: Mon 09:02   │
├─────────────┬─────────────┬─────────────┬───────────┤
│  SPEND      │  CONVERSIONS│  CPA        │  ROAS     │
│  £12,400    │  348        │  £35.63     │  3.2x     │
│  ▲ +8% WoW  │  ▼ -4% WoW  │  ▲ +12% WoW │  ▼ -3%   │
├─────────────┴─────────────┴─────────────┴───────────┤
│  CHANNEL BREAKDOWN                                  │
│  ┌──────────────┬────────┬──────┬───────┬────────┐  │
│  │ Channel      │ Spend  │ Conv │ CPA   │ Status │  │
│  ├──────────────┼────────┼──────┼───────┼────────┤  │
│  │ Google Ads   │ £7,200 │ 210  │£34.28 │ ✅     │  │
│  │ Meta Ads     │ £5,200 │ 138  │£37.68 │ ⚠️     │  │
│  └──────────────┴────────┴──────┴───────┴────────┘  │
│                                                     │
│  ⚠️  OBSERVATION: Meta CPA up 18% vs prior week.    │
│     Highest in last 30 days. Review ad creative.    │
└─────────────────────────────────────────────────────┘
```
