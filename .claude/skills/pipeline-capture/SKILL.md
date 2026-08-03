---
name: pipeline-capture
description: Twice-weekly scan of a VC's Gmail (plus a light Google Calendar check) to surface deals the fund RECENTLY PASSED ON where the company is likely still raising a pre-seed/seed round — sealed end-to-end to the fund's OWN private Union review queue, where the manager approves what to share. Recall-biased on purpose: it flags LIKELY passes (founder pitched then the thread died, a meeting that went nowhere, a soft "keep us posted" deferral), not only explicit "we're passing" emails — the manager rejects the false positives in Union. Live deals (active back-and-forth, a future meeting, diligence in progress) and won/closed deals are never surfaced. Runs incrementally on a stored cursor; deck/doc synthesis describes stealth passes. Use when the user says "scan my passed deals", "find recent passes", "/pipeline-capture", or "/pipeline-capture sync". Default is an incremental sync; accepts an explicit date range for a first backfill (e.g. "since 2026-05-01").
argument-hint: "sync | [start-date] [end-date]"
---

# Pipeline Capture — recently-passed, still-live deals

Surface the deals a fund **recently passed on**, where the company is **plausibly still raising**, into the manager's **own end-to-end-encrypted Union queue**. The manager unlocks, reviews, and approves which of those passed deals to share back into the Union network; anything they don't approve is never readable by Primary or anyone else. This routine's whole job is to find good passed-deal candidates and hand them to the manager — nothing it produces is shared with anyone until the manager approves it in Union.

**Why "passed" and not the whole pipeline.** A fund's live and won deals are its crown jewels; it would never share those. But a deal it *passed on* costs nothing to pass along — and is genuinely useful to another fund whose thesis fits. So this routine captures **only passes**, and never a deal that's still active or already closed.

**Why "recently" and "still raising."** A pass from four years ago is dead — that company isn't raising anymore. A pass from the last few days is live: to the fund's knowledge that founder is still looking for their pre-seed/seed. The twice-weekly incremental cadence does most of this for free — each run only looks at mail since the last run, so "passed this week" is simply what it sees. The other relevance signal — whether the round has **already closed** — comes from the **email itself** during classification (see Relevance below), not from any external deal database (PitchBook and the like lag private pre-seed/seed rounds too much to trust).

**Recall over precision — this is a deliberate stance.** When a thread *might* be a pass, **include it** and let the manager reject it in Union. Missing a real passed deal is silent and unrecoverable; a false positive costs the manager one click. So this routine flags **likely** passes, not only explicit ones. Twice a week, the review pile stays small enough that a wide net is not a burden.

## What counts as in-scope (a pass) vs. out

> **In scope** = a deal the fund **passed on** (explicitly or likely) that is **not currently active** and **not closed/won**, where the counterparty looks like a **pre-seed/seed company or founder**.

**Explicit pass** — the fund told the founder no. Decline language *from the fund* (not the founder reporting someone else passed): "we're going to pass", "not a fit for us", "decided not to move forward", "won't be able to lead", "not the right time for us", "going to sit this one out", "best of luck with the raise".

**Likely pass** (the recall net — surface these for the manager to triage):
- **Pitched then died** — founder sent a deck / intro / pitch, the fund replied once or not at all, and the thread went cold with no fund follow-up.
- **Met then nowhere** — a meeting happened (past calendar event or "great meeting" thread) but there were no next steps and the thread died.
- **Soft deferral** — the fund gave a non-committal "keep us posted", "reconnect when you have more traction", "circle back after X", "not now" — and nothing followed.

