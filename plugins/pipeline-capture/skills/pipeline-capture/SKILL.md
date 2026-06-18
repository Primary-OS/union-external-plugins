---
name: pipeline-capture
description: Reconstruct a venture fund's deal pipeline from Gmail + Google Calendar. Retrospective scan — produces a single pipeline.csv (all confidences, low rows flagged via the confidence/needs_review columns) shared with Primary for Seen Deal Analysis. Phases — Calendar discovery → windowed Gmail keyword passes → contact-graph expansion → classification → deck/doc synthesis (reads linked Google Slides/Docs + PDF/pptx/docx attachments + inline pitches to describe pre-opportunity & deck-only deals, sharing only the paraphrase) → aggregation. Use when the user says "scan my email for pipeline", "build my pipeline from email", "capture my deals from gmail", "/pipeline-capture", or wants to produce a pipeline CSV from their inbox. Defaults to 2025-01-01 through today; accepts an optional date range override (e.g. "2024-2025", "since 2024-06-01", "all of 2025").
argument-hint: [start-date] [end-date]
---

# Pipeline Capture Skill

Reconstruct a fund's deal pipeline from Gmail + Google Calendar. Output is a CSV that Primary Venture Partners ingests for Seen Deal Analysis (overlap with PitchBook, timing advantage vs Primary's own Affinity pipeline).

## Environment

You run inside **Claude Code** with Anthropic's official **Gmail** and **Google Calendar** connectors enabled, plus local filesystem access. Before starting:

1. Verify the connectors are connected. The Anthropic **Gmail** connector exposes tools for searching threads, reading a thread, and reading user profile. The Anthropic **Google Calendar** connector exposes tools for listing events and reading event details. The Anthropic **Google Drive** connector (used in Phase 4b to read linked Slides/Docs/files) exposes search / metadata / read-content tools. If Gmail or Calendar is not connected, tell the user to enable it in Claude Code → Settings → Connectors and stop. Google Drive is required only for Phase 4b deck/doc synthesis — if it's absent, run the rest of the skill and skip Phase 4b with a warning.
   - **Office-file extraction is local and dependency-free**: `.docx` via macOS `textutil`, `.pptx`/`.docx` fallback via python3 stdlib (`zipfile` + `xml`). No LibreOffice, no `pip install`. PDFs are read visually by the built-in Read tool.
2. Discover exact tool names dynamically — do not hardcode. Use the tools the active Anthropic connectors expose (search / list / get patterns).
3. Output goes to the **current working directory** (local filesystem). The user can move the CSVs wherever they want afterwards.

## Execution model — orchestrator + subagents

**You are the orchestrator, not the worker.** Real-world VC inboxes contain enough volume that running every Gmail search inline would exhaust the context window before classification finishes. Instead:

- The **main skill** (you) handles: argument parsing, fund-domain detection, plan confirmation, state-file management, Phase 5 aggregation, and reporting back to the user.
- The **heavy phases** (Phase 1 calendar discovery, Phase 2 keyword passes, Phase 3 contact expansion, Phase 4 classification) are dispatched as **Agent tool subagents**, one per phase. Each subagent gets a fresh context window, runs its phase end-to-end, writes intermediate state to disk, and returns a short summary (counts + any anomalies).
- The user sees one progress line per phase, not the per-tool-call noise. Subagents are an implementation detail — do not mention them in user-facing output.

Briefing a subagent: pass it (1) which phase to run, (2) the absolute path to the working directory, (3) the scan window, (4) the fund domain, (5) the global noise filter (below), (6) explicit "write to disk; return ≤200-word summary".

If the Agent tool is unavailable in this environment, fall back to running phases inline — but warn the user that the run may need to be re-invoked one or more times to complete.

## Global Gmail noise filter

Append the following to **every** Gmail search query in Phases 2 and 3. This drops the bulk of mass-mailing / notification noise that dominates real inboxes and that no founder thread should ever fall under:

```
-category:promotions -category:updates -category:forums -category:social -from:notifications@github.com -from:notifications@slack.com -from:noreply -from:no-reply -from:notify -from:notifications -from:announcements -from:newsletter -from:digest -from:billing -from:support -from:comments-noreply@docs.google.com -in:spam -in:trash
```

This filter is intentionally aggressive. False negatives from over-filtering are recoverable (the user can re-run with `--no-noise-filter` if anything important was missed); false positives bloat the candidate set and burn context.

Per-fund extension: if `pipeline_state.json` contains `excluded_domains`, append `-from:@<domain>` for each. The agent learns the fund's specific noise set over runs.

You never exfiltrate raw email content — output is structured CSV columns plus thread/event URLs for audit.

**Inclusion bias.** When in doubt, include a candidate at `low` confidence rather than dropping it. False positives are cheap (user deletes a row). False negatives are silent and unrecoverable.

---

## "In Pipeline" definition

> **In Pipeline** = a Deal Opportunity OR Pre-Opportunity that the fund has received information about or communicated with.

- **Pre-Opportunity** — a founder or team whose business is not publicly defined (pre-idea or stealth). Still belongs in pipeline if the fund has communicated with them.
- **Deal Opportunity** — has a defined business.
- **Defined Date** — for a Deal Opportunity, earliest of: (a) public website or announcement, (b) founder telling the fund what they're building, (c) appearance in PitchBook or Crunchbase. Marks the Pre-Opportunity → Deal Opportunity transition.

