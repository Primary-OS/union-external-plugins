# Pipeline Capture — Setup & Run

This tool reconstructs your deal pipeline from your own Gmail + Google Calendar and publishes it to your **private review queue in Union**, where you decide what to share with Primary. It runs **entirely on your machine, under your own Google login** — Primary never touches your inbox, and nothing reaches Primary or the network until you approve it in Union.

---

## For you — 3 things, then walk away

1. **Unzip** this bundle somewhere easy (e.g. your Downloads folder). *(You've probably done this already.)*
2. **Open Claude Code**, point it at the unzipped folder, and **paste this one line:**

   > Read ./pipeline-capture/ONBOARDING.md and follow the "Claude Code runbook" section to install and run the Primary pipeline-capture tool for me. Do the setup yourself — only stop to ask me to connect Google, or to confirm once before the full scan.

3. **When Claude asks, click "Connect"** for Gmail, Google Calendar, and Google Drive, and sign in with your fund's Google account. *(This is the only manual step — Google sign-in can't be automated.)*

4. **When Claude asks, paste the connection code** Primary sent you (a short string starting with letters/numbers). It links this tool to your private Union queue. *(One time only.)*

> If Claude tells you to **restart Claude Code**, quit and reopen it, then **paste the same line again** — it picks up where it left off.

That's it. Claude runs a quick 3-month test, shows you a sample, asks once before the full scan, then **publishes your pipeline to your private Union queue** and emails you the review link. The full scan is **~30–45 minutes, mostly unattended** — you can close the laptop and come back; it resumes automatically.

## What you get

Your pipeline lands in your **private review queue in Union** — one row per deal (intro → meetings → follow-ups → decks all merged), with: company/founder, what they do, sector, the date you first saw it, latest contact, stage, status (Met / Passed / Active / etc.), source, and a confidence flag. You review there, exclude anything you don't want shared, and click **Share** — only then does it reach Primary. (A local `pipeline.csv` is also kept on your machine as your own copy.)

**To pull new deals later:** just say `/pipeline-capture sync` — it scans only email since your last run and stages a fresh batch for you to review. No need to re-scan everything.

## Why this is safe (privacy)

- Runs **locally**, authenticated as you. Primary never sees your inbox.
- **Only structured rows leave** your machine — fields + links, never raw email text — and they go to *your* private queue, not to Primary. Nothing is shared until you approve it in Union.
- **Decks never leave.** Linked Slides/Docs and attached PDFs/PPTs are read locally, distilled to a one-line paraphrase, and the raw files are deleted immediately. Even email-gated decks work because it's your own session.

---
---

## Claude Code runbook

