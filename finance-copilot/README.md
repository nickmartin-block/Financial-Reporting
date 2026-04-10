# Finance Copilot

AI-powered financial dashboard for Block F&S leadership. Provides real-time pacing vs. guidance/consensus, governed metric Q&A, IR document search, and CFO-level KPI visualization.

## Pages

| Page | Purpose | Data Source |
|------|---------|-------------|
| **Quarterly Pacing** | Live pacing vs. AP, guidance, and consensus for GP, AOI, Cash App, Square | Master Pacing Sheet (Google Sheets) |
| **CFO Dashboard** | KPI tiles + trend charts (GP, AOI, GPV, Rule of 40, OpEx) with monthly/quarterly/annual toggle | Block Data MCP (governed metrics) |
| **Q&A** | Natural language queries against Block financial metrics | Block Data MCP + LLM |
| **IR Hub** | Search and chat with Block's IR document corpus | Glean agent |
| **Home** | Landing page with feature cards | — |

## Data Sources

- **Master Pacing Sheet** — `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4` (summary tab). Contains Q pacing, AP, guidance, consensus, WoW deltas. Updated weekly by FP&A.
- **Visible Alpha Consensus Model** — `1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ`. Street consensus estimates by quarter.
- **Block Data MCP** — Governed financial metrics via `fetch_metric_data`. Source of truth for P&L actuals (GP, AOI, VP, OpEx, EPS).
- **Glean** — IR document search and chat across earnings materials, investor presentations, and internal docs.

Both Google Sheets are read via the G2 proxy (`X-G2-Extension: google-drive` header → Drive API CSV export).

## Architecture

```
G2 App Platform (Cloudflare Workers)
├── Hono server (API routes: /api/health, /api/cache, /api/stock, /api/news)
├── D1 database (query result caching)
└── Static client (single-page HTML app)
    ├── fetchPacingSheet()     → Master Pacing Sheet CSV
    ├── fetchConsensus()       → Visible Alpha Sheet CSV
    ├── fetchBDM()             → Block Data MCP fetch_metric_data
    ├── callMCPTool()          → G2 MCP bridge (postMessage to parent frame)
    └── Chart.js               → KPI trend visualization
```

## Development

```bash
npm install          # install dependencies (uses Block Artifactory npm registry)
npm test             # 67 tests (parsers, metrics, server)
npm run build        # esbuild → build/server/index.js + build/client/index.html
```

Deploy to staging (Nick's iteration app):
```bash
# Update build/app.yaml: app_id → finance-copilot, owner → nmart
# Deploy via Block App Kit MCP deploy_site tool
```

## Relationship to finance-copilot-v2

This is Nick's iteration fork of `finance-copilot-v2` (owned by Beckman in squareup/g2-apps). Changes are developed and tested here, then PRed back to the canonical app via squareup/g2-apps.

| | This repo | squareup/g2-apps |
|---|-----------|-----------------|
| App ID | `finance-copilot` | `finance-copilot-v2` |
| Owner | nmart | beckman |
| Deploy access | Nick (direct) | Beckman only |
| Purpose | Iteration sandbox | Production canonical |
| Staging URL | g2.stage.sqprod.co/apps/finance-copilot | g2.stage.sqprod.co/apps/finance-copilot-v2 |