Do **not** apply a "seen deal" filter. Seen-deal-ness is computed downstream by Primary against PitchBook. Surface every relationship; Primary decides which intersect.

---

## Output schema — `pipeline.csv`

| Column | Required | Notes |
|---|---|---|
| `company_name` | yes | From signature/signoff/deck title. For pre-opportunity: `Founder Name (stealth)` |
| `domain` | no | Sender domain or URL in body. Null for pre-opportunity without website |
| `date` | yes | **Earliest** contact date across all merged threads (ISO `YYYY-MM-DD`) — when fund first saw it |
| `latest_contact` | yes | Most recent contact date — drives `Stale` |
| `thread_count` | yes | Threads + calendar events merged into this entry |
| `source_thread_ids` | yes | JSON array of thread IDs and `cal:<event_id>` refs |
| `stage` | yes | `deal_opportunity` \| `pre_opportunity` |
| `defined_date` | no | When entry became a Deal Opportunity, if known |
| `status` | yes | `Closed` \| `Passed` \| `Active_Diligence` \| `Met` \| `Scheduled` \| `Intro_Received` \| `Responded` \| `Sourced` \| `Stale` |
| `source` | yes | `intro` \| `inbound` \| `outbound` \| `calendar` \| `newsletter` \| `event` \| `unknown` |
| `sector` | no | Best-effort 1–3 tags |
| `hq_location` | no | From signature |
| `founder_bio` | no | One-line founder name + role + prior |
| `company_linkedin_url` | no | From body or signature |
| `description_short` | no | One-line company description |
| `source_evidence` | yes | Best thread URL + short reason |
| `confidence` | yes | `high` \| `medium` |
| `confidence_reason` | yes | Which signals fired; any contradictions |
| `needs_review` | yes | `false` for high, `true` for medium |
| `synthesized_from` | no | `slides` \| `doc` \| `pdf` \| `pptx` \| `docx` \| `inline` \| `none` — provenance when `description_short`/`sector`/`founder_bio` were filled from a read source in Phase 4b |

All deals — high, medium, **and** low confidence — go into a single `pipeline.csv`. There is no separate review-queue file. Low-confidence rows are not withheld; they carry `confidence = low` and `needs_review = true` so Primary (or you) can filter or sort on those columns. Only `excluded` rows are dropped.

---

## The five phases

### Setup

1. Parse arguments. **Default window: `2025-01-01` through today.** This skill is for retrospective capture; the user can extend or narrow easily:
   - `/pipeline-capture` → default (2025-01-01 → today)
   - `/pipeline-capture 2024-2025` → 2024-01-01 through 2025-12-31
   - `/pipeline-capture since 2024-06-01` → 2024-06-01 through today
   - `/pipeline-capture all of 2025` → 2025-01-01 through 2025-12-31
   - `/pipeline-capture 2025-01-01 2025-03-31` → explicit range (good for a first validation run)
   - Natural-language phrasings also valid; resolve to an ISO date range before scanning, then confirm with the user.
2. Detect fund domain from the user's Gmail address (whatever the MCP server reports). Confirm with user before scanning.
3. Check working directory for existing `pipeline_state.json`. If present and incomplete: resume from the last checkpoint (see **Error handling & recovery → Resume**) — announce in one line and continue **without asking**. If complete: ask whether to extend the window earlier, re-run, or abort.
4. Create `_pipeline_state/` subdirectory for intermediates. Final CSVs go to the working directory root.
5. Post a one-paragraph plan and confirm before running.

### Phase 1 — Google Calendar discovery

**Dispatch as a subagent.** Brief it to: list all calendar events in the scan window (paginate fully), filter to events with at least one non-investor non-service non-fund-domain attendee, synthesize calendar pseudo-threads, append to `_pipeline_state/candidates.jsonl`, return ≤200-word summary (event count, qualifying count, sample of 3 founder domains, anything anomalous).

Subagent should write each calendar pseudo-thread as:

```jsonl
{"thread_id": "cal:<event_id>", "source": "calendar", "passes": ["calendar"], "first_seen_date": "<event_start_date>", "attendees": ["founder@acme.com"], "subject": "<event_title>"}
```

Keep events where at least one attendee is:
- Not on the fund domain (skip internal team meetings)
- Not on a known investor domain (see seed list below)
- Not on a known service domain (lawyers, recruiters, fund admin)

### Phase 2 — Gmail keyword passes (per 6-month window)

**Dispatch as a subagent.** Brief it to: run all seven passes below, once per 6-month sub-window, append all global noise filter clauses, paginate fully (or to a hard cap of 200 threads per pass-window combo), append thread IDs to `_pipeline_state/candidates.jsonl`, return ≤200-word summary (per-pass counts, sample external sender domains, anything anomalous).

**Critical**: Gmail search is recency-biased. Split the scan window into 6-month sub-windows and run each query once per sub-window. If total scan window is <9 months, use a single sub-window.

