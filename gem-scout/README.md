# GeM Scout: President TMT

Every morning this finds open **GeM (Government e-Marketplace)** bids that
President TMT can supply. It covers TMT rebar first, then adjacent steel
products. It also tracks which sellers compete on those bids and the prices
they win at.

| File | Purpose |
|------|---------|
| `profile.yaml` | Your product, grades, states, keywords and scoring. **Edit this.** |
| `PLAYBOOK.md` | The steps the daily routine runs |
| `reports/YYYY-MM-DD.md` | One report per morning |
| `data/seen_bids.csv` | Ledger of bids already reported, so you only see new ones |
| `data/competitors.csv` | Sellers, makes and L1 prices seen on TMT bids |

## How it runs
A Claude Code routine starts a fresh cloud session every day at **07:00 IST**.
The session follows `PLAYBOOK.md`, then commits the report and pushes it to
this branch. You get the top 5 bids as a push notification and an email.

## Data sources
The cloud session's own network cannot reach `gem.gov.in`, so every read goes
through the **Firecrawl** connector:

1. **TenderPulse** (`tenderpulse.co.in/tenders?q=…`): a free mirror of active
   GeM BidPlus bids, refreshed twice a day, with GET search. This is the main
   discovery feed. It holds only about 1k of GeM's roughly 45k live bids, so
   coverage is partial.
2. **Web search** (`firecrawl_search`) over mirrors (tender18, tendershark,
   infralens) catches bids TenderPulse misses, such as the NALCO TOR-steel bid
   on 2026-09-23. Firecrawl's live browser cannot open GeM (tunnel error), so
   GeM's own keyword search is out of reach.
3. **Tender247**: multi-portal leads, including non-GeM portals.
4. **GeM itself**: every bid is verified on `showbidDocument/<id>` (PDF) or
   `getBidResultView/<id>` before it is reported.

## Limits
- Firecrawl allows 1,000 credits a month on the current plan. A run costs
  about 30–40 credits, so a month of daily runs uses most of the allowance.
- Firecrawl also limits scrapes to 11 per minute, so a run takes 10–15 minutes.
- Without a direct connection to GeM, some bids will be missed. For complete
  coverage, also save a keyword search on GeM's own seller dashboard.