**(This section is for the assistant. Execute the steps in order. The user is non-technical — minimize questions. Only stop for: Google OAuth connects, the one go/no-go before the full run, and a restart if required. This runbook is re-entrant: on entry, detect what's already done and jump to the first incomplete step.)**

### Step 0 — Locate the bundle
You are likely running in or near the unzipped folder. Find `pipeline-capture/SKILL.md` (search downward from the working directory, then `~/Downloads`, if not in the cwd). If you genuinely can't find it, ask the user where they unzipped the bundle. Note its absolute path as `BUNDLE`.

### Step 1 — Install the skill
- Ensure `~/.claude/skills/pipeline-capture/` exists (create it).
- Copy `BUNDLE/SKILL.md`, `BUNDLE/settings.allowlist.json`, **and `BUNDLE/skills/pipeline-capture/union.py`** (the Union publish helper) into it. (`union.py` may live next to `SKILL.md` in the bundle — copy it from wherever `SKILL.md` was found.)
- If `~/.claude/skills/pipeline-capture/SKILL.md` already exists, overwrite all of them (this is an update). Don't ask — just report "updated existing install" vs "fresh install."

### Step 1b — Connect to Union (the publish destination)
- Ask the user for the **connection code** Primary sent them (one line). If they don't have one, they can still proceed — the tool falls back to producing a CSV — so don't block; just note Union publishing will be skipped.
- If they paste a code, run: `python3 ~/.claude/skills/pipeline-capture/union.py connect "<code>"`. It writes the fund's ingest URL + token to `~/.config/union/pipeline-capture.json` (token stored private, never in the repo or the CSV). Report the `✅ Connected to Union for <fund>` line back.
- This is idempotent — re-running with a new code just updates the connection.

### Step 2 — Permission allowlist (prevents hundreds of prompts during the run)
- Read `~/.claude/skills/pipeline-capture/settings.allowlist.json`.
- Merge its `permissions.allow` array into the user's `~/.claude/settings.json` (create the file as `{"permissions":{"allow":[...]}}` if absent; union the arrays if it exists; never remove existing entries).
- **The MCP server names in the allowlist (`mcp__claude_ai_Gmail`, `…Google_Calendar`, `…Google_Drive`) are best-effort.** If you can see the actual connector server names in this environment and they differ, substitute the correct ones. If you can't tell, leave them — the validation run's "don't ask again" approvals are the fallback.
- If the user is uneasy about `Bash(rm:*)`, you may drop it; the skill's temp cleanup will just prompt a few times.

### Step 3 — Verify connectors
- Check that **Gmail**, **Google Calendar**, and **Google Drive** connectors are connected. (Try a trivial read, e.g. list calendars / read profile, or inspect available tools.)
- For any that are missing or unauthorized: stop and tell the user the exact path — **Claude Code → Settings → Connectors → Connect [name] → sign in with your fund's Google account** — then **wait** for them to confirm before continuing. Gmail and Calendar are required; Drive powers deck-reading (without it, deck synthesis is skipped but the run still works).

### Step 4 — Restart gate (only if this was a fresh install this session)
Skills and permission settings are loaded at **startup**. If you installed the skill or wrote new permissions in this session, `/pipeline-capture` and the allowlist won't be active yet. Tell the user, in one line:
> Setup done. Please **quit and reopen Claude Code**, then paste the same instruction again — I'll continue from the test run.

Then stop. (On the next session you'll detect the skill is installed + connectors are up, and jump straight to Step 5.)

### Step 5 — Validation run (small, builds trust, confirms plumbing)
Run `/pipeline-capture 2025-01-01 2025-03-31`. This is a ~3-month slice — fast, and it confirms connectors + fund-domain detection before committing to the full scan. **The validation run stays local — do not publish it to Union** (it's a throwaway sample). Show the user the **top 5 rows** of `pipeline.csv` and ask one question:
> Here's a sample from Q1 2025. Does this look like your pipeline? Reply **go** to run the full 2025→today scan, or tell me what looks off.

### Step 6 — Full run
On "go," run `/pipeline-capture` (defaults to 2025-01-01 → today). Report progress as the skill does (one ✅/⚠️/❌ line per phase). Do **not** babysit or re-plan around transient errors — the skill's own "Error handling & recovery" section governs retries, skips, and resume. If it halts, relay the skill's one-line resume instruction verbatim.

### Step 7 — Deliver
When the full run completes, the skill's **Deliver** section runs `union.py publish`: if connected to Union it stages the rows in the fund's private queue, prints the review link, and emails the user that link. Relay the `✅ Staged N deals … review & approve here: <link>` line and confirm the email was sent. If the fund isn't connected to Union, the skill falls back to revealing `pipeline.csv` + drafting an email to **theo@primary.vc** (do not auto-send). Either way, **approval happens in Union, not here** — don't email the rows to Primary when connected.

### Step 8 — Recurring pulls
Tell the user, once, how to keep their pipeline current: **run `/pipeline-capture sync` whenever they want** (e.g. weekly). It scans only email since the last pull and stages a fresh batch in their Union queue to review — fast, no full re-scan. Each sync run = one new review batch.

### If anything fails
Everything is checkpointed. If the session dies, the laptop closes, or a usage limit is hit, the user just re-runs `/pipeline-capture` and it resumes from the last checkpoint — no flags, no lost work. Point them to that single command rather than troubleshooting.

---

## For Primary (operator) — issuing a connection code

Each fund gets one connection code that links their tool to **their** Union queue (a token scoped to that fund — it can only ever populate that fund's queue).

1. Mint a per-fund ingest token in the Union DB (once per fund):
   ```sql
   select create_fund_ingest_token('<Fund Name>', '<label, e.g. their laptop>');
   ```
   This returns a `uig_…` token **once** — copy it.
2. Build the connection code (no secrets are logged beyond what you paste):
   ```bash
   python3 union.py mint \
     --ingest-url "https://<project>.supabase.co/functions/v1/ingest" \
     --app-url    "https://<union-app-host>" \
     --token      "uig_…" \
     --fund       "<Fund Name>"
   ```
   It prints a base64 connection code. Send that to the fund over a secure channel; they paste it in Step 1b. (Add `--anon-key "<anon>"` only if the deployment's function gateway requires an apikey.)
3. To rotate/revoke: `select revoke_fund_ingest_token('<token_id>');` and issue a fresh code.