Example for the default window (2025-01-01 → 2026-05-26, ~17 months):
- Window A: 2025-01-01 → 2025-07-01
- Window B: 2025-07-01 → 2026-01-01
- Window C: 2026-01-01 → 2026-05-26

For a wider override like `since 2024-01-01` (~29 months), you'd get 5 windows.

Run each pass below **once per sub-window**. Date filter syntax: `after:YYYY/M/D before:YYYY/M/D`. Use the MCP's max page size and paginate fully (cap 200 threads per pass-window combo).

**Every query must end with the global noise filter from the Environment section.** Add it inline as a suffix; do not skip it.

**Pass 1 — Calendar-bearing threads (strong)**
```
(from:(calendly.com OR cal.com OR savvycal.com) OR has:attachment filename:ics OR subject:invitation) after:<window_start> before:<window_end>
```

**Pass 2 — Deck links (strong)**
```
(docsend.com OR pitch.com OR notion.site OR figma.com OR drive.google.com/file) -from:<fund_domain> after:<window_start> before:<window_end>
```

**Pass 3 — Outbound founder-meeting threads (strong)**
```
from:<fund_domain> ("looking forward" OR "great meeting" OR "follow up" OR "next steps" OR deck OR pitch OR terms) after:<window_start> before:<window_end>
```

**Pass 4 — Forwarded warm intros (strong)**
```
subject:(intro OR "connecting you" OR "double opt-in" OR "wanted to introduce") after:<window_start> before:<window_end>
```

**Pass 5 — Fundraise keywords (medium)**
```
(raising OR fundraise OR fundraising OR "seed round" OR "pre-seed" OR "series A" OR SAFE OR "lead investor" OR "priced round" OR "cap table" OR valuation) after:<window_start> before:<window_end>
```

**Pass 6 — Pass/decline language (strong)**
```
("we're going to pass" OR "not a fit" OR "going to pass" OR "decided not to" OR "won't be able to" OR "not the right time" OR "good luck with the raise") after:<window_start> before:<window_end>
```

**Pass 7 — Attachment + deck filenames**
```
(filename:pdf OR filename:pptx) (deck OR pitch OR memo OR "one-pager") after:<window_start> before:<window_end>
```

After each pass, append new thread IDs to `_pipeline_state/candidates.jsonl` (dedup by `thread_id`, keep union of passes). **After each pass×window combo completes, record it in `pipeline_state.json` `completed_passes`** so a resumed run skips finished combos (re-running a combo is harmless thanks to dedup, but wasteful).

### Phase 3 — Contact-graph expansion

**Dispatch as a subagent.** Brief it to: read `_pipeline_state/candidates.jsonl`, extract contacts (3a), run domain expansion (3b) and individual-contact expansion (3c), append new threads to candidates, finalize (3d), return ≤200-word summary (domains expanded, contacts expanded, new threads found).

This is the recall multiplier — finds threads keywords miss.

**3a. Extract contacts.** Read `candidates.jsonl`. For each candidate, pull thread headers + snippets (not bodies). Extract:
- External email addresses (skip fund domain, noreply, mailer-daemon)
- External domains (skip generic providers: gmail.com, proton.me, outlook.com, yahoo.com, icloud.com, aol.com, hotmail.com, msn.com, live.com, googlemail.com)
- Names from signatures, company names from signatures/subjects

Process in batches of 25. Persist contact registry to `_pipeline_state/contacts.jsonl`.

**3b. Domain expansion.** Sort discovered non-investor non-service domains by source-thread count. Take top **80**. If more than 80, warn the user and offer to expand all (more API calls).

For each domain, query once across the **full** scan window:
```
from:@<domain> OR to:@<domain> after:<scan_start> before:<scan_end>
```

Append new threads to `candidates.jsonl` with `passes: ["expansion_domain"]`.

**3c. Individual-contact expansion.** For founders on **generic email providers** who appeared in Pass 2/4/6 threads:
```
from:<full_address> OR to:<full_address> after:<scan_start> before:<scan_end>
```

Cap at **40 individuals**. Prioritize those in Pass 4 (intros) first. Append with `passes: ["expansion_contact"]`.

**Resume tracking.** Record each domain/contact in `pipeline_state.json` (`searched_expansion_domains`, `searched_expansion_contacts`) as its search completes; a resumed run skips already-searched ones.

**3d. Finalize.** Sort `candidates.jsonl` by `first_seen_date` ascending.

### Phase 4 — Classification

**Dispatch as a subagent (or multiple subagents if candidate count > 200).** Brief each subagent to: process a contiguous chunk of candidates from `_pipeline_state/candidates.jsonl` (read by line index range), apply confidence + status + source rules from this skill, write classified rows to `_pipeline_state/classified.jsonl` (append-only), return ≤200-word summary (routing counts, any classification edge cases).

Process `candidates.jsonl` in chunks of 50. For each candidate:

1. **Gmail thread**: fetch subject, participants, dates, snippet of first + last message. Do not fetch body unless ambiguous.
2. **Calendar pseudo-thread** (`cal:` prefix): use event metadata already in candidates.
3. Apply sender classification + signal counting + confidence rules (below).
4. Determine candidate `status` (rules below) and `source` (rules below) — these will be re-derived from the merged thread set in Phase 5.
5. Extract company info.
6. Decide routing: `high` / `medium` / `low` / `excluded`.
7. Write the classified row to `_pipeline_state/classified.jsonl` (append).
8. **Drop the chunk from working memory before the next.**

