# Reddit India Demand Mining — Collection Notes

**Run date:** 2026-07-29
**Result: 0 rows collected. Phase 1 failed. Phases 2–4 not run** (per the hard rule: no row in `raw_threads.csv` = no problem may be reported).

## Method-by-method outcome (Phase 0 ladder)

| # | Method | Outcome |
|---|--------|---------|
| 1 | Firecrawl MCP (scrape + search) | Connected, but the Firecrawl account has **zero credits**. `firecrawl_scrape` returned "Insufficient credits"; `firecrawl_search` returned HTTP 402. |
| 2 | Sandbox python/curl against reddit.com `.json` endpoints | The session's network policy blocks **all general egress**. The agent proxy answers `CONNECT 403` for reddit.com, old.reddit.com, api.reddit.com — and even google.com. Only package registries (npm, PyPI, crates) are allowlisted. |
| 3 | WebFetch on `.json` endpoints | reddit.com and old.reddit.com are hard-blocked for the fetcher. Fallback archives also failed: api.pullpush.io → HTTP 403, arctic-shift.photon-reddit.com → HTTP 403. |
| 4 | WebSearch with site:reddit.com | The `site:` operator was ignored; forcing `allowed_domains=[reddit.com]` returned an explicit API error: **reddit.com blocks Anthropic's crawler**, so no reddit.com result can ever be returned by this tool. |

## What this means

There is currently no working channel from this session to any Reddit content —
live site, JSON API, search index, or third-party archive. No subreddit returned
anything because no subreddit was reachable; the thinness is 100% access, 0% demand.

## Cheapest fixes, in order of effectiveness

1. **Top up the Firecrawl account** (firecrawl.dev/pricing). It is already
   connected to this session and is the best tool for Reddit's bot protection.
   A Phase 1 harvest of ~23 subreddits × ~30 queries needs roughly 100–200
   scrape credits using the `search.json` endpoints (1 credit ≈ 1 endpoint page,
   ~100 posts per page).
2. **Loosen this environment's network policy** (Claude Code on the web →
   environment settings) to allow `*.reddit.com`, then method 2 (python +
   requests, descriptive User-Agent, 2s delay) runs as specified. Caveat:
   Reddit sometimes 403s datacenter IPs even for `.json` endpoints.
3. **Provide Reddit API credentials** (a free "script" app from
   reddit.com/prefs/apps) as environment secrets, combined with fix 2 —
   the OAuth API is the most reliable and rate-limit-friendly route.

The pipeline itself (subreddit list, query bank, CSV schema, emerging-vs-perennial
protocol) is ready to re-run unchanged the moment any one of these lands.
