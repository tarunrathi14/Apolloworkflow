# Runbook — Weekly Apollo Outbound Run (fresh-session mode)

This is the operating procedure for the Monday routine. From 2026-08-17 each run executes in a
**fresh session with no memory of previous runs**, so everything needed is either in this repo or
queryable from Apollo. Do not assume prior context.

**Read `HANDOVER.md` in this repo first** — it carries the project background, all Apollo IDs, and
current open items.

---

## Before you start

```bash
git fetch origin claude/monday-outbound-workflow-eops28
git checkout claude/monday-outbound-workflow-eops28
```

Everything below depends on files on that branch.

### Hard preconditions — stop and notify if any fail

| Check | If it fails |
|---|---|
| `data/active_clients.csv` exists | **Do not enrich or enroll.** Notify Taarun that the client list is missing. |
| Apollo tools available | Notify that the Apollo connector needs reattaching. |
| Credits ≥ 100 | Stop before enriching; notify. |

---

## The run

### 0. Read state
`data/run_state.json` → `next_search_page`. Use that as the `page` parameter.

### 1. Search
`apollo_mixed_people_api_search`, 1 credit per request.

**Search C — directors at mid-size construction firms. THIS IS THE ACTIVE SEARCH** (opened
2026-09-07). Pool 1,077 — far larger and cleaner than anything before it. Page 1 yielded 53 saved.

- `person_titles`: director, managing director, founder, proprietor, partner, owner
- `include_similar_titles`: **false**
- `person_locations`: `["Bengaluru, India"]`
- `organization_locations`: `["Bengaluru, India"]`
- `contact_email_status`: `["verified"]`
- `organization_num_employees_ranges`: `["25,200"]`
- `q_organization_keyword_tags`: real estate development, real estate contractors, construction,
  building construction, residential building construction, nonresidential building construction
- `per_page`: 100, `page`: `search_c_directors_25_200.next_search_page` from `run_state.json`

⚠️ **Do not add the bare `real estate` or `commercial real estate` tags.** They are what wrecked
Search B — they match law firms, fintech, proptech and brokerages that merely mention property.
Construction-only tags are the whole reason Search C works.

**Search A (procurement titles, 15+ employees) — EXHAUSTED.** Pool was 361; pages 1–4 used it up.
**Search B (director titles, 15–24 employees) — worked out.** Page 1 gave 33 of 100, page 2 gave 2
of 100. Its `next_search_page` is 3 if ever needed, but prefer Search C.

Founder/director titles beat procurement titles in this market: small and mid-size Bengaluru
developers are run by their founders, while procurement-title searches surface IT and
manufacturing staff.

### 2. Review — four filters, all of them

**a. Industry.** Drop anything outside real estate / construction / fitout. Recurring offenders:
Wipro, Infosys, Bosch, ZETWERK, AJAX Engineering, Schneider, BEML, Asian Paints, SKF, Molex,
Ashirvad, First American, Geberit, Emmvee, L&T Construction Equipment (the *equipment* arm),
Zuari Cement.

**b. Net-new only.** Page through `apollo_contacts_search` and collect every `person_id`. Exclude
anyone already saved. (576 contacts as of 2026-09-07 — **6 pages** at `per_page: 100`; keep paging
until a page returns fewer than 100.) Note a company already appearing in the base does not mean
the person does — dedupe on `person_id`, not company name.

**c. Client exclusion — never cold-pitch an existing customer.**
Read `data/active_clients.csv` (198 rows, `client_name`, `qty_mt`). Match on **company name and
email domain**, allowing group entities and spelling variants.

Known client groups — exclude all entities:
| Group | Variants seen |
|---|---|
| Sobha | "Sobha Ltd.", "SOBHA Projects & Trade Pvt. Ltd. (SPTL)" |
| DS-MAX | "D S Max Properties Pvt Ltd", "DS MAX" |
| Nambiar | "Nambiar Builders", "NAMBIAR ENTERPRISES LLP", "NAMBIAR ENSEMBLE…" |
| KNS | "KNS Industries", "KNS Infrastructure" (domain `knsgroup.in`) |
| Ravi Infrabuild | "RAVI INFRABUILD PROJECTS LIMITED" |
| Ramsons | "RAMSONS TRENDSQUARES REALTY LLP" |
| SNN | "SNN BUILDERS", "SNN PROPERTIES LLP", "SNN SPIRITUA DEVELOPERS" — also SNN Estates, SNN Raj Corp (~539 MT) |
| Ruchira | "RUCHIRA DEVELOPERS LLP" — also Ruchira Projects |
| Elegant | "ELEGANT BUILDERS AND DEVELOPERS", "ELEGANT ALTIMA", "ELEGANT ATMOS" (~558 MT) |

Also permanently excluded by user instruction (2026-08-03), though not on the client list:
**Prestige Group · Sumadhura Infracon · Modern Spaaces · DivyaSree Developers**

