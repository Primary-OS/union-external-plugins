# Run pipeline-capture as a scheduled cloud routine

This sets up **pipeline-capture to run on Anthropic's cloud every day** — so the
deals you've recently **passed on** (and that are likely still raising) are found and
added to your private Union review queue automatically, even with your laptop closed.
It runs in *your* Claude account, under *your* Google login; Primary never touches
your inbox, and every deal is encrypted to a key only you hold before it leaves
Anthropic's cloud. You then approve which passed deals to actually share.

## Where to set it up

You can create this routine from **Claude Code on the web** or the **desktop app** —
either works, and in both you simply paste the instructions below into Claude Code. The
**web is the easiest start**, so that's the link we give you: open **<https://claude.ai/code>**
(routines live at **<https://claude.ai/code/routines>**). Whichever you use, the one thing
to get right is **attaching the tool's repository** in the routine (step 3 below) — that's
what lets the pasted instructions actually run.

## Before you start (once)
1. **Finish Union web onboarding and set your encryption passphrase.** The routine
   encrypts to your fund's key, which is created when you set that passphrase. If you
   skip this, the routine will report "encryption isn't set up yet."
2. Have the **connection values** Primary gave you: your ingest URL, your Union app
   URL, and your per-fund token (`uig_…`).
3. **A GitHub account connected to Claude Code on the web.** Any GitHub account works —
   the skill repo is **public**, so you do **not** need to be invited to it, be a
   collaborator, or fork it. You just need *some* GitHub account connected so the web
   app can attach a repository. (Connect it at <https://claude.ai/code> when prompted.)

## Create the routine
1. Go to **<https://claude.ai/code/routines>** → **New routine** (or run `/schedule`
   from the Claude Code CLI).
2. **Instructions (the prompt):**
   > Use the **pipeline-capture** skill in **sync** mode. Scan my Gmail since my last
   > run for deals I've recently **passed on** where the company is likely still
   > raising, and publish them to my private Union queue (it encrypts each deal to my
   > fund's key before sending). Include *likely* passes, not just explicit ones —
   > I'll reject any that aren't real passes when I review. Never surface deals I'm
   > still actively working. Then stop — I review and approve in Union myself. Do not
   > email anyone but me.
3. **Add repository → `Primary-OS/union-external-plugins`.** This is the public repo
   that carries the skill at `.claude/skills/pipeline-capture/`; the routine loads it
   automatically from the repo's **default branch** on each run. Paste
   `Primary-OS/union-external-plugins` (or search for it) — no fork and no collaborator
   invite are needed, because a public repo is visible to any connected GitHub account.
4. **Connectors:** check **Gmail** and **Google Calendar** (and **Google Drive** if you
   want deck/doc reading). Click through the Google consent screens if prompted.
5. **Trigger:** **Schedule → Daily** (e.g. 8:00 AM). A daily run keeps each review pile
   small and gives the routine several chances a week to complete cleanly. The window is
   cursor-driven (it scans mail since the last successful run), so a skipped or interrupted
   day is simply picked up by the next run — nothing is missed. Recommendations still go
   out to the network on their own weekly schedule, independent of how often this runs.
6. **Environment** (click the cloud icon under Instructions → settings gear):
   - **Network access → Custom.** Under **Allowed domains** add your ingest host, e.g.
     `trjuiqcygeycenjvgovz.supabase.co`. **This is the only host the routine needs** —
     publish encrypts each deal locally and POSTs the ciphertext there. You do **not**
     need to allow PyPI or any package registry: encryption runs on a bundled
     pure-Python library, so publish works with no package install and no other egress.
   - **Environment variables** (`.env` format):
     ```
     UNION_INGEST_URL=https://trjuiqcygeycenjvgovz.supabase.co/functions/v1/ingest
     UNION_APP_URL=<your Union app URL>
     UNION_INGEST_TOKEN=uig_your_token_here
     ```
   - **Setup script — optional (audited crypto only).** Publish already works without
     this. If you'd prefer the routine use the audited PyNaCl binding instead of the
     bundled pure-Python fallback, paste the contents of [`setup.sh`](setup.sh) here
     **and** tick **"Also include default list of common package managers"** under
     Network access so it can reach PyPI. If PyPI is blocked it's skipped, and the
     pure-Python fallback is used — publish still works either way.
   - Save changes.
7. **Create**, then click **Run now** to test immediately (don't wait for the schedule).

## What a run does
Reads only *new* mail since your last publish (the resume point comes from the server,
so it works even though each cloud run is a fresh sandbox), finds deals you **recently
passed on** that look like they're still raising, **seals each one to your public key**,
and POSTs the ciphertext to your Union queue. It prints a `REVIEW_URL` (your `/review`
page). Open Union, unlock with your passphrase, and approve the ones worth sharing —
**reject anything that isn't actually a pass or isn't still live.** The routine casts a
wide net on purpose (it would rather show you a maybe-pass than miss a real one), so
expect to reject some; that's the design. Nothing is readable by Primary until you approve.

## What the operator (Primary) can see
The routine reports lightweight **operational telemetry** — that a run happened, which
phase it reached, how many threads it scanned and deals it published, timing, and any
error class. This is **counts and health only**: it carries no company, founder, or deal
content, and the server literally has no column to store such a thing. It's how Primary
knows your routine is alive and working without ever seeing what's in your pipeline. It
goes to the same ingest host you already allow-listed — nothing extra to configure.

## Notes & gotchas
- **No crypto install needed.** Publish encrypts with a bundled pure-Python sealed box
  when PyNaCl isn't present, so it works even if your environment blocks PyPI. (An
  earlier version tried to `pip install pynacl` at run time and failed with a 403 when
  the environment used **Custom** network access without package managers — that failure
  mode is gone.)
- **Env-var secret:** the token is only a *publish* credential for your own fund's queue
  (it can't read anything), and it lives only in your own routine's environment. Still,
  treat it like a password — don't share the environment.
- **Skill not loading?** Cloud routines load project skills from `.claude/skills/` in the
  connected repo, but **only from the repo's *default* branch** (each run clones the
  default branch fresh). The skill must be committed to `main` as **real files** — not a
  git symlink, which isn't guaranteed to resolve after the cloud clone. If a run falls
  back to account skills, confirm the routine is pointed at
  `Primary-OS/union-external-plugins`'s default branch and that
  `.claude/skills/pipeline-capture/SKILL.md` exists there.
- **Cloud vs. local file reading:** deck/doc synthesis (Phase 2b) is slightly reduced in
  the cloud (no macOS `textutil`); Google Slides/Docs and PDFs still read fine.
- **First run:** with no cursor yet, the first run backfills the last **60 days** of
  passes (recent enough to still be live). To scan a specific earlier window once, run
  the interactive `/pipeline-capture since <date>` on desktop; then let the daily routine
  handle the deltas.
- **Expect to reject some:** the routine deliberately surfaces *likely* passes, not only
  explicit ones, so a few won't be real passes (or won't still be raising). One click to
  reject. Missing a real passed deal is the error we optimize against.
