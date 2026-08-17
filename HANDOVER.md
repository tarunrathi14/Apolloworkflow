# Handover — Apollo Outbound Workflow (President TMT)

**Owner:** Taarun (taarun@stscl.co.in)
**Last updated:** 2026-08-17
**Business context:** President TMT — TMT rebar manufacturer in Karnataka. Outbound targets
procurement/purchase decision-makers at Bengaluru real-estate developers and civil contractors.

> ⚠️ **Read "Open Items" before running anything.** The live sequence is **paused**, and the last
> two weekly runs were held because of it.

---

## 1. Current state at a glance

| Thing | Status |
|---|---|
| Weekly routine | **Active** — fires Mondays 09:00 IST |
| Sales Outreach Sequence | **PAUSED** (`manual_pause`, since 2026-08-05) — ~100 contacts frozen mid-flight |
| Contacts in Apollo | 404 total |
| Credits remaining | 2,783 (as of 2026-08-17) |
| Week-4 run (2026-08-10) | **Held** after filtering — 1 credit spent, nothing saved |
| Week-5 run (2026-08-17) | **Held** — 0 credits spent, blocker unchanged |

### ⛔ Uncarried instruction — read this first
On 2026-08-17 Taarun typed **"Run Sequence"** and then interrupted before it executed.
**Nothing was done.** The sequence was **not** reactivated and remains paused. If picking this up,
confirm what was intended — reactivating restarts ~100 frozen contacts and releases a large
queued call backlog onto the rep in one go.

---

## 2. Apollo identifiers

Do not guess these — all confirmed from live tool responses.

### Sequences
| Name | ID | State |
|---|---|---|
| Sales Outreach Sequence | `6a6080c3ab6e0e0020a91ae2` | inactive (`manual_pause`) |
| Call First Outreach — Bengaluru Builders | `6a72b817fe136b0010a6673f` | inactive — draft/rollback copy, now redundant |

### Lists (labels, modality = contacts)
| Name | ID | Count |
|---|---|---|
| Builders in Bengaluru | `6a607ee13dbb2e0018c328f3` | 129 |
| Builders in Mysore | `6a72b5f101ce1c00109eb9d7` | 6 |
| Builders - Karnataka Tier 2 | `6a72b82ffe136b0010a66783` | 2 |

### Accounts / people
| Thing | ID |
|---|---|
| User (Taarun) | `695f80e866efc30021e7432b` |
| Team | `695f80e766efc30021e74214` |
| **Sender mailbox — use this** | `695f80e766efc30021e74213` (taarun@stscl.co.in) |
| ⛔ Do NOT use | `6a69b227fee0210020921a3e` (sales@presidenttmt.com) |

`sales@presidenttmt.com` belongs to a **different user** (`6a69aeacac48380010f23ccc`) and is also
flagged `default: true`. Auto-selecting "the default mailbox" picks the wrong one. Pin the ID.

### Scheduled routine
- Trigger ID: `trig_018sFLckhL9PvSv1F3t4e7PY`
- Cron: `30 3 * * 1` (UTC) = **Mondays 09:00 IST**
- Fires into this persistent session; full run instructions live in the trigger prompt.

---

## 3. The sequence (call-first, 8 steps)

Restructured 2026-08-05 from a 10-step email-led cadence to a call-led one.

| # | Step ID | Type | Wait | Day |
|---|---|---|---|---|
| 1 | `6a6089c3788f79001465f783` | LinkedIn view profile | 0d | 0 |
| 2 | `6a608ef558072e0018ad5bbb` | **Call 1** | 0d | 0 |
| 3 | `6a6089c3788f79001465f786` | auto_email (new thread) | 1d | 1 |
| 4 | `6a6089c3788f79001465f784` | LinkedIn connect | 2d | 3 |
| 5 | `6a608ef558072e0018ad5bc0` | **Call 2** | 2d | 5 |
| 6 | `6a608ef558072e0018ad5bbc` | auto_email (reply to thread) | 3d | 8 |
| 7 | `6a72bbd43163c9000c6806e0` | **Call 3** | 4d | 12 |
| 8 | `6a6092044e7e58001c7ecf51` | auto_email (reply to thread) | 4d | 16 |

**Why it changed:** calls converted at **32% Connected-Positive** while email sat at ~5% reply with
a climbing bounce rate. Email steps cut 6 → 3 to protect the sending domain. Steps 6 and 8 were
switched to `reply_to_thread` so follow-ups thread rather than opening new conversations.

---

## 4. Performance to date

