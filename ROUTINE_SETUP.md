# Run pipeline-capture as a scheduled cloud routine

This sets up **pipeline-capture to run on Anthropic's cloud once a week** — so the
deals you've recently **passed on** (and that are likely still raising) are found and
added to your private Union review queue automatically, even with your laptop closed. It runs in *your* Claude account, under *your* Google login; Primary
never touches your inbox, and every deal is encrypted to a key only you hold before
it leaves Anthropic's cloud. You then approve which passed deals to actually share.

The interactive version (`/pipeline-capture since <date>` in Claude Code) still works
and is a fine way to do a first backfill of recent passes. The routine is for
hands-off recurring pulls.

## Before you start (once)
1. **Finish Union web onboarding and set your encryption passphrase.** The routine
   encrypts to your fund's key, which is created when you set that passphrase. If
   you skip this, the routine will report "encryption isn't set up yet."
2. Have the **connection values** Primary gave you: your ingest URL, your Union app
   URL, and your per-fund token (`uig_…`).

## Create the routine
1. Go to **claude.ai/code/routines → New routine**.
2. **Instructions (the prompt):**
   > Use the **pipeline-capture** skill in **sync** mode. Scan my Gmail since my last
   > run for deals I've recently **passed on** where the company is likely still
   > raising, and publish them to my private Union queue (it encrypts each deal to my
   > fund's key before sending). Include *likely* passes, not just explicit ones —
   > I'll reject any that aren't real passes when I review. Never surface deals I'm
   > still actively working. Then stop — I review and approve in Union myself. Do not
   > email anyone but me.
3. **Add repository:** select the repo that contains `.claude/skills/pipeline-capture/`
   (this one, `union-external-plugins`).
4. **Connectors:** check **Gmail** and **Google Calendar** (and **Google Drive** if
   you want deck/doc reading). Click through the Google consent screens if prompted.
5. **Trigger:** **Schedule → Weekly** (e.g. Monday, 8:00 AM). A weekly run keeps each
   review pile small while still catching passes while they're fresh — don't set it to
   daily. The window is cursor-driven (it scans mail since the last run), so the cadence
   just sets how large each review batch is, not what the net catches.
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
Reads only *new* mail since your last publish (the resume point comes from the
server, so it works even though each cloud run is a fresh sandbox), finds deals you
**recently passed on** that look like they're still raising, **seals each one to
your public key**, and POSTs the ciphertext to your Union queue. It prints a
`REVIEW_URL` (your `/review` page). Open Union, unlock with your passphrase, and
approve the ones worth sharing — **reject anything that isn't actually a pass or
isn't still live.** The routine casts a wide net on purpose (it would rather show
you a maybe-pass than miss a real one), so expect to reject some; that's the design.
Nothing is readable by Primary until you approve.

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
- **Skill not loading?** Cloud routines load project skills from `.claude/skills/`
  in the connected repo, but **only from the repo's *default* branch** (each run
  clones the default branch fresh). So the skill must be committed to `main`
  (it is), as **real files** — not a git symlink, which isn't guaranteed to resolve
  after the cloud clone. If a run still falls back to account skills, confirm the
  routine is pointed at this repo's default branch and that
  `.claude/skills/pipeline-capture/SKILL.md` exists there.
- **Cloud vs. local file reading:** deck/doc synthesis (Phase 2b) is slightly reduced
  in the cloud (no macOS `textutil`); Google Slides/Docs and PDFs still read fine.
- **First run:** with no cursor yet, the first run backfills the last **60 days** of
  passes (recent enough to still be live). To scan a specific earlier window once, run
  the interactive `/pipeline-capture since <date>`; then let the weekly routine
  handle the deltas.
- **Expect to reject some:** the routine deliberately surfaces *likely* passes, not
  only explicit ones, so a few won't be real passes (or won't still be raising). One
  click to reject. Missing a real passed deal is the error we optimize against.
