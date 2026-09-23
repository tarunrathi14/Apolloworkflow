# GeM Scout: daily playbook

The scheduled routine follows this file every morning. It is written for a
Claude session that has the **Firecrawl** connector. The session's own network
cannot reach `*.gem.gov.in`, so every GeM read goes through Firecrawl.

## Inputs
- `gem-scout/profile.yaml`: brand, keywords, exclusions, scoring weights
- `gem-scout/data/seen_bids.csv`: every bid already reported (dedupe ledger)
- `gem-scout/data/competitors.csv`: sellers seen on TMT bids so far

## Steps

1. **Find open bids on the TenderPulse GeM mirror (primary source).**
   For each term in `keywords.core` and `keywords.adjacent`, scrape
   `https://www.tenderpulse.co.in/tenders?q=<term>&sort=newest` as markdown
   (1 credit each). Every hit shows a `GEM/2026/B/…` number and a
   `bidplus.gem.gov.in/showbidDocument/<id>` link. The `<id>` is GeM's internal
   document id, which you need for step 3. Firecrawl allows 11 scrapes/min; if
   you hit the rate limit, wait about 20 s and retry.

2. **Widen with search (secondary sources).**
   - `firecrawl_search` for `"Deformed Steel Bars" GEM/2026/B` and `TMT GeM bid`
     with `tbs: "qdr:w"`. Mirrors such as tenderpulse, tender18, tendershark
     and infralens expose bid numbers in their snippets. To turn a bid number
     into a document id, search the quoted number (e.g. `"GEM/2026/B/8029238"`);
     the tenderpulse result URL `/tender/<id>` carries it.
   - Scrape `https://www.tender247.com/tenders/tmt-bar-tenders` as **markdown**,
     not json, because json mode invents "GEM/..." numbers from Tender247
     IDs. These listings mix every portal (GeM, state eProc, IREPS). List
     non-GeM ones under "Other portals" only.
   - Do **not** use `firecrawl_agent` or `firecrawl_interact` on
     bidplus.gem.gov.in. Firecrawl's browser gets `ERR_TUNNEL_CONNECTION_FAILED`
     there (tested 2026-09-23). Plain scrapes of GeM pages do work.

3. **Verify every GeM bid before reporting it.**
   First scrape `https://bidplus.gem.gov.in/bidding/bid/getBidResultView/<id>`
   (1 credit, HTML). It gives the **current** end date (after any extension),
   buyer, quantity and turnover criterion. For shortlisted bids, also scrape
   `https://bidplus.gem.gov.in/showbidDocument/<id>` with
   `parsers: ["pdf"]` and `pdfOptions.maxPages: 3`. Record the end date,
   organisation, quantity, EMD, turnover and experience criteria, MSE and MII
   preference, and whether it is a two-packet bid or has a reverse auction.
   Drop the bid if its end date has passed. Never report a bid you did not verify.

4. **Filter and score.** Apply `exclude_terms`, then the `scoring` weights in
   `profile.yaml`. Skip any bid number already in `seen_bids.csv`, unless its
   end date changed (a corrigendum or extension), in which case flag it as updated.

5. **Competitor intel.** For 2–3 TMT bids that closed in the last 30 days, scrape
   `https://bidplus.gem.gov.in/bidding/bid/getBidResultView/<id>`. Append each
   seller, the make offered, qualified or disqualified status, and the L1 price
   if shown to `competitors.csv`. Where the price and quantity allow it, work
   out ₹/MT.

6. **Write the report** to `gem-scout/reports/YYYY-MM-DD.md` (IST date):
   - Top opportunities table (score, bid number and link, buyer, items, qty,
     closes, key eligibility)
   - Adjacent-product opportunities
   - Updated or extended bids
   - Competitor and price intel
   - Other-portal leads (not GeM)
   - Run notes: sources that failed and Firecrawl credits used
     (`firecrawl_credit_usage`)

7. **Persist.** Append the new bids to `seen_bids.csv`, then commit and push
   to the working branch with the message `GeM scout: YYYY-MM-DD`.

8. **Summarise** the top 5 bids and anything closing within 3 days in the
   final chat message. That message is what the push/email notification shows.

## Budget
Firecrawl plan: 1,000 credits/month. Aim for **≤ 30 credits per run**: about 15
TenderPulse queries, about 8 result-view checks, 2–3 PDF queries (the `query`
format on a PDF costs about 8 credits, so use it sparingly) and 2 searches.
If `remainingCredits < 150`, skip step 5 and the adjacent keywords, and say so
in the report.
