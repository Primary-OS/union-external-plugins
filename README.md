# Union External Plugins

A Claude Code plugin marketplace from Primary Venture Partners, for external VCs in the Union network. One git repo that is *both* the marketplace and the plugin host.

Currently ships:
- **pipeline-capture** — reconstruct your deal pipeline from Gmail + Google Calendar into a single `pipeline.csv` for Primary's Seen Deal Analysis (includes deck/doc synthesis for stealth deals).

> A second plugin, **domain-enrich** (fill missing company domains from Gmail), can be added here later — drop it under `plugins/domain-enrich/` and add an entry to `.claude-plugin/marketplace.json`.

---

## Install (for the VC)

**This repo is private.** Before the commands below, you must (1) accept the GitHub invite to this repo (you're added as an outside collaborator — you get *only* this repo, nothing else in the org), and (2) have git authenticated on your machine (`gh auth login`, macOS Keychain, or an SSH key). Without that, `marketplace add` can't clone the repo.

```
/plugin marketplace add <owner>/<repo>        # e.g. Primary-OS/union-external-plugins  (fill in once hosted)
/plugin install pipeline-capture@union-external-plugins
```

Then connect **Gmail**, **Google Calendar**, and **Google Drive** in Claude Code → Settings → Connectors (sign in with your fund's Google account), and run it:

```
/pipeline-capture:pipeline-capture
```

> **Note on the command name:** plugin skills are namespaced as `plugin:skill`, so the command is `/pipeline-capture:pipeline-capture` (not bare `/pipeline-capture`). The full run guide is in [`plugins/pipeline-capture/ONBOARDING.md`](plugins/pipeline-capture/ONBOARDING.md).

## Updates (the reason this is a plugin)

Fixes pushed to this repo reach VCs through plugin updates. Updates are **not** automatic by default for third-party marketplaces — to get them, either:
- enable auto-update once: `/plugin marketplace add` then turn on auto-update in `/plugin` settings, **or**
- pull manually: `/plugin marketplace update union-external-plugins && /plugin update pipeline-capture@union-external-plugins`

Because this repo is **private**, auto-update at launch needs a git token in the environment *before* Claude Code starts (`GITHUB_TOKEN` or `GH_TOKEN`). Set it with `printf '%s'`, never `echo` (a trailing newline silently breaks token auth). **If the token isn't set, auto-update silently no-ops and the VC drifts onto an old version** — so for hands-off updates this token step is required, not optional. Otherwise, updates must be pulled manually (which still needs interactive git auth).

## Permissions

Plugins can't pre-grant tool permissions. On the first run, approve each tool with **"Yes, and don't ask again for this tool"** — that carries the rest of the run prompt-free. Optionally, paste the `permissions.allow` block from [`plugins/pipeline-capture/settings.allowlist.json`](plugins/pipeline-capture/settings.allowlist.json) into your `~/.claude/settings.json` to skip even the first prompts.

---

## Maintainer notes

- **Versioning:** `plugins/pipeline-capture/.claude-plugin/plugin.json` carries `version`. **Bump it on every release** or clients won't fetch the update. (Alternatively, delete the `version` field to use the git commit SHA as the version — every push then counts as a new version automatically.)
- **State:** the skill writes intermediates to `_pipeline_state/` in the *user's working directory*, not inside the plugin — so plugin updates never wipe a run in progress.
- **Validate before pushing:** `claude plugin validate ./plugins/pipeline-capture` and `claude plugin validate .`
- **Source of truth:** the canonical skill also lives at `~/.claude/skills/pipeline-capture/`. When editing, keep that and `plugins/pipeline-capture/skills/pipeline-capture/SKILL.md` in sync (or make the skills dir a symlink).