**Body-fetch escalation.** Empirically, snippets + headers are sufficient for >95% of classifications. Only fetch the body of the first inbound message when classification is genuinely on the border (one medium signal + unknown sender + no contradicting noise). Budget ≤5% of threads. Never embed bodies in any output column.

**Progress.** After every chunk: `Classified 400/2189 — 28 high, 11 medium, 9 low, 352 excluded`.

### Phase 4b — Source synthesis (decks, docs, inline pitches)

**Why this phase exists.** A pre-opportunity founder often has no website, no PitchBook record, and a near-empty signature — the *only* description of what the deal is lives inside an attached deck, a linked Google Doc, or a few paragraphs of inline pitch. Without reading those, the row is just `Founder Name (stealth) — (no details found)` and the pipeline can't tell what the deal pertains to. This phase reads the source **on the VC's own machine, with the VC's own Google auth**, distills it to a few structured fields, and **discards the raw file**. Only the distilled fields ever reach `pipeline.csv`.

**Dispatch as a subagent** (after Phase 4). Brief it to: read `_pipeline_state/classified.jsonl`, select qualifying candidates, read each one's best available source, write one synthesis row per candidate to `_pipeline_state/synthesis.jsonl`, delete all temp files, return a ≤200-word summary (sources read by type, access failures, pre-opportunity rows newly described). **On (re)start, first read any existing `synthesis.jsonl` and skip candidates whose `thread_id` is already present** — a resumed Phase 4b never re-reads a deck it already synthesized. If the Google Drive connector is unavailable, skip Google-link sources and process only PDF/Office attachments and inline text; if nothing is readable, skip the phase and warn.

**Scope — which candidates get synthesized (cost control).** In priority order, until the per-run cap of **60 sources** is hit:
1. `pre_opportunity` candidates with thin/empty `description_short` — these need it most.
2. `high`/`medium` candidates with a readable source and a weak description.

Skip `excluded` rows and `low` rows that already carry a usable one-liner. `log()` how many qualifying sources were skipped by the cap.

**Source detection.** For each qualifying candidate, find the best source among its threads, richest first:
1. Google Slides — `docs.google.com/presentation/d/<id>`
2. Google Docs — `docs.google.com/document/d/<id>`
3. Drive file — `drive.google.com/file/d/<id>` (resolve mimeType)
4. PDF / `.pptx` / `.docx` **attachment** on the thread
5. Substantial inline pitch text in the first inbound message (≥ ~400 chars of founder-written prose)

**Reading each source — every path is local, zero-LibreOffice, zero-pip:**

| Source | How to read | Fidelity |
|---|---|---|
| Google Slides / Docs | Drive connector: `get_file_metadata` → read/export text. Authenticated as the VC, so email-gated files the VC can view are readable. | text |
| Drive file (PDF) | Drive connector download → `_pipeline_state/_tmp/`, then **Read tool** (Claude sees it visually) | full visual |
| Drive file (Office) | download → extract as below | text |
| PDF attachment | save to `_pipeline_state/_tmp/`, **Read tool** | full visual |
| `.docx` | `textutil -convert txt -stdout <file>` (built into macOS); if absent, python3 helper below | text |
| `.pptx` | python3 stdlib helper below — unzip + parse `ppt/slides/slideN.xml`. No `python-pptx`. | text |
| Inline | use the body text already fetched | text |

Write the helper once to `_pipeline_state/extract_office.py`:

```python
import sys, zipfile, re
from xml.etree import ElementTree as ET
path = sys.argv[1]
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}t'        # pptx text run
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t' # docx text run
z = zipfile.ZipFile(path)
def texts(xml, tag): return [e.text for e in ET.fromstring(xml).iter(tag) if e.text]
if path.endswith('.pptx'):
    slides = sorted([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)],
                    key=lambda n: int(re.search(r'(\d+)', n).group(1)))
    for i, n in enumerate(slides, 1):
        print(f"--- Slide {i} ---"); print(" ".join(texts(z.read(n), A)))
elif path.endswith('.docx'):
    print(" ".join(texts(z.read('word/document.xml'), W)))
```

Call: `python3 _pipeline_state/extract_office.py <file>`.

**Attachment-retrieval caveat.** If the Gmail connector can return attachment bytes, download to `_tmp/` and read. If it can **not** (some connector builds expose attachment *metadata* only) and the deck is not also a Drive link, set `synthesized_from: none`, note `(attachment present, not auto-readable)` in `confidence_reason`, and synthesize from inline text only — don't fail the candidate. Note: Gmail auto-converts large attachments to Drive links, so many "attachments" actually resolve to case 3 and are readable.

**Access failures.** Google file shared to a *different* address than the VC's, link expired, or permission denied → flag `(deck not accessible)` in `confidence_reason`, fall back to inline/signature, continue. Never prompt the founder or attempt to bypass an email gate.

**Synthesis — write to `_pipeline_state/synthesis.jsonl`, one row per candidate:**