Known false positives — do **not** exclude these:
- DivyaSree Developers ≠ "DIVYA TRADERS"
- Gopalan Enterprises ≠ "GOPALA NARAYANA RAO" (a person)
- Embassy Group vs "EMBASSY MARBLE & CEMENT COMPANY" — unresolved; treat as **not** a client
  and flag it in the summary.
- Durga Projects & Infrastructure ≠ "SRI DURGA TRADERS" (a trader, different firm)
- Disha Habitat ≠ "ADISHAKTI SMELTERS" (substring artefact — "DISHA" inside "ADISHAKTI")

**d. Fit.** Structural builders, developers and civil contractors are the target — they buy TMT
rebar. Coworking operators and interior-fitout firms are weak fits: WeWork, IndiQube, BHIVE,
MOJO Campus, Table Space, Livspace, HomeLane, Design Arc Interiors, Zyeta, Simpliwork, Truww,
Studio19, Acme Interiors, Nag Interiors, The KariGhars, Aiti Interieurs, LVNG Design Studio.
Keep them in a separate group; they are **not** part of the default set.

Rank by seniority (Heads/GMs > Managers > Executives) and take the top 50, fewer if fewer exist.

### 3. Enrich
`apollo_people_bulk_match`, batches of 10.

⚠️ **Check `direct_dial_credit` in `apollo_usage_stats_credit_usage_stats` before setting
`reveal_phone_number: true`.** It hit zero on 2026-08-17 and the pool only refills at the cycle
reset. With no direct-dial credits, set `reveal_phone_number: false` — enrich emails, save the
leads, and note in the summary that phones still need revealing once credits return.

With phones available: `reveal_phone_number: true`, then poll `apollo_webhook_result_show` with
each top-level `request_id`.

- Cost: 1 credit per email match, **~8 credits per revealed phone**. A 50-person run is ~275–300
  with phones, ~50 without.
- Drop anyone whose email comes back `unavailable`.
- ⚠️ Apollo may report `email_status: "verified"` while also setting
  `extrapolated_email_confidence`. That means the address is a **guess**. Exclude those from the
  saved set and list them separately in the summary — they have caused bounces before.

### 4. Save
`apollo_contacts_bulk_create` with all enriched fields, then
`apollo_labels_add_entity_ids_to_label_names` → list **"Builders in Bengaluru"**
(`6a607ee13dbb2e0018c328f3`). Weak-fit fitout/coworking people go to
**"Fitout & Interiors - Bengaluru"** (`6a82b1893374bd0010197047`) instead.

⚠️ The `label_names` field on a contact object in `apollo_contacts_bulk_create` is silently
ignored — contacts come back with `label_ids: []`. You **must** make the separate
`apollo_labels_add_entity_ids_to_label_names` call, using the contact ids from the create
response. Verify the returned `cached_count` went up.

### 5. STOP — do not enroll

> ⛔ **An unattended run must never add anyone to a sequence.**
> Decided with Taarun on 2026-08-17: the scheduled Monday run banks leads only. Enrollment is a
> decision he makes explicitly.

This applies to the **fresh-session Routine**. When Taarun is present and explicitly says to
enroll, do it — that is the fresh approval the gate exists for. He has done so twice
(2026-08-27, 2026-09-07).

To enroll: re-resolve the sequence with `apollo_emailer_campaigns_search` and the mailbox with
`apollo_email_accounts_index` **in the same session** — both have changed underneath us before —
then `apollo_emailer_campaigns_add_contact_ids` with `status: "active"` and
`sequence_same_company_in_same_campaign: true` (many of these firms yield 2–4 contacts each).

### 6. Update state and commit
Advance `search_c_directors_25_200.next_search_page`, append to its `pages_used`, record the
page's yield in `yield_by_page`, update `last_run_date` and `last_run_outcome` in
`data/run_state.json`, then commit and push to `claude/monday-outbound-workflow-eops28`.

Quality degrades by page within a search. Search A: page 1 ~85% relevant, page 3 ~35%, page 4 ~10%.
Search B: page 1 33%, page 2 2%. When a page yields almost nothing, don't grind the next one —
change the filters (size band or keyword tags) as Search C did.

---

## The summary to send

Keep it short and factual:

- Found / net-new after filters / enriched / saved
- **Client-excluded** — who and which client they work for
- Split of saved leads: structural builders vs fitout/coworking
- Anyone dropped for an unavailable or guessed email
- **Credits consumed and remaining**
- Sequence state (paused or active) and the reminder that nothing was enrolled
- Anything that needs a decision

---

## Do not do these

- Do not enroll anyone in any sequence.
- Do not reactivate the Sales Outreach Sequence.
- Do not send from `sales@presidenttmt.com` (`6a69b227fee0210020921a3e`) — it belongs to a
  different user and is also flagged `default: true`. The correct mailbox is
  `taarun@stscl.co.in` (`695f80e766efc30021e74213`).
- Do not enrich if `data/active_clients.csv` is missing.
- Do not spend if credits are below 100.
