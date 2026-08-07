# Union External Plugins

A Claude Code plugin marketplace from Primary Venture Partners, for external VCs in the Union network. One git repo that is *both* the marketplace and the plugin host.

Currently ships:
- **pipeline-capture** — reconstruct your deal pipeline from Gmail + Google Calendar into a single `pipeline.csv` for Primary's Seen Deal Analysis (includes deck/doc synthesis for stealth deals).

> A second plugin, **domain-enrich** (fill missing company domains from Gmail), can be added here later — drop it under `plugins/domain-enrich/` and add an entry to `.claude-plugin/marketplace.json`.

---

## Install (for the VC)

**Full from-zero walkthrough — installing Claude Code, connecting Google, and your Union connection code — is in [`SETUP.md`](SETUP.md).** Start there if you don't already have Claude Code.

Short version, once Claude Code is installed and signed in (this marketplace is **public** — no GitHub account or login needed):

```
/plugin marketplace add Primary-OS/union-external-plugins
/plugin install pipeline-capture@union-external-plugins
```

Then connect **Gmail**, **Google Calendar**, and **Google Drive** in Claude Code → Settings → Connectors (sign in with your fund's Google account), paste your **connection code** from Primary when asked, and run it:

```
/pipeline-capture:pipeline-capture
```

> **Note on the command name:** plugin skills are namespaced as `plugin:skill`, so the command is `/pipeline-capture:pipeline-capture` (not bare `/pipeline-capture`). Human setup guide: [`SETUP.md`](SETUP.md); run-time choreography: [`plugins/pipeline-capture/ONBOARDING.md`](plugins/pipeline-capture/ONBOARDING.md).

## Run it automatically every day (recommended)

The steps above are the **desktop / manual** path — good for a one-off backfill. To have it run **on its own every day** (even with your laptop closed), set it up as a **scheduled cloud routine** on Claude Code for the web: open <https://claude.ai/code/routines>, attach this repo (`Primary-OS/union-external-plugins` — it's public, no fork or invite needed), and follow **[`ROUTINE_SETUP.md`](ROUTINE_SETUP.md)** for the exact prompt, schedule, connectors, and environment settings. That's the way most funds should run it.

## Updates (the reason this is a plugin)

Fixes pushed to this repo reach VCs through plugin updates. Updates are **not** automatic by default for third-party marketplaces — to get them, either:
- enable auto-update once: `/plugin marketplace add` then turn on auto-update in `/plugin` settings, **or**
- pull manually: `/plugin marketplace update union-external-plugins && /plugin update pipeline-capture@union-external-plugins`

The repo is **public**, so updates need no GitHub token or auth — enabling auto-update once, or the manual pull above, just works.

## Permissions

Plugins can't pre-grant tool permissions. On the first run, approve each tool with **"Yes, and don't ask again for this tool"** — that carries the rest of the run prompt-free. Optionally, paste the `permissions.allow` block from [`plugins/pipeline-capture/settings.allowlist.json`](plugins/pipeline-capture/settings.allowlist.json) into your `~/.claude/settings.json` to skip even the first prompts.

---

## Maintainer notes

- **Versioning:** `plugins/pipeline-capture/.claude-plugin/plugin.json` carries `version`. **Bump it on every release** or clients won't fetch the update. (Alternatively, delete the `version` field to use the git commit SHA as the version — every push then counts as a new version automatically.)
- **State:** the skill writes intermediates to `_pipeline_state/` in the *user's working directory*, not inside the plugin — so plugin updates never wipe a run in progress.
- **Validate before pushing:** `claude plugin validate ./plugins/pipeline-capture` and `claude plugin validate .`
- **Source of truth:** the canonical skill also lives at `~/.claude/skills/pipeline-capture/`. When editing, keep that and `plugins/pipeline-capture/skills/pipeline-capture/SKILL.md` in sync (or make the skills dir a symlink).