```jsonl
{"thread_id": "<id>", "synthesized_from": "slides", "what_they_do": "<1–2 sentence paraphrase>", "sector": ["fintech","payments"], "stage_signal": "pre-seed", "founder_bio": "<name, role, prior>", "defined_business": true, "note": "<≤1 line, e.g. 'live pilot w/ 2 design partners'>"}
```

These map onto pipeline columns in Phase 5: `what_they_do`→`description_short`, `sector`→`sector`, `founder_bio`→`founder_bio`, `stage_signal`→`stage` hint; `defined_business: true` sets `stage = deal_opportunity` and supplies a `defined_date` signal (deck/thread date — the Pre→Deal transition); a rich synthesis may upgrade `confidence` one step.

**Privacy guardrail (hard rules):**
- All downloads go to `_pipeline_state/_tmp/`; **delete every temp file the moment its synthesis row is written** (`rm -f`). The dir must be empty when the phase ends.
- `what_they_do`, `note`, and `founder_bio` are the VC's own **paraphrase**, never transcription. Cap any verbatim quote at **≤15 words** (same rule as email bodies).
- Never write raw slide text, full deck paragraphs, speaker notes, or the file itself into `synthesis.jsonl`, any CSV column, or any persisted state.
- Result: `pipeline.csv` carries only distilled fields and is safe to share with Primary; the deck never leaves the VC's machine.

**Progress.** `Phase 4b: Synthesized 37/60 sources — 22 slides, 4 docs, 2 pdf, 9 inline; 14 pre-opportunity rows now described; 3 inaccessible.`

### Phase 5 — Aggregation, cross-thread joining, status recomputation

Stream `_pipeline_state/classified.jsonl` row by row. Build an in-memory dedup index keyed on `lower(domain)` else `lower(company_name)`.

For each merged company:
- `date` = MIN(date) across merged threads
- `latest_contact` = MAX(date)
- `thread_count` = N merged rows
- `source_thread_ids` = array of all IDs
- `confidence` = MAX(confidence)
- `defined_date` = MIN(defined_date) where non-null
- Free-text fields: prefer most descriptive non-null

**Synthesis join.** If `_pipeline_state/synthesis.jsonl` exists, index it by `thread_id`. For each merged company, gather the synthesis rows for all its `source_thread_ids` and pick the richest (most fields populated). Fill `description_short` (from `what_they_do`), `sector`, `founder_bio`, and `synthesized_from`. If any joined synthesis has `defined_business: true`, set `stage = deal_opportunity` and `defined_date = MIN(deck/thread date)`; otherwise keep `pre_opportunity`. A rich synthesis may upgrade `confidence` one step (low→medium, medium→high) and clear `needs_review` — turning a deck-only stealth founder from a thin, flagged row into a well-described high-confidence one, exactly the goal of this feature.

After merging, **recompute `status` per company from the merged thread set** using the status table below, and **recompute `source` from the earliest merged thread**.

Write a single final CSV to the working directory:
- `pipeline.csv` — **all** confidences (high + medium + low), sorted by `confidence` (high→low) then `latest_contact` descending. Low rows keep `confidence = low` / `needs_review = true` so they're easy to filter, but they are not split into a separate file.

---

## Classification rules

### Confidence

| Label | Rule | Routing |
|---|---|---|
| `high` | Multiple strong signals OR one strong signal + clear founder sender + no contradictions | `pipeline.csv`, `needs_review = false` |
| `medium` | One strong signal, OR multiple medium signals | `pipeline.csv`, `needs_review = true` |
| `low` | One medium signal, ambiguous sender, or thin evidence | `pipeline.csv`, `needs_review = true` |
| `excluded` | Matches an exclusion rule | Dropped |

**Strong signals** (any one → likely `high`):
- Calendar event held with non-investor attendee
- Outbound email from fund to founder domain referencing meeting/deck/terms/follow-up
- Inbound email with attached/linked deck (DocSend, Notion, Pitch, Drive, Figma)
- Calendly / Cal.com / Savvycal booking confirmation from founder
- Forwarded warm intro
- Explicit pass/decline from the fund

**Medium signals** (one → `medium`, two → `high`):
- Inbound founder email describing what they're building (no deck)
- Thread containing fundraise keywords ("raising", "round", "SAFE", "lead investor", etc.)
- Founder's LinkedIn URL in a fund-participated thread
- Thread surfaced only via Phase 3 expansion (sender is known-deal domain but thread has no keyword match)

**Exclusions** (force `excluded`):
- Newsletters / mass mailings (`List-Unsubscribe` header)
- Investor-to-investor co-investment chatter with no founder
- Service providers (law, recruiters, fund admin, banks)
- Cold sales outreach to the fund
- Internal fund team threads (all on fund domain)
- Recruiter / job-search threads

### Sender classification

- `founder` — non-investor domain; signature suggests founder/CEO/CTO/cofounder; or sender on a thread initiated by a known introducer
- `investor` — domain on seed list below, or in `pipeline_state.json` `excluded_domains`; investor-to-investor (no founder) → excluded
- `service` — law, recruiter, banker, accountant
- `unknown` — defaults to `low` unless a strong signal contradicts

### Status (top-down, first match wins)

