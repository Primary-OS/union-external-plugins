# Pipeline Capture — Setup (from zero)

This guide takes you from *nothing installed* to *your pipeline in your Union review queue*. It works whether you're following along on a call with Primary or doing it yourself. Total time **~15 minutes**, almost all of it one-time.

> **What it does:** reconstructs your deal pipeline from your own Gmail + Google Calendar **on your machine**, and publishes it to your **private review queue in Union**, where you choose what to share. Primary never touches your inbox; nothing reaches Primary or the network until *you* approve it.

---

## Before you start — what you need

- A **Mac, Windows, or Linux computer** where you read your fund's email.
- A **Claude account** (Pro or Max) — sign up at [claude.ai](https://claude.ai) if you don't have one.
- A **connection code** from Primary (a short text string). Primary generates one per fund and sends it to you — see *For Primary* at the bottom. You can install everything without it and add it at the end.
- ~15 minutes.

---

## Part 1 — Install Claude Code  *(one-time, ~5 min)*

Pipeline Capture runs **on your computer** (it reads your email locally), so you need **Claude Code** — the desktop app or CLI, **not** the web version at claude.ai.

1. Go to the official install page: **https://docs.claude.com/en/docs/claude-code** and install Claude Code for your OS (the desktop app is the simplest for most people).
2. Open Claude Code and **sign in** with your Claude account.
3. Confirm it works: you should land at a chat prompt where you can type commands starting with `/`.

*(On a call with Primary: this is the one step worth doing before the call — the download can take a few minutes.)*

---

## Part 2 — Add the Pipeline Capture tool  *(one-time)*

In Claude Code, run these two commands (type them at the prompt):

```
/plugin marketplace add Primary-OS/union-external-plugins
/plugin install pipeline-capture@union-external-plugins
```

The marketplace is **public** — no GitHub account, invite, or login needed. If Claude Code asks you to **restart** after installing, quit and reopen it.

To confirm it's installed, type `/` and you should see **`/pipeline-capture:pipeline-capture`** in the list.

---

## Part 3 — Connect your Google account  *(one-time)*

The tool reads your Gmail + Calendar through Claude Code's Google connectors, signed in as **you**.

- Open **Settings → Connectors** in Claude Code.
- Connect **Gmail**, **Google Calendar**, and **Google Drive**, signing in with **your fund's Google account**.
- This is the only step that can't be automated (Google sign-in is manual). Gmail + Calendar are required; Drive lets the tool read pitch decks (optional but recommended).

---

## Part 4 — Connect to Union  *(one-time — needs your connection code)*

This links the tool to **your** private Union queue. Paste this at the Claude Code prompt, putting your code in place of `<CODE>`:

```
Set up the pipeline-capture tool and connect me to Union with this connection code: <CODE>
```

Claude will store the connection locally (your token is kept private on your machine — never emailed, never in any file you share). It'll confirm with `✅ Connected to Union for <your fund>`.

*(No code yet? Skip this — the tool will still produce a local CSV you can send Primary, and you can connect later.)*

---

## Part 5 — Run it the first time

At the prompt, run:

```
/pipeline-capture:pipeline-capture
```

What happens:
1. A quick **3-month test scan** → Claude shows you a sample of your pipeline and asks if it looks right.
2. You reply **go** → the **full scan** runs (~30–45 min, mostly unattended — you can close the laptop and come back; it resumes on its own).
3. When it finishes, it **publishes your pipeline to your private Union queue** and **emails you the review link**.
4. Open the link → **review, exclude anything you don't want shared, and click Share.** Only then does it reach Primary.

*(If you're not connected to Union, step 3 instead produces a local `pipeline.csv` and drafts an email to Primary for you to review.)*

---

## Part 6 — Keep it current  *(recurring)*

Whenever you want to refresh (e.g. weekly), run:

```
/pipeline-capture:pipeline-capture sync
```

This scans **only new email since your last run** (fast) and stages a fresh batch in your Union queue to review. Each sync = one new batch. You'll get an email with the review link each time.

---

## Troubleshooting

- **`/pipeline-capture:...` doesn't appear** → restart Claude Code (plugins load at startup).
- **"Connectors" empty or Google not connected** → Settings → Connectors → connect + sign in with your fund's Google account.
- **"token invalid / revoked"** when publishing → ask Primary for a fresh connection code (Part 4).
- **The run stopped partway** (laptop slept, usage limit) → just run `/pipeline-capture:pipeline-capture` again; it resumes from where it left off.
- **Want updates** → `/plugin marketplace update union-external-plugins && /plugin update pipeline-capture@union-external-plugins` (or enable auto-update in `/plugin` settings).

---

## For Primary (operator) — issuing a connection code

Each fund gets one connection code, which carries a token scoped to **that fund only** — it can never write to another fund's queue.

1. Mint a per-fund ingest token in the Union DB (once per fund):
   ```sql
   select create_fund_ingest_token('<Fund Name>', '<label, e.g. their laptop>');
   ```
   Copy the `uig_…` value it returns (shown once).
2. Build the connection code with the bundled helper (in the repo, or any installed copy):
   ```bash
   python3 plugins/pipeline-capture/skills/pipeline-capture/union.py mint \
     --ingest-url "https://<project>.supabase.co/functions/v1/ingest" \
     --app-url    "https://<union-app-host>" \
     --token      "uig_…" \
     --fund       "<Fund Name>"
   ```
   It prints a base64 connection code. **Send that to the fund over a secure channel** (it contains their token). Add `--anon-key "<anon>"` only if the deployment's function gateway requires an apikey.
3. **Rotate / revoke:** `select revoke_fund_ingest_token('<token_id>');` then issue a fresh code.