**Excluded — never surface:**
- **Live / active** — recent two-way back-and-forth, a **future** calendar event, diligence in progress ("data room", "references", "term sheet", "next steps" within the recent window). If it's still moving, it is not a pass.
- **Round already closed** — the thread says the raise is **done**: "we've closed our round", "round is oversubscribed", "round is full", "completed our raise", "finished fundraising", "we're oversubscribed". A closed round can't be invested in, so there's nothing to share. **This is the only "already raised?" check** — it comes from the email, not a database. If it's *ambiguous* whether the round is closed or merely closing ("closing soon", "wrapping up the round", "final spots"), keep it as a likely pass and note the uncertainty in `pass_reason` — never drop a possibly-live deal on a misread.
- **Closed / won (by this fund)** — "signed", "wired", "welcome to the portfolio", portfolio company. That's an investment, not a pass.
- **Not a deal** — investor-to-investor chatter with no founder, service providers (legal, recruiting, banking, fund admin), newsletters / mass mail, cold sales into the fund, internal team threads.
- **Out of stage** — clearly not a pre-seed/seed company (late-stage, public, not a company).

When a thread is genuinely ambiguous between *likely pass* and *live*, and there is no active signal (no future meeting, no back-and-forth in the recent window), **lean include** as a likely pass. The manager is the precision filter.

## Environment

You run inside **Claude Code** (interactive) or an **Anthropic cloud Routine** (scheduled), with the official **Gmail** and **Google Calendar** connectors enabled, plus (optionally) **Google Drive** for deck/doc reading and a local/sandbox filesystem. Before starting:

1. Verify the connectors are connected. **Gmail** exposes search-threads / read-thread / read-profile tools; **Google Calendar** exposes list-events / read-event; **Google Drive** (only for deck/doc synthesis) exposes search / metadata / read-content. If Gmail is not connected, tell the user to enable it (Claude Code → Settings → Connectors, or the routine's Connectors panel) and stop. Calendar is used only as a light exclusion check — if absent, proceed and note it. Drive is only for deck synthesis — if absent, skip that phase with a warning.
   - **Office-file extraction is dependency-free**: `.pptx`/`.docx` via python3 stdlib (`zipfile` + `xml`); `.docx` also via macOS `textutil` when present (local installs only — not in the cloud). PDFs are read visually by the built-in Read tool. Google Slides/Docs are read through the Drive connector. No LibreOffice, no `pip install` for extraction.
2. Discover exact tool names dynamically — do not hardcode. Use whatever the active connectors expose (search / list / get patterns).
3. Intermediate files go to the working directory (or the sandbox's cwd in a routine). The deliverable is not a file — it's the sealed publish to Union (see Deliver).

## Execution model — orchestrator + subagents

**You are the orchestrator, not the worker.** Even scoped to passes, a real inbox has enough volume that running every search inline would exhaust context. So:

- The **main skill** (you) handles: argument parsing, cadence/window resolution, cursor, fund-domain detection, plan line, Phase 3 aggregation, publish, and telemetry.
- The **heavy phases** (Phase 1 pass discovery, Phase 2 classification) are dispatched as **Agent tool subagents**, each with a fresh context window; each runs its phase, writes intermediate state to disk, and returns a ≤200-word summary (counts + anomalies).
- The user sees one line per phase, not per-tool-call noise. Subagents are an implementation detail — don't mention them.

If the Agent tool is unavailable, run phases inline but warn the run may need re-invoking to finish.

## Global Gmail noise filter

Append to **every** Gmail search. Drops the mass-mail / notification noise no founder thread falls under:

```
-category:promotions -category:updates -category:forums -category:social -from:notifications@github.com -from:notifications@slack.com -from:noreply -from:no-reply -from:notify -from:notifications -from:announcements -from:newsletter -from:digest -from:billing -from:support -from:comments-noreply@docs.google.com -in:spam -in:trash
```

Per-fund extension: if `pipeline_state.json` has `excluded_domains`, append `-from:@<domain>` for each. The routine learns the fund's noise set over runs.

You never exfiltrate raw email content — the sealed payload carries structured fields (company, why-we-think-it's-a-pass, a paraphrased description), plus thread URLs for the manager's own audit. Nothing is shared with anyone until the manager approves in Union.

---

## Output — the sealed deal payload

Each surfaced pass becomes one JSON object, sealed to the fund's public key and sent to Union. Fields:

| Field | Required | Notes |
|---|---|---|
| `company_name` | yes | From signature / signoff / deck title. Stealth founder with no company: `Founder Name (stealth)` |
| `domain` | no | Sender domain or URL in body. Null for a stealth pre-company founder |
| `date_added` | yes | **Earliest** contact date across merged threads (ISO `YYYY-MM-DD`) — when the fund first saw it |
| `passed_at` | yes | Date the pass signal fired (explicit decline date, or last-contact date for a died/deferred thread) — drives recency |
| `pass_type` | yes | `explicit` \| `likely` — explicit decline vs. inferred (died / met-then-nowhere / soft-deferral) |
| `pass_reason` | yes | One concrete line: which signal fired, e.g. `Fund replied 'not a fit for us right now' on 2026-07-28` or `Founder sent deck 2026-07-25; no fund reply since` |
| `stage_signal` | no | `pre_seed` \| `seed` \| `unknown` — best guess at what they were raising |
| `sector` | no | 1–3 tags |
| `founder_bio` | no | One line: name, role, prior |
| `hq_location` | no | From signature |
| `description` | no | One-line company description (from signature/body, or Phase 2b deck synthesis) |
| `company_linkedin_url` | no | From body / signature |
| `evidence` | yes | Best thread URL + short reason (human-readable; for the manager's audit) |
| `confidence` | yes | `high` \| `medium` \| `low` — how sure we are it's a pass in scope |
| `synthesized_from` | no | `slides`\|`doc`\|`pdf`\|`pptx`\|`docx`\|`inline`\|`none` — provenance if `description`/`sector`/`founder_bio` came from a read source |

Every in-scope pass — explicit **and** likely, all confidences — is surfaced. `pass_type` and `confidence` let the manager triage fast (and let Union sort). Only excluded rows are dropped.

---

## The phases

### Setup

1. **Resolve cadence + window.** Locate the bundled helper (works for a plugin or a `~/.claude/skills/` install):
   ```bash
   UNION_PY=$(find ~/.claude . "$PWD" -name union.py -path '*pipeline-capture*' 2>/dev/null | head -1)
   ```
   - **`sync` (the default, and what the twice-weekly routine runs):** read the cursor with `python3 "$UNION_PY" cursor`; set the start date to that value **minus a 4-day overlap buffer** (twice-weekly runs are ~3–4 days apart; re-staging an overlapping day is harmless — Union dedups on approve) and the end date to today. If the cursor is empty (first run ever), fall back to a **90-day backfill** (start = today − 90d) so the first run captures the recent passes that are still live, without dredging up years of dead ones. State the resolved window in one line.
   - **Explicit range** (`/pipeline-capture since 2026-05-01`, `/pipeline-capture 2026-05-01 2026-07-01`): use it verbatim — for a deliberate one-off backfill. Resolve natural language to ISO dates and confirm.
2. **Detect fund domain** from the user's Gmail address (whatever the connector reports). Confirm before scanning (interactive) / assume it (routine).
3. **Resume check.** If `pipeline_state.json` exists and is incomplete, resume from the last checkpoint and announce in one line — do not ask. If complete, this is a fresh run.
4. Create `_pipeline_state/` for intermediates.
5. **Emit `run_started` telemetry** (see Operational telemetry) and post a one-line plan.

### Phase 1 — Pass discovery (Gmail)

**Dispatch as a subagent.** Brief it to run the passes below across the window (split into 6-month sub-windows only if the window exceeds 9 months — a sync window never will; a backfill might), append the global noise filter to every query, paginate to a cap of 200 threads per pass, append thread IDs to `_pipeline_state/candidates.jsonl` (dedup by `thread_id`), and return a ≤200-word summary (per-pass counts, sample external domains, anomalies).

Date filter syntax: `after:YYYY/M/D before:YYYY/M/D`.

**Pass A — Explicit decline from the fund (strongest).**
```
from:<fund_domain> ("going to pass" OR "we're passing" OR "decided to pass" OR "not a fit" OR "not the right fit" OR "not the right time" OR "won't be able to" OR "won't be leading" OR "decided not to" OR "going to sit this one out" OR "not moving forward" OR "good luck with the raise" OR "best of luck with your raise") after:<window_start> before:<window_end>
```

**Pass B — Inbound pitches / decks (candidate passes if they then died).**
```
(docsend.com OR pitch.com OR notion.site OR figma.com OR "drive.google.com/file" OR deck OR "pitch deck" OR "our deck" OR "raising" OR "pre-seed" OR "pre seed" OR "seed round" OR SAFE) -from:<fund_domain> after:<window_start> before:<window_end>
```

**Pass C — Warm intros to founders (candidate passes if they went nowhere).**
```
subject:(intro OR "connecting you" OR "double opt-in" OR "wanted to introduce") after:<window_start> before:<window_end>
```

**Pass D — Soft deferrals from the fund.**
```
from:<fund_domain> ("keep us posted" OR "keep me posted" OR "reconnect when" OR "circle back" OR "when you have more traction" OR "a bit early for us" OR "too early for us" OR "let's stay in touch" OR "reach back out") after:<window_start> before:<window_end>
```

Passes A and D are direct pass signals. Passes B and C surface **candidate** deals whose pass-ness is decided in Phase 2 (did the thread die, or is it still live?). After each pass, append to `candidates.jsonl` and record the pass in `pipeline_state.json` `completed_passes` so a resume skips it.

*(No contact-graph expansion and no calendar discovery here — those were full-pipeline recall multipliers that would drag in active, non-passed relationships. Calendar is used only as an exclusion check in Phase 2.)*

### Phase 2 — Classification (is it an in-scope pass?)

**Dispatch as a subagent** (or several if candidates > 200). Brief each to process a contiguous chunk of `candidates.jsonl`, apply the rules below, write in-scope passes to `_pipeline_state/classified.jsonl` (append-only), and return a ≤200-word summary (explicit/likely/excluded counts, edge cases).

Process in chunks of 50. For each candidate:

1. **Fetch** the thread's subject, participants, dates, and a snippet of the first + last message (fetch the body only when genuinely on the border — budget ≤5% of threads; never store bodies).
2. **Exclude first** — drop the candidate if any of:
   - **Live:** the last message in the thread is recent (within the window) and the fund is still engaging; OR there is a **future** calendar event with the counterparty (light Calendar check by attendee/domain); OR active-diligence language ("data room", "references", "term sheet", "next steps") with recent activity.
   - **Round closed:** the thread indicates the raise is complete — "closed our round", "oversubscribed", "round is full", "completed/finished our raise". (Ambiguous "closing soon" / "wrapping up" → do **not** exclude; keep as a likely pass and note it in `pass_reason`.) This is the relevance check for "have they already raised?" — read it from the email, never a database.
   - **Won:** "signed", "wired", "welcome to the portfolio", portfolio-company signal.
   - **Not a deal:** investor-to-investor with no founder, service provider, newsletter (`List-Unsubscribe`), cold sales into the fund, internal (all fund-domain) thread.
   - **Out of stage:** clearly not a pre-seed/seed company.
3. **Otherwise classify the pass:**
   - `pass_type = explicit` if Pass-A decline language from the fund is present.
   - `pass_type = likely` if: inbound pitch/deck (Pass B) with **no fund follow-up** and the thread has gone quiet; OR an intro (Pass C) that got a non-committal or no reply and died; OR a Pass-D soft deferral with nothing after it; OR a past meeting with no next steps.
4. **Confidence:** `high` = explicit decline, or a clear died-after-pitch with a real company. `medium` = a solid likely-pass signal. `low` = thin/ambiguous but no active signal (still surface — manager triages).
5. **Extract** company info (name, domain, stage signal, sector, founder bio, description, LinkedIn) from signature/snippet.
6. Write the classified pass to `classified.jsonl`. Drop the chunk from memory before the next.

**Progress:** `Phase 2: classified 240 candidates — 31 explicit, 44 likely, 165 excluded`.

### Phase 2b — Source synthesis (decks, docs, inline pitches)

**Why.** A recently-passed pre-seed founder often has no website and a near-empty signature — the only description of what they're building lives in an attached deck or a linked Doc. Without it the row is `Founder Name (stealth) — (no details)` and a receiving fund can't tell what the deal is. This phase reads the source **on the VC's own machine/sandbox under the VC's own Google auth**, distills a few fields, and **discards the raw file** — only the paraphrase is ever sealed.

**Dispatch as a subagent** after Phase 2. Brief it to read `classified.jsonl`, select qualifying passes, read each one's best source, write one synthesis row per candidate to `_pipeline_state/synthesis.jsonl`, delete all temp files, and return a ≤200-word summary. On restart, skip `thread_id`s already in `synthesis.jsonl`. If Drive is unavailable, process only PDF/Office attachments and inline text; if nothing is readable, skip and warn.

**Scope (cost control), until a per-run cap of 40 sources:** priority (1) stealth / thin-description passes that need it most, then (2) passes with a readable source and a weak description. Skip passes that already carry a usable one-liner. Log how many qualifying sources the cap skipped.

**Source detection** (richest first): Google Slides (`docs.google.com/presentation/d/<id>`), Google Docs (`docs.google.com/document/d/<id>`), Drive file (`drive.google.com/file/d/<id>`), PDF/`.pptx`/`.docx` attachment, then ≥~400 chars of inline founder prose.

**Reading each source — every path is local/sandbox, zero-LibreOffice, zero-pip:**

| Source | How to read | Fidelity |
|---|---|---|
| Google Slides / Docs | Drive connector: metadata → read/export text. Authenticated as the VC, so files the VC can view are readable. | text |
| Drive file (PDF) | Drive download → `_pipeline_state/_tmp/`, then **Read tool** (visual) | full visual |
| Drive file (Office) | download → extract as below | text |
| PDF attachment | save to `_tmp/`, **Read tool** | full visual |
| `.pptx` / `.docx` | python3 stdlib helper below (`textutil` for `.docx` on local macOS only) | text |
| Inline | body text already fetched | text |

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

**Privacy guardrail (hard rules):**
- All downloads go to `_pipeline_state/_tmp/`; **delete each temp file the moment its synthesis row is written** (`rm -f`). The dir must be empty when the phase ends.
- `description`, `note`, and `founder_bio` are the VC's own **paraphrase**, never transcription. Any verbatim quote ≤15 words.
- Never write raw slide text, deck paragraphs, speaker notes, or the file itself into any persisted state. Only distilled fields are sealed.

**Progress:** `Phase 2b: synthesized 22/28 sources — 14 slides, 3 docs, 2 pdf, 3 inline; 9 stealth passes now described; 2 inaccessible`.

### Phase 3 — Aggregate + build the payload

Stream `classified.jsonl`, dedup on `lower(domain)` else `lower(company_name)` (do **not** auto-merge fuzzy names like "Acme" vs "Acme AI" — flag both). For each merged company:
- `date_added` = MIN(date); `passed_at` = MAX(pass-signal date); `confidence` = MAX; `pass_type` = `explicit` if any merged thread was explicit else `likely`.
- Join `synthesis.jsonl` by `thread_id`; fill `description`, `sector`, `founder_bio`, `stage_signal`, `synthesized_from` from the richest synthesis.
- `pass_reason` / `evidence`: the most concrete signal + best thread URL.

Write one row per merged company to `pipeline.csv` in the working directory, with columns matching the payload schema above (`company_name, domain, date_added, passed_at, pass_type, pass_reason, stage_signal, sector, founder_bio, hq_location, description, company_linkedin_url, evidence, confidence, synthesized_from`). `union.py publish` reads this CSV and seals each row to the fund's key. Then run Deliver.

---

## Relevance ("is the company still raising?")

Two gauges, both decided **here in the email scan** — no external deal database:

1. **Recency** — supplied by the twice-weekly cadence. Each run only sees mail since the last, so a surfaced pass is a recent one.
2. **Round not yet closed** — the only trustworthy signal that a company has finished raising is **the email saying so** (PitchBook and other databases lag private pre-seed/seed rounds too much to rely on). During classification, read the thread for a round-closed signal and **exclude** those (a closed round can't be invested in — nothing to share). When it's genuinely ambiguous ("closing soon", "final spots"), keep it as a likely pass and say so in `pass_reason`; don't drop a possibly-live deal on a misread.

That's the whole relevance model: **recent, and not yet closed.** Everything else about whether the company is a good fit is the receiving fund's judgment, downstream in Union.

---

## Deliver — seal and publish to Union (the only destination)

The only destination is the fund's **private, end-to-end-encrypted Union queue**. `union.py publish` seals **every deal to the fund's own public key** (a libsodium sealed box) before anything leaves the machine, so Primary and anyone with database access see only ciphertext. The passes become readable only when the manager unlocks with their passphrase in Union and approves them. **There is no CSV-to-Primary path and no email-to-anyone path** — the manager's approval is the only gate through which a deal ever becomes visible.

```bash
python3 "$UNION_PY" publish --run-id "$RUN_ID" --sync   # drop --sync on an explicit-range backfill
```

(Run from the working directory so it finds the payload, or pass the path. First run auto-installs PyNaCl for the encryption — one-time. `--run-id` lets the auto-emitted `run_completed` telemetry correlate with `run_started`.) Then branch on the exit code:

- **Exit 0 (published).** stdout carries `REVIEW_URL:` and `STORED:`. Tell the user in one line: `✅ Sealed & sent <STORED> passed-deal candidates to your private Union queue — only you can read them. Unlock with your passphrase to triage & approve: <REVIEW_URL>`. Then **send the VC a self-notification email** (Gmail connector, **to the user's own address from the connector profile**, never anyone else) — Subject `Union: <STORED> passed deals to review`, body one line + the `REVIEW_URL` — so they're reminded after the routine's session closes. Sending to self is fine to send directly.
- **Exit 3 (NOT_CONNECTED).** No Union connection configured. In a routine this is a setup error — report it (the env vars aren't set). Do **not** fall back to any other destination.
- **Exit 4 (rejected) / 5 (unreachable) / 6 (crypto unavailable).** Relay the one-line reason. Exit 4 + 404 = the VC hasn't set their encryption passphrase in Union onboarding yet (tell them to). 401 = token invalid/revoked (ask Primary to re-issue the connection code). 5/6 = offer to retry; the candidates are not lost (re-run picks them up via the cursor overlap).

Do **not** expose subagent internals or per-tool logs to the user — those go to `pipeline_run_log.md` for audit.

---

## Operational telemetry (routine runs)

So the operator (Primary) can see *that* a fund's routine ran and how much it moved — never *what* moved — emit run events via `union.py`. **Metadata only** (counts, timing, phase, error class); no company, founder, or deal content, and the server drops any field outside its fixed set. Always **best-effort**: a telemetry failure must never fail, slow, or block a capture. Skip it entirely if not connected to Union.

Generate one `RUN_ID` at the start (e.g. `run-<something-unique>`) and reuse it so start/complete/fail correlate.

- **At run start** (after resolving the window, only when connected):
  ```bash
  python3 "$UNION_PY" telemetry run_started --run-id "$RUN_ID" --mode sync --window-start <start> --window-end <end> || true
  ```
- **On any halt:** `python3 "$UNION_PY" telemetry run_failed --run-id "$RUN_ID" --phase <phase> --error "<one-line class>" || true`
- **On success:** you emit nothing — `union.py publish` auto-emits `run_completed` with the count. Pass it the same `--run-id`.
- **On a clean run with zero passes to publish** (nothing sealed — so `publish` isn't called, or exits with "no rows"): emit a terminal event yourself so the operator sees a clean finish rather than a run that looks hung — `python3 "$UNION_PY" telemetry run_completed --run-id "$RUN_ID" --deals-published 0 || true`. (An empty `union.py publish` already does this, so it's harmless if both fire.)

Always append `|| true` so a telemetry call can never break the run.

---

## Error handling & recovery

Runs **unattended** (interactive or cloud) across hundreds of connector calls. Never improvise through a failure or loop indefinitely. Invariants:

1. **Bounded retries.** Any single operation retries **at most twice** with short backoff, then follows the decision table. Never a third retry.
2. **Item failures never stop the run.** A single failed thread / event / deck is skipped and logged; the phase continues. Only *phase-level* failures (auth, context exhaustion) halt.
3. **One-command resume.** On a halt, write `pipeline_state.json`, print one plain line, give the single resume command — `/pipeline-capture` (or, in a routine, the next scheduled run resumes automatically via the cursor).
4. **Emit `run_failed` telemetry on any halt** (phase + one-line error class). Best-effort; halt regardless.

### Decision table

| Error | Response |
|---|---|
| Connector auth expired / disconnected (Gmail, Calendar, Drive) | **Halt (❌).** One line: "Reconnect `<connector>`, then re-run." |
| Rate limit / 429 from Google | Short backoff, retry ≤2. Still failing → checkpoint, halt with a ❌ resume line. |
| Single thread / event / deck fetch fails | Skip, log to `pipeline_run_log.md`, continue. |
| Drive file inaccessible (gated to another address, expired) | Flag `(deck not accessible)` in `pass_reason`, fall back to inline/signature, continue. |
| Single discovery query returns >10,000 threads | **Halt (❌):** window too wide; suggest a narrower range (a sync window should never do this). |
| `python3` / `textutil` missing | Degrade Office extraction (`synthesized_from: none`), continue. |
| Subagent context < ~100k tokens | Subagent writes partial state and returns; orchestrator checkpoints and re-invokes. |
| Unknown / unexpected tool error | Retry ≤2. Item-level → skip. Phase-level → checkpoint + halt (❌). Never loop. |

Every phase ends with exactly one status line: ✅ success, ⚠️ degraded-but-continuing, or ❌ halt (with the resume line and saved progress).

### Resume

Durable on-disk state covers usage limits, timeouts, context exhaustion, a closed laptop, a network drop. Re-running `/pipeline-capture` (or the next scheduled routine run) reads `pipeline_state.json` and continues — **no flags, no questions**. Announce in one line: `↻ Resuming — Phase 1 done, continuing Phase 2 from candidate 240/610`. Intermediates are append-keyed JSONL (keyed by `thread_id`), so a resumed run never duplicates rows and never double-charges a paid call; at worst it repeats some unpaid search work. Write `pipeline_state.json` atomically *after* a unit completes.

## Checkpointing

Write `pipeline_state.json` after each phase:

```json
{
  "fund_domain": "examplevc.com",
  "mode": "sync",
  "scan_window": {"start": "2026-07-26", "end": "2026-07-30"},
  "phase_1_complete": true,
  "phase_2_complete": false,
  "phase_2b_complete": false,
  "phase_3_complete": false,
  "candidate_count": 0,
  "last_classified_index": 0,
  "completed_passes": [],
  "counts": {"explicit": 0, "likely": 0, "excluded": 0},
  "sources_synthesized": 0,
  "excluded_domains": [],
  "last_processed_at": "2026-07-30T00:00:00Z"
}
```

## Investor-domain seed list (for the exclusion / sender check)

Treat these as `investor` (investor-to-investor with no founder → excluded):

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

## Privacy

Runs against the VC's own Gmail/Calendar/Drive under the VC's own auth. The sealed payload carries structured, paraphrased fields + thread URLs — never raw email bodies. Intermediate `_pipeline_state/` files stay on the VC's machine/sandbox. **Every deal is sealed to the fund's own key before it leaves; nothing is readable by Primary or anyone else until the manager approves it in Union.** Deck/doc synthesis reads sources locally, distills to a paraphrase, and deletes the raw file immediately — the deck itself never leaves the VC's machine.