**Time anchoring**: thresholds are relative to **scan window end**, not today.

| Status | Rule |
|---|---|
| `Closed` | Any merged thread: "signed", "wired", "term sheet signed", "portfolio company", "welcome to the portfolio" |
| `Passed` | Any thread contains "pass", "not a fit", "decline", "going to pass", "good luck with the raise" — from fund (not founder reporting another investor passed) |
| `Active_Diligence` | `thread_count >= 3` AND `latest_contact` within 30 days of window end AND mentions "diligence", "data room", "references", "next steps" |
| `Met` | "great meeting", "thanks for the time", "after our call", "as discussed" — OR a calendar event in the past |
| `Scheduled` | Calendar event in the future OR "looking forward to", "see you on", "confirmed for" — no meeting-held evidence |
| `Intro_Received` | Third-party intro thread exists (Pass 4 hit), no meeting evidence |
| `Responded` | `thread_count >= 2` with founder, no meeting evidence, not an intro |
| `Sourced` | Single touch — newsletter, forward, outbound, single inbound. Lowest bar |
| `Stale` | `latest_contact` > 90 days before window end AND otherwise `Responded`/`Scheduled`/`Intro_Received` |

`Closed` and `Passed` are terminal — never overridden by `Stale`.

### Source (from earliest merged thread)

| Pattern | `source` |
|---|---|
| Third party in CC on earliest message, or forwarded "Intro: …" | `intro` |
| Founder emailed fund first | `inbound` |
| Fund emailed founder first | `outbound` |
| First contact was a calendar event with no preceding email | `calendar` |
| Originated from a newsletter sender | `newsletter` |
| Mentions a specific conference / demo day / meetup as venue | `event` |
| Cannot determine | `unknown` |

### Investor-domain seed list

Treat these as `investor` classification:

```
a16z.com, accel.com, benchmark.com, bessemer.com, bvp.com, costanoa.vc,
craftventures.com, eniac.vc, firstround.com, foundercollective.com,
foundersfund.com, gc.com, generalcatalyst.com, greylock.com, gv.com,
indexventures.com, initialized.com, khoslaventures.com, kpcb.com,
lightspeedvp.com, lsvp.com, lux-capital.com, m13.co, menlovc.com, nea.com,
nfx.com, primary.vc, redpoint.com, ribbitcap.com, sequoiacap.com,
shastaventures.com, signalfire.com, slow.co, sparkcapital.com,
techstars.com, thrivecap.com, tigerglobal.com, ucan.vc, union.vc,
unusual.vc, usv.com, vy.capital, wing.vc, ycombinator.com
```

When uncertain, default to `unknown`.

---

## Dedup — cross-thread joining

One deal often spans multiple threads (intro → meeting → follow-up → pass → reconnect) plus calendar events. Aggregation (Phase 5) merges these into one row.

Dedup key: `lower(domain)` when present, else `lower(company_name)`.

Fuzzy name matches (e.g. "Acme" vs "Acme AI") are **NOT** auto-merged. Flag in `confidence_reason` and set `needs_review = true` on both.

---

## Quality + filtering pass (before writing CSVs)

1. **Orphan contacts** — records with no company name, no website, only 1 thread → keep them but flag in `description_short` as `(low confidence — single touch)`.
2. **Sparse records** — company name but no useful `description_short` → flag as `(no details found)`.
3. **Date sanity** — clip any date outside the scan window to the window boundary.
4. **Status sanity** — any `Closed` with `thread_count = 1` → downgrade to `Met` (closing a deal almost always involves multiple threads).
5. **Required columns** — verify `company_name`, `date`, `stage`, `status`, `source`, `source_evidence`, `confidence`, `confidence_reason`, `needs_review` are non-null on every row.

---

## Tone of evidence

`source_evidence` and `confidence_reason` are read by humans. Keep them concrete:

- Good: `Outbound 'looking forward to our meeting' to founder@acme.com; deck linked`
- Good: `Forwarded intro from John Doe; founder replied with Notion deck`
- Bad: `Likely a pipeline entry based on contextual signals`

Never quote more than ~10 words of raw email content.

---

## Reporting back to the user

**During the run**, post one short line per phase as it completes — not per tool call. The user wants to know progress, not internals. Prefix each line with a status marker (see **Error handling & recovery**): ✅ complete, ⚠️ completed-but-degraded, ❌ halted.

```
✅ Phase 1: Calendar scan complete — 47 events, 21 qualifying candidates.
✅ Phase 2: Gmail keyword passes complete — 134 candidates across 7 passes × 3 windows.
⚠️ Phase 3: Contact-graph expansion complete — 64 added; 4 domains skipped (rate-limited).
✅ Phase 4: Classified 219 threads — 41 high, 18 medium, 22 low, 138 excluded.
✅ Phase 4b: Synthesized 37 sources — 22 slides, 4 docs, 2 pdf, 9 inline; 14 pre-opportunity rows now described.
✅ Phase 5: Aggregating + writing CSV…
```

**After Phase 5**, post the final summary using the **absolute path** to the CSVs so the user can find them instantly:

