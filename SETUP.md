# Pipeline Capture — Setup (from zero)

This guide takes you from *nothing set up* to *your recently-passed deals landing in
your private Union review queue*, where you choose what to share. Primary never touches
your inbox; nothing reaches Primary or the network until **you** approve it, and every
deal is encrypted to a key only you hold before it leaves your session.

---

## Which one should I use? (pick a path)

There are two ways to run Pipeline Capture. **Most funds should use Path A.**

- **Path A — Automated (recommended).** Set it up once on **Claude Code on the web**;
  it then runs **every day on its own in the cloud**, even with your laptop closed,
  staging new passed deals for you to review. No software to install. → **[Path A](#path-a--automated-daily-routine-claude-code-on-the-web-recommended)** below.
- **Path B — Manual.** Use **Claude Code on your desktop** and run it yourself whenever
  you want a refresh. No scheduling — nothing runs unless you start it. Choose this if
  you'd rather not connect a GitHub account, or want to run a one-off. → **[Path B](#path-b--run-it-yourself-on-desktop-manual)** below.

Both do the same thing and keep the same privacy guarantee. You can also do both — run
the daily routine *and* trigger a manual run anytime.

> **The short version of the choice:** the daily automation lives on the **web**
> (`claude.ai/code`) and needs you to attach one repository —
> **`Primary-OS/union-external-plugins`**. The manual version lives on the **desktop**
> app and needs nothing attached. Details for each below.

---

## Path A — Automated daily routine (Claude Code on the web)  *(recommended)*

**What you need**
- A **Claude account** (Pro or Max) — sign up at [claude.ai](https://claude.ai).
- **A GitHub account** — *any* account. You'll connect it so the routine can load the
  tool. You do **not** need to be invited to anything, be a collaborator, or create a
  fork — the tool's repo is public.
- Your **connection values** from Primary (your ingest URL, Union app URL, and `uig_…`
  token). Primary sends these — see *[For Primary](#for-primary-operator--issuing-a-connection-code)* at the bottom.

**Steps**
1. **Open Claude Code on the web:** go to **<https://claude.ai/code>** and sign in with
   your Claude account. When prompted, **connect a GitHub account** — any one works; it's
   only used to load the tool's public repo.
2. **Start a new routine:** go to **<https://claude.ai/code/routines>** → **New routine**.
3. **Attach the tool's repository — this is the important one.** In the routine's
   **Add repository** field, enter:
   ```
   Primary-OS/union-external-plugins
   ```
   This public repo carries the Pipeline Capture skill (at `.claude/skills/pipeline-capture/`);
   the routine loads it automatically on each run. Because it's public, any connected
   GitHub account can attach it — **no fork and no invite needed.**
4. **Fill in the rest of the routine** — the prompt to paste, the daily schedule, the
   Gmail/Calendar connectors, and the environment settings (your connection values, and
   allowing your ingest host) — by following the short copy-paste checklist in
   **[`ROUTINE_SETUP.md`](ROUTINE_SETUP.md)**.
5. **Run now** to test immediately, then let the daily schedule take over. Each run stages
   new passed deals in your Union queue; open the review link, unlock with your passphrase,
   and approve what to share.

That's the whole setup — nothing installed on your computer.

---

## Path B — Run it yourself on desktop  *(manual)*

Prefer to run it by hand, or can't connect a GitHub account? Install Claude Code on your
computer and run it on demand. (This path has **no** daily automation — it runs only when
you start it.)

### B1 — Install Claude Code  *(one-time, ~5 min)*
Pipeline Capture reads your email locally here, so you need **Claude Code** — the desktop
app or CLI (this is the *desktop* tool, **not** the web routine in Path A).
1. Go to the official install page: **<https://docs.claude.com/en/docs/claude-code>** and
   install Claude Code for your OS (the desktop app is simplest for most people).
2. Open Claude Code and **sign in** with your Claude account.
3. Confirm it works: you should land at a chat prompt where you can type commands starting with `/`.

### B2 — Add the Pipeline Capture tool  *(one-time)*
In Claude Code, run these two commands at the prompt:
```
/plugin marketplace add Primary-OS/union-external-plugins
/plugin install pipeline-capture@union-external-plugins
```
The marketplace is **public** — no GitHub account, invite, or login needed. If Claude Code
asks you to **restart** after installing, quit and reopen it. To confirm, type `/` and you
should see **`/pipeline-capture:pipeline-capture`**.

### B3 — Connect your Google account  *(one-time)*
- Open **Settings → Connectors** in Claude Code.
- Connect **Gmail**, **Google Calendar**, and **Google Drive**, signing in with **your
  fund's Google account**. Gmail + Calendar are required; Drive lets it read pitch decks.

### B4 — Connect to Union  *(one-time — needs your connection code)*
Paste this at the prompt, with your code in place of `<CODE>`:
```
Set up the pipeline-capture tool and connect me to Union with this connection code: <CODE>
```
Your token is stored locally and kept private (never emailed, never in any file you share).
It confirms with `✅ Connected to Union for <your fund>`. *(No code yet? Skip — it'll still
produce a local CSV, and you can connect later.)*

### B5 — Run it the first time
At the prompt, run:
```
/pipeline-capture:pipeline-capture
```
It does a quick 3-month test scan, shows you a sample and asks if it looks right; reply
**go** for the full scan (~30–45 min, mostly unattended — it resumes on its own if
interrupted). When done, it publishes to your private Union queue and emails you the review
link. Open it → review, exclude anything you don't want shared, and click **Share**.

### B6 — Keep it current  *(recurring)*
Whenever you want a refresh, run `/pipeline-capture:pipeline-capture sync` — it scans only
new email since your last run and stages a fresh batch to review.

---

## Troubleshooting

- **(Web) The routine can't find the skill** → confirm you attached
  `Primary-OS/union-external-plugins` and that the routine points at its **default branch**
  (see the "Skill not loading?" note in [`ROUTINE_SETUP.md`](ROUTINE_SETUP.md)).
- **(Web) Publish can't reach Union** → in the routine's **Environment → Network access**,
  set **Custom** and add your ingest host (e.g. `…supabase.co`). That host is the only
  egress the routine needs.
- **(Desktop) `/pipeline-capture:…` doesn't appear** → restart Claude Code (plugins load at startup).
- **"Connectors" empty / Google not connected** → connect + sign in with your fund's Google account.
- **"token invalid / revoked"** when publishing → ask Primary for a fresh connection code.
- **(Desktop) The run stopped partway** (laptop slept, usage limit) → run
  `/pipeline-capture:pipeline-capture` again; it resumes from where it left off.
- **Want plugin updates (desktop)** → `/plugin marketplace update union-external-plugins && /plugin update pipeline-capture@union-external-plugins`, or enable auto-update in `/plugin` settings.

---

## For Primary (operator) — issuing a connection code

Each fund gets one connection code, which carries a token scoped to **that fund only** — it
can never write to another fund's queue.

1. Mint a per-fund ingest token in the Union DB (once per fund):
   ```sql
   select create_fund_ingest_token('<Fund Name>', '<label, e.g. their laptop>');
   ```
   Copy the `uig_…` value it returns (shown once).
2. Build the connection code with the bundled helper:
   ```bash
   python3 plugins/pipeline-capture/skills/pipeline-capture/union.py mint \
     --ingest-url "https://<project>.supabase.co/functions/v1/ingest" \
     --app-url    "https://<union-app-host>" \
     --token      "uig_…" \
     --fund       "<Fund Name>"
   ```
   It prints a base64 connection code. **Send it over a secure channel** (it contains their
   token). Add `--anon-key "<anon>"` only if the deployment's function gateway requires an apikey.
3. **For a web (Path A) setup**, the VC enters the same values as environment variables
   (`UNION_INGEST_URL`, `UNION_APP_URL`, `UNION_INGEST_TOKEN`) rather than running `connect`
   — you already have those three from step 2, so send them alongside (or instead of) the
   code. See [`ROUTINE_SETUP.md`](ROUTINE_SETUP.md).
4. **Rotate / revoke:** `select revoke_fund_ingest_token('<token_id>');` then issue a fresh code.
