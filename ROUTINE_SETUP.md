# Run pipeline-capture as a scheduled cloud routine

This sets up **pipeline-capture to run on Anthropic's cloud on a schedule** — so
your pipeline is captured, encrypted, and sent to your private Union review queue
automatically, even with your laptop closed. It runs in *your* Claude account,
under *your* Google login; Primary never touches your inbox, and every deal is
encrypted to a key only you hold before it leaves Anthropic's cloud.

The interactive version (`/pipeline-capture` in Claude Code) still works and is a
fine way to do a first full backfill. The routine is for hands-off recurring pulls.

## Before you start (once)
1. **Finish Union web onboarding and set your encryption passphrase.** The routine
   encrypts to your fund's key, which is created when you set that passphrase. If
   you skip this, the routine will report "encryption isn't set up yet."
2. Have the **connection values** Primary gave you: your ingest URL, your Union app
   URL, and your per-fund token (`uig_…`).

## Create the routine
1. Go to **claude.ai/code/routines → New routine**.
2. **Instructions (the prompt):**
   > Use the **pipeline-capture** skill in **sync** mode. Scan my Gmail and Google
   > Calendar for new deal-flow since my last run, build my pipeline, and publish
   > it to my private Union queue (it encrypts each deal to my fund's key before
   > sending). Then stop — I'll review and approve in Union myself. Do not email
   > anyone.
3. **Add repository:** select the repo that contains `.claude/skills/pipeline-capture/`
   (this one, `union-external-plugins`).
4. **Connectors:** check **Gmail** and **Google Calendar** (and **Google Drive** if
   you want deck/doc reading). Click through the Google consent screens if prompted.
5. **Trigger:** **Schedule → Daily** at a time you like (e.g. 8:00 AM).
6. **Environment** (click the cloud icon under Instructions → settings gear):
   - **Network access:** **Custom**. Under **Allowed domains** add your ingest host,
     e.g. `trjuiqcygeycenjvgovz.supabase.co`. Also tick **include default package
     managers** (so the encryption library can install).
   - **Environment variables** (`.env` format):
     ```
     UNION_INGEST_URL=https://trjuiqcygeycenjvgovz.supabase.co/functions/v1/ingest
     UNION_APP_URL=<your Union app URL>
     UNION_INGEST_TOKEN=uig_your_token_here
     ```
   - **Setup script** (optional, only if the first run errors on the crypto import):
     ```bash
     pip install pynacl || true
     ```
   - Save changes.
7. **Create**, then click **Run now** to test immediately (don't wait for the schedule).

## What a run does
Reads only *new* mail/events since your last publish (the resume point comes from
the server, so it works even though each cloud run is a fresh sandbox), reconstructs
your pipeline, **seals every deal to your public key**, and POSTs the ciphertext to
your Union queue. It prints a `REVIEW_URL` (your `/review` page). Open Union, unlock
with your passphrase, and approve what you want to share. Nothing is readable by
Primary until you approve.

## What the operator (Primary) can see
The routine reports lightweight **operational telemetry** — that a run happened,
which phase it reached, how many threads it scanned and deals it published, timing,
and any error class. This is **counts and health only**: it carries no company,
founder, or deal content, and the server literally has no column to store such a
thing. It's how Primary knows your routine is alive and working without ever seeing
what's in your pipeline. It goes to the same ingest host you already allow-listed —
nothing extra to configure.

## Notes & gotchas
- **Env-var secret:** the token is only a *publish* credential for your own fund's
  queue (it can't read anything), and it lives only in your own routine's
  environment. Still, treat it like a password — don't share the environment.
- **Skill not loading?** The skill is exposed at `.claude/skills/pipeline-capture`
  as a symlink to the plugin copy. If a run can't find the skill, copy the folder
  `plugins/pipeline-capture/skills/pipeline-capture/` to `.claude/skills/pipeline-capture/`
  as real files and re-push.
- **Cloud vs. local file reading:** deck/doc synthesis (Phase 4b) is slightly reduced
  in the cloud (no macOS `textutil`); Google Slides/Docs and PDFs still read fine.
- **First-time backfill:** for the initial multi-year scan, run the interactive
  `/pipeline-capture <start> <end>` once; let the routine handle the daily deltas.