```
Pipeline capture complete — <window>

  pipeline.csv:                 <N> entries (<H> high / <M> medium / <L> low)
  Excluded:                     <count>

Status breakdown:
  Closed: . Active_Diligence: . Met: . Scheduled: . Intro_Received: .
  Responded: . Sourced: . Passed: . Stale:

Source breakdown:
  intro: . inbound: . outbound: . calendar: . newsletter: . event: . unknown:

📂 Output files (in <ABSOLUTE_PATH>):
  pipeline.csv                ← the deliverable; share this with Primary (all confidences)
  pipeline_run_log.md         ← audit log
```

## Hand-off — make it trivial for the user to send `pipeline.csv` back to Primary

Output lives on the user's local filesystem. Primary cannot read it directly. After printing the summary, **proactively offer** the following three actions (in order, do them on demand):

1. **Reveal the file in Finder** (macOS) / **Explorer** (Windows) / **xdg-open** (Linux). On macOS:
   ```bash
   open -R "<ABSOLUTE_PATH>/pipeline.csv"
   ```
   The user sees the file highlighted in Finder and can drag/attach it anywhere.

2. **Draft an email to Primary with the CSV attached.** You have the Gmail connector enabled — use its draft-creation tool with:
   - To: `theo@primary.vc`
   - Subject: `Pipeline CSV — <fund_name or domain> — <window>`
   - Body: short 3–4 line note ("Here's my pipeline CSV for the window <start>–<end>. Total entries: N (H high / M medium). Generated by the pipeline-capture skill. Happy to walk through any flagged review-queue items.")
   - Attachment: base64-encode `pipeline.csv` and attach with `filename="pipeline-<fund_domain>-<window>.csv"` and `mimeType="text/csv"`
   - Do **not** auto-send. Always create a draft so the user reviews before hitting send.

3. **Show a preview of the top 5 entries** in `pipeline.csv` if the user wants a sanity-check before sending.

Example phrasing of the offer:

> Your CSV is at `<absolute path>`. Want me to:
> (a) reveal it in Finder,
> (b) draft an email to theo@primary.vc with the CSV attached for you to review and send, or
> (c) show you a preview of the top 5 entries first?

Pick whichever the user says, then stop. Do not push the email through without the user reviewing the draft.

Also offer to: review specific entries, adjust status calls, remove low-confidence entries, or re-scan a different range.

Do **not** expose subagent internals, raw tool results, or per-tool-call logs to the user. Those belong in `pipeline_run_log.md` for audit, not in the conversation.

---

## Error handling & recovery

This skill runs **unattended** on a VC's machine for 10–60 minutes across hundreds of connector calls. The orchestrator must never improvise its way through a failure or loop indefinitely — it follows the rules in this section. Three invariants:

1. **Bounded retries.** Any single operation (a search, thread fetch, Drive read, Bash call) retries **at most twice** with short backoff, then follows the decision table. Never debug a failure open-endedly, and never attempt a third retry.
2. **Item failures never stop the run.** A single failed thread, calendar event, or deck is skipped and logged; the phase continues. Only *phase-level* failures (auth, context exhaustion, oversized query) halt the run.
3. **One-command resume.** When the run must stop, write `pipeline_state.json`, print one plain-language line, and give the VC the single command to resume — `/pipeline-capture`. No flags, no multi-step recovery.

### Decision table — match the error, apply the response, do not reason from scratch

| Error | Response |
|---|---|
| Connector auth expired / disconnected (Gmail, Calendar, Drive) | **Halt (❌).** One line: "Reconnect `<connector>` in Settings → Connectors, then type `/pipeline-capture` to resume." |
| Rate limit / 429 from Google | Short backoff, retry ≤2. Still failing → checkpoint, pause with a ❌ resume line. |
| Single thread / event / deck fetch fails | Skip, log to `pipeline_run_log.md`, continue. Never escalate. |
| Drive file inaccessible (gated to another address, expired) | Flag `(deck not accessible)` in `confidence_reason`, fall back to inline/signature, continue. |
| Single discovery query returns >10,000 threads | **Halt (❌):** "window too wide / query too broad," suggest a narrower range. |
| `python3` / `textutil` missing | Degrade Office extraction (flag `synthesized_from: none`), continue. |
| Subagent context < ~100k tokens | Subagent writes partial state and returns; orchestrator checkpoints and asks VC to re-invoke. Do not push through. |
| Unknown / unexpected tool error | Retry ≤2. If item-level → skip. If phase-level → checkpoint + halt (❌). **Never loop indefinitely.** |

### Detection — the VC always knows the state

Every phase ends with exactly one status line:
- ✅ success — `✅ Phase 2 complete — 134 candidates.`
- ⚠️ degraded but continuing — `⚠️ Phase 3 — 4 domains skipped (rate-limited); continuing with 76.`
- ❌ halt — `❌ Phase 4 stopped — Gmail disconnected. Reconnect in Settings → Connectors, then type /pipeline-capture to resume. Progress saved (412/980 classified).`

Subagents return failures to the orchestrator; the orchestrator surfaces them as one of these three lines. Never stall silently, never bury an error inside subagent output. Full detail goes to `pipeline_run_log.md`, not the chat.

### Anti-spin guardrails (context efficiency)