**Email (80 delivered, no new sends since the pause):**
- Bounce **6.98%** (6 bounced, 3 hard) — ⚠️ above the 5% warning line, below the 8% auto-pause line
- Spam blocked 3 (3.49%)
- Open 7.5% · **Reply 7.5% (6 replies)** · **1 demo booked** · 1 unsubscribe

> Replies are still arriving from work already delivered — the count went 5 → 6 between
> 10 and 17 August with the sequence switched off.

**Calls (25 completed on Call 1):**
- **Connected-Positive 8 (32%)** · Neutral 5 · Negative 3
- No answer 3 · Busy 2 · **Bad/wrong number 3** · Not in service 1

**Read:** phone is the working channel; email is support and a liability if fed unverified
addresses. ~16% of dialled numbers were bad — verify the number before writing someone off.

**Apollo auto-pause config:** warning 5%, auto-pause 8%, min volume 200, 7-day window.

---

## 5. Client exclusion rule (permanent, user-confirmed 2026-08-03)

**Never cold-pitch a company President TMT already supplies.**

**Source file:** `/root/.claude/uploads/7d9ffde2-66ec-5020-84c1-354d37af72ed/fb901155-Active_Clients_List.xlsx`
sheet `TMT BARS`, column B = client name, column C = qty (MT). 198 clients, 1 Apr – 28 Jul 2026.

> This upload path is session-scoped. **If the file is missing, ask Taarun to re-send it before
> enrolling anyone** — do not silently skip the check.

### Confirmed client matches found so far
| Company | Tonnage | Notes |
|---|---|---|
| Sobha Ltd. / SOBHA Projects & Trade (SPTL) | 2,689.56 MT | Two entities, same client |
| D S Max Properties / DS MAX | 4,069.68 + 88.85 MT | Largest account |
| Nambiar Builders (+ Enterprises LLP, Ensemble Residential) | 315.50 + 38.41 + 12.38 MT | Group entities |
| KNS Industries / KNS Group | 36.38 MT | Matched via `@knsgroup.in` domain |
| Ravi Infrabuild Projects Limited | 3.94 MT | Caught during Belgaum run |

### Also permanently excluded (user instruction 2026-08-03 — not on the client list)
Prestige Group · Sumadhura Infracon · Modern Spaaces · DivyaSree Developers

### Matching guidance
Match on **company name and email domain**, allowing for group entities and spelling variants.
Naive string matching produces false positives — these were checked and **rejected**:
- DivyaSree Developers ≠ "DIVYA TRADERS"
- Gopalan Enterprises ≠ "GOPALA NARAYANA RAO" (a person)
- Embassy Group ≠ "EMBASSY MARBLE & CEMENT COMPANY" — **still unresolved**, see Open Items

### Cleanup already performed (2026-08-03)
9 contacts permanently **removed** from the sequence: 3 × Sobha, 2 × Nambiar, 1 × DS-MAX,
1 × KNS, plus Umesh Raut (GR Constructions) and Pradeep Shetty (Atmos Constructions).

The call script at step 2 names *"the plant in Karnataka that supplies Sobha and DS Max"* as social
proof — those contacts were being cold-pitched with their own employer as the reference.

### Separately: 3 contacts stopped for unverified emails (2026-08-05)
Srinivas Murthy (KEC), Ganesh Kumar (L&T), Puneeth J (buildAhome) — all had guessed addresses
(54–65% confidence). Mode was **stop**, not remove, so this is reversible. They keep mobile
numbers on the Mysore list for manual calling.

---

## 6. Run history

| Run | Date | Page | Enriched | Saved | Enrolled | Credits |
|---|---|---|---|---|---|---|
| Week 1 | Jul 22 | 1 | 50 | 50 | 37 (13 skipped) | ~378 |
| Week 2 | Jul 27 | 1 | 50 | 50 | 49 (1 skipped) | ~291 |
| Week 3 | Aug 3 | 2 | 50 | 49 | 15 (user trimmed) | ~291 |
| Mysore | Aug 5 | — | 17 | 6 | 6 | 106 |
| Karnataka Tier 2 | Aug 5 | — | 4 | 2 | 0 | 12 |
| Week 4 | Aug 10 | 3 | — | — | — | 1 (held) |
| Week 5 | Aug 17 | — | — | — | — | 0 (held) |

**Page rotation:** advance `page` each week. Pages 1–3 are mined out. **Week 6 should start at
page 4.**

---

## 7. Lessons learned (don't rediscover these)

