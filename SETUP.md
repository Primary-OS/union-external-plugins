# Pipeline Capture — Setup (from zero)

This takes you from *nothing set up* to *your recently-passed deals landing in your private
Union review queue*, where you choose what to share. Primary never touches your inbox;
nothing reaches Primary or the network until **you** approve it, and every deal is encrypted
to a key only you hold before it leaves your session.

Setup is the same wherever you run Claude Code: **open Claude Code, attach one repository,
and paste the setup instructions.** The one thing not to miss is **which repository to
attach** — that's what lets the instructions run.

---

## What you need
- A **Claude account** (Pro or Max) — sign up at [claude.ai](https://claude.ai).
- **A GitHub account** — *any* account. You'll use it to attach the tool's repository. The
  repo is **public**, so you do **not** need to be invited to it, be a collaborator, or fork it.
- Your **connection values** from Primary (your ingest URL, Union app URL, and `uig_…` token).
  Primary sends these — see *[For Primary](#for-primary-operator--issuing-a-connection-code)* below.

---

## Set it up

1. **Open Claude Code.** The easiest way is the web app: **<https://claude.ai/code>**. Sign
   in with your Claude account, and connect a GitHub account when prompted (any account —
   it's only used to load the tool). *(The desktop app works exactly the same way if you
   prefer it.)*

2. **Attach the tool's repository — don't skip this.** When the routine asks for a
   repository, attach:
   ```
   Primary-OS/union-external-plugins
   ```
   This public repo carries the Pipeline Capture tool; attaching it is what makes the
   instructions in the next step work. Because it's public, any connected GitHub account can
   attach it — **no fork and no invite needed.**

3. **Create the routine (paste the instructions).** Follow the short copy-paste checklist in
   **[`ROUTINE_SETUP.md`](ROUTINE_SETUP.md)** — it has the exact instruction block to paste,
   the daily schedule, the Gmail/Calendar connectors to enable, and where your connection
   values go. Then click **Run now** to test.

4. **Review in Union.** Each run stages your new passed deals in your private queue and gives
   you a review link. Open it, unlock with your passphrase, and approve the ones worth sharing —
   nothing is readable by Primary until you do.

That's it. From then on it runs on its own on the schedule you set.

> ### Which repository do I attach?
> **`Primary-OS/union-external-plugins`** — it's public, so any connected GitHub account can
> attach it (no fork, no invite). This is the single step people miss; get it right and the
> pasted instructions just work.

---

## Troubleshooting

- **It can't find the tool / falls back to a generic answer** → confirm you attached
  `Primary-OS/union-external-plugins`, and that the routine points at its **default branch**
  (see "Skill not loading?" in [`ROUTINE_SETUP.md`](ROUTINE_SETUP.md)).
- **Publish can't reach Union** → in the routine's **Environment → Network access**, set
  **Custom** and add your ingest host (e.g. `…supabase.co`). That host is the only egress the
  routine needs.
- **Google not connected** → enable the **Gmail** and **Google Calendar** connectors on the
  routine, signed in with your fund's Google account (Drive optional, for decks).
- **"token invalid / revoked"** when publishing → ask Primary for a fresh connection code.

---

## For Primary (operator) — issuing a connection code

Each fund gets one connection code, which carries a token scoped to **that fund only** — it
can never write to another fund's queue.

1. Mint a per-fund ingest token in the Union DB (once per fund):
   ```sql
   select create_fund_ingest_token('<Fund Name>', '<label, e.g. their fund>');
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
   It prints a base64 connection code. Add `--anon-key "<anon>"` only if the deployment's
   function gateway requires an apikey.
3. **Send the VC their values over a secure channel.** For the routine, they enter these as
   environment variables (`UNION_INGEST_URL`, `UNION_APP_URL`, `UNION_INGEST_TOKEN`) — you
   already have all three from step 2, so send them directly (the base64 code just bundles the
   same values). See [`ROUTINE_SETUP.md`](ROUTINE_SETUP.md).
4. **Rotate / revoke:** `select revoke_fund_ingest_token('<token_id>');` then issue a fresh code.