- Per-phase call budgets (200 threads/pass-window, 80 domains, 40 contacts, 60 sources) are hard caps — a phase cannot balloon.
- The orchestrator does **not** fetch raw bodies, re-read large outputs, or re-plan mid-run to work around a failure. If a situation isn't covered in the decision table, it checkpoints and halts with a ❌ line rather than exploring — a clean re-invoke with fresh context solves it far more cheaply than reasoning in a depleted one.

### Resume — surviving timeouts, usage limits, and crashes

Every interruption is handled by one mechanism: durable on-disk state. This covers hitting a Claude **usage/rate limit** mid-run, a **session timeout**, **context exhaustion**, a **closed laptop**, or a **network drop**. There is no special recovery procedure — **the VC just re-runs `/pipeline-capture` (no flags), even hours later.** The skill reads `pipeline_state.json` from the working directory and continues.

**On re-invocation with incomplete state, do NOT ask questions** — announce and continue in one line:
`↻ Resuming — Phases 1–3 done, continuing Phase 4 from thread 412/980.`

**Resume granularity (where it picks up):**
- **Phase 4 (classification — the longest)** — per **50-thread chunk** (`last_classified_index`). Worst-case loss: <50 threads.
- **Phase 2 (keyword passes)** — per **pass×window combo** (`completed_passes`). Worst-case loss: the current combo.
- **Phase 3 (expansion)** — per **domain/contact** (`searched_expansion_domains` / `_contacts`). Worst-case loss: the current search.
- **Phases 1, 4b, 5** — re-run from phase start, but each is idempotent (Phase 4b skips `thread_id`s already in `synthesis.jsonl`; Phase 5 just rewrites the CSV).

**Idempotency guarantee.** Every intermediate is an append-keyed JSONL (`candidates.jsonl` and `synthesis.jsonl` keyed by `thread_id`). Re-processing an item updates in place rather than duplicating — so a resumed run **never produces duplicate rows and never double-charges a paid call**; at worst it repeats some unpaid search work.

**The one bounded risk.** If the process is killed *between* a tool call and the next checkpoint, the in-flight chunk/segment is lost and redone on resume. State is never left corrupt: write `pipeline_state.json` atomically *after* a unit completes, never mid-write.

Re-running after a *completed* run asks whether to extend the window, re-run, or abort (Setup step 3).

## Stop conditions

Stop and ask the user if:

- Required MCP connectors aren't available — tell them which to install
- Fund domain cannot be confidently inferred from the user's Gmail address
- A single discovery query returns >10,000 threads — window is too wide or query is too broad
- >30% of "founder" senders share the fund's domain — internal-thread heuristic is broken
- A single domain accounts for >5% of `high` confidence entries — likely false-positive cluster (often a portfolio company)
- Contact-graph expansion would exceed 80 domains — confirm before proceeding
- Token usage per chunk consistently exceeds 30k — working memory leak, may need smaller chunks

---

## Checkpointing

Write `pipeline_state.json` after each phase. Schema:

```json
{
  "fund_domain": "examplevc.com",
  "scan_window": {"start": "2025-01-01", "end": "2026-05-26"},
  "phase_1_complete": true,
  "phase_2_complete": true,
  "phase_3_complete": false,
  "phase_4_complete": false,
  "phase_4b_complete": false,
  "phase_5_complete": false,
  "candidate_count": 2189,
  "last_classified_index": 0,
  "calendar_event_count": 47,
  "gmail_keyword_threads": 1834,
  "expansion_domains_searched": 0,
  "expansion_contacts_searched": 0,
  "completed_passes": [],
  "searched_expansion_domains": [],
  "searched_expansion_contacts": [],
  "routing_counts": {"high": 0, "medium": 0, "low": 0, "excluded": 0},
  "sources_synthesized": 0,
  "confirmed_thread_ids": [],
  "excluded_domains": [],
  "last_processed_at": "2026-05-26T00:00:00Z"
}
```

If the user re-runs the skill and this file shows incomplete phases, resume from the first incomplete phase.

---

## Performance notes

- This skill is intentionally thorough. A 28-month scan of an active fund inbox may require 1,000–3,000 MCP calls and 15–40 minutes.
- Filesystem appends are cheap (unlike Drive). No sharding needed.
- The token guardrail matters: if context drops below 100k tokens mid-run, write state, tell the user to re-invoke, and resume cleanly.

---

## Privacy

The skill runs locally in the user's Claude Code session against their own Gmail/Calendar/Drive. Output is structured metadata + thread URLs, never raw email bodies. The intermediate `_pipeline_state/` files stay with the user. `pipeline.csv` — all confidences — is the intended deliverable to Primary; the user still reviews it (and the email draft) before it's sent.

**Deck & document synthesis (Phase 4b) never exfiltrates source content.** Linked Slides/Docs and downloaded PDF/Office files are read on the user's own machine under the user's own Google auth, distilled into a few paraphrased fields, and the raw files are deleted from `_pipeline_state/_tmp/` immediately. No slide text, deck paragraph, speaker note, or file copy is ever written to a CSV column or persisted — only the VC's paraphrase (verbatim quotes capped at ≤15 words). This is what lets a privacy-sensitive, email-gated deck inform the pipeline without the deck itself ever leaving the VC's machine or reaching Primary.
