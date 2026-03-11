# Reporting Standards

## Fact Format
When stating metrics in reports, use:
> "Metric X landed at Y (Z% YoY)"

Example: "Revenue landed at $12.4M (up 8% YoY)"

## Data Source
- All report data comes from governed Google Sheets tables
- Do not infer or estimate metrics — pull from source data only

## Report Types
| Report | Cadence | Notes |
|--------|---------|-------|
| Weekly Financial Report | Weekly | Metrics + commentary from data tables |
| Monthly Financial Report | Monthly | Broader trends, brand-level breakdown |
| Flash Update | Monthly | Quick-turn snapshot, same population pattern as weekly |
| Ad-hoc Analysis | As needed | Modeling and trend analysis |

## Agent Architecture
- A **global reporting recipe/constitution** defines standards that apply to ALL reporting agents
- Sub-agents inherit from the global recipe first, then apply their specific deliverable logic
- Never build a reporting agent that bypasses the global recipe