1. **Phone reveals cost ~8 credits each, not 1.** A 50-person run with phones is ~275–300 credits.
2. **Apollo's `email_status: "verified"` is not always trustworthy.** Check for
   `extrapolated_email_confidence` on the same record — a guessed address can still be labelled
   verified.
3. **Search quality degrades sharply by page.** Page 1 was ~85% relevant; page 3 was 35%. The
   keyword tags pull in Wipro, Infosys, Bosch, ZETWERK and similar.
4. **Coworking and interior-fitout firms are weak fits** for structural rebar — they buy furniture
   and MEP. Keep separate from the default enrolment set (WeWork, IndiQube, BHIVE, MOJO Campus,
   Table Space, Livspace, HomeLane, Design Arc Interiors, Zyeta, Simpliwork, Truww, Studio19).
5. **Karnataka outside Bengaluru is not viable.** Mysore: 39 people total, 6 usable.
   Mangalore: 17, mostly Gulf-based. Belgaum: 17, one builder. Hubli: 11, one builder.
   Don't schedule recurring runs for these.
6. **Apollo tool responses are large.** Most calls overflow the context limit and are written to
   `tool-results/*.txt`. Parse them with a script rather than reading them.
7. **Filtered-but-unenriched candidates do not persist.** They live only in session context. If a
   run is held at the enrichment gate, the search must be re-run (1 credit) to recover them.

---

## 8. Open items

### 🔴 Blocking
1. **Sequence is paused** (`manual_pause`, 2026-08-05). ~100 contacts frozen. Two weekly runs held
   because of it. Unknown whether Taarun paused it deliberately or in response to the bounce
   warning — **ask before reactivating.**
2. **"Run Sequence" instruction (2026-08-17) was interrupted and never carried out.** Confirm intent.
3. **`[Name]` placeholder is still in all three call scripts.** Reps will read the literal text.

### 🟡 Needs attention
4. **Bounce rate 6.98%** — between Apollo's 5% warning and 8% auto-pause. The restructure halves
   future email volume but does not undo the 6 bounces already recorded.
5. **Embassy contacts (3) unresolved.** Chetan Palguna + Alaguraja Arumugam (Embassy Group),
   Mohamad Ahmed (Embassy Services). Client list has "EMBASSY MARBLE & CEMENT COMPANY"
   (199.95 MT) — likely a different entity, unconfirmed. Left enrolled.
6. **Week-4 candidates were never persisted.** 34 filtered leads (19 builders, 15 fitout) from
   page 3 are lost. Re-run the page-3 search to recover if wanted.
7. **Draft sequence `6a72b817fe136b0010a6673f` is redundant.** Archive or keep as rollback.
8. **Trial-load claim needs verification.** Scripts and emails offer "twelve tonnes on your next
   slab" for a lab test. Confirm President TMT will honour this.

### 🟢 Nice to have
9. Tier-2 Karnataka contacts (2 saved; only Rohit Swamy at Marvel Properties is genuinely useful)
   are unenrolled and unworked.
10. Consider dropping the weekly target below 50 given the thinning pool, or widening industry tags.

---

## 9. Restarting the weekly run

Pick one and instruct:

| Option | What happens |
|---|---|
| **Reactivate the sequence** | Switch it on, resume the full run. ~100 frozen contacts restart from their current steps; a large call queue lands at once. |
| **Run and bank the leads** | Search → enrich → save to list, no enrolment. Gives inventory ready for restart. ~275 credits. |
| **Keep holding** | Skip each Monday; report only when something changes. |

---

## 10. Weekly workflow definition

Authoritative version lives in the trigger prompt (`trig_018sFLckhL9PvSv1F3t4e7PY`). Summary:

1. **Search** — `apollo_mixed_people_api_search`, procurement/purchase titles, Bengaluru (both
   person and org location), verified email only, 15+ employees, real-estate/construction keyword
   tags, `per_page: 100`, advancing `page` weekly.
2. **Review** — four filters: (a) industry, (b) net-new only, (c) **client exclusion**,
   (d) builders preferred over fitout. Rank by seniority, take top 50.
3. **Enrich** — `apollo_people_bulk_match` in batches of 10 with `reveal_phone_number: true`, then
   poll `apollo_webhook_result_show` per request_id. Drop anyone whose email is unavailable.
4. **Save** — bulk create, then add to "Builders in Bengaluru".
5. **Approval gate** — ⛔ **never enrol without fresh explicit approval.** Present the batch split
   into builders vs fitout, note client exclusions, and wait.

Standing approval covers steps 1–4 and their credit cost. Step 5 always requires a fresh yes.
Stop and ask if credits drop below 100.
