# VeriScope

**Regression intelligence for engineering teams.**

VeriScope analyzes pull requests, historical failures, coverage signals, and fragility patterns to recommend exactly what should be tested — and explain why.

**Website:** [https://amrsalahsap-droid.github.io/VeriScope/](https://amrsalahsap-droid.github.io/VeriScope/)  
**Source:** [github.com/amrsalahsap-droid/VeriScope](https://github.com/amrsalahsap-droid/VeriScope)

## What it does

- **Explainable recommendations** — every suggested test includes evidence-backed reasoning
- **Organizational fragility memory** — remembers recurring failure patterns across repositories
- **Operational trust** — built for calm, deterministic release decisions

Now in a pilot program.

## Repository layout

| Path | Purpose |
| --- | --- |
| `app/` | Python backend (recommendation, journey, and architecture intelligence) |
| `landing-page/` | Next.js product UI |
| `alembic/` | Database migrations |
| `docs/` | Public site and operational docs |
| `scripts/` | Helper scripts |

## Local development

Backend and frontend are separate. The landing-page app proxies API calls to a local backend on port 8000.

```bash
# Frontend
cd landing-page
npm install
npm run dev
```

See `docs/` for CI/CD production runbooks and deployment notes.
