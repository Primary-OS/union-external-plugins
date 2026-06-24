#!/usr/bin/env python3
"""union.py — connect the pipeline-capture skill to a fund's Union queue.

Ships next to SKILL.md. Whether the skill was installed as a plugin or copied to
~/.claude/skills/, find this file's absolute path with:
    find ~/.claude -name union.py -path '*pipeline-capture*' 2>/dev/null | head -1
then invoke it as `python3 <that path> <subcommand>`.

Bundled with the pipeline-capture skill. Pure python3 stdlib (no pip). Subcommands:

  connect <code>     Decode a base64 connection code (issued by Primary) and write
                     the local config. Run once during setup.
  publish [csv]      POST the rows in pipeline.csv to the fund's Union quarantine
                     queue (default destination). Prints staged/flagged counts +
                     the review URL, and advances the incremental cursor.
  cursor             Print the last successful pull date (YYYY-MM-DD) or nothing.
                     The skill uses this to scan only new email on a `sync` run.
  mint ...           Operator-only: build a connection code from a fund's
                     ingest URL / app URL / token. (Primary runs this, not the VC.)

Config lives at ~/.config/union/pipeline-capture.json and holds the ingest URL,
the Union app URL, the per-fund token (secret — never logged in full, never put
in the CSV or the plugin repo), and the cursor. Nothing here ever sends raw email
— only the structured pipeline rows the skill already produced.
"""

import argparse
import base64
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

CONFIG_DIR = os.path.expanduser("~/.config/union")
CONFIG_PATH = os.path.join(CONFIG_DIR, "pipeline-capture.json")

# pipeline.csv column -> §7.1 ingest field. Provenance columns (confidence,
# evidence, etc.) ride along in the row and surface in Union's row-detail drawer.
FIELD_MAP = {
    "company_name": "company_name",
    "domain": "domain",
    "date": "date_added",
    "defined_date": "defined_at",
    "status": "status",
    "sector": "sector",
    "founder_bio": "founder_bio",
    "hq_location": "hq_location",
}
PROVENANCE_MAP = {
    "confidence": "confidence",
    "confidence_reason": "confidence_reason",
    "source_evidence": "evidence",
    "synthesized_from": "synthesized_from",
    "description_short": "description",
}


def _load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Write with user-only perms — the token is a secret.
    fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)


def _mask(token):
    return token[:8] + "…" + token[-4:] if token and len(token) > 14 else "set"


def cmd_connect(args):
    try:
        raw = base64.b64decode(args.code.strip()).decode("utf-8")
        incoming = json.loads(raw)
    except Exception as e:
        print(f"❌ Invalid connection code ({e}). Ask Primary to re-issue it.", file=sys.stderr)
        return 2
    required = ("ingest_url", "app_url", "token")
    missing = [k for k in required if not incoming.get(k)]
    if missing:
        print(f"❌ Connection code missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    cfg = _load_config() or {}
    cfg.update({
        "ingest_url": incoming["ingest_url"].rstrip("/"),
        "app_url": incoming["app_url"].rstrip("/"),
        "token": incoming["token"],
        "fund_name": incoming.get("fund_name"),
    })
    if incoming.get("anon_key"):
        cfg["anon_key"] = incoming["anon_key"]
    cfg.setdefault("last_pulled_at", None)
    _save_config(cfg)
    fund = cfg.get("fund_name") or "your fund"
    print(f"✅ Connected to Union for {fund}. Token {_mask(cfg['token'])} stored at {CONFIG_PATH}.")
    return 0


def cmd_cursor(args):
    cfg = _load_config()
    if cfg and cfg.get("last_pulled_at"):
        print(cfg["last_pulled_at"])
    return 0


def _row_to_payload(row):
    out = {}
    for col, field in FIELD_MAP.items():
        v = (row.get(col) or "").strip()
        if v:
            out[field] = v
    for col, field in PROVENANCE_MAP.items():
        v = (row.get(col) or "").strip()
        if v:
            out[field] = v
    return out


def cmd_publish(args):
    cfg = _load_config()
    if not cfg or not cfg.get("token"):
        print("NOT_CONNECTED: no Union connection configured.", file=sys.stderr)
        return 3

    csv_path = args.csv or "pipeline.csv"
    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} not found.", file=sys.stderr)
        return 2

    rows = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            status = (r.get("status") or "").strip().lower()
            if status == "excluded":
                continue
            payload = _row_to_payload(r)
            if payload.get("company_name"):
                rows.append(payload)

    if not rows:
        print("⚠️  No rows to publish (empty pipeline.csv).", file=sys.stderr)
        return 1

    body = json.dumps({"source": "email-agent", "rows": rows}).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-ingest-token": cfg["token"]}
    # Some Supabase gateways require an apikey even when the function disables JWT
    # verification — include it if the connection code carried one.
    if cfg.get("anon_key"):
        headers["apikey"] = cfg["anon_key"]
        headers["Authorization"] = f"Bearer {cfg['anon_key']}"

    req = urllib.request.Request(cfg["ingest_url"], data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        print(f"❌ Union rejected the upload (HTTP {e.code}): {detail}", file=sys.stderr)
        if e.code == 401:
            print("   The token is invalid or revoked — ask Primary to re-issue your connection code.", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"❌ Could not reach Union ({e}). pipeline.csv is kept locally — retry later.", file=sys.stderr)
        return 5

    staged = result.get("staged", 0)
    flagged = result.get("flagged", 0)
    import_id = result.get("import_id", "")
    review_url = f"{cfg['app_url']}/contribute/review/{import_id}" if import_id else cfg["app_url"]

    # Advance the incremental cursor only on a successful publish.
    cfg["last_pulled_at"] = date.today().isoformat()
    cfg["last_import_id"] = import_id
    _save_config(cfg)

    print(f"✅ Staged {staged} deal(s) in your Union queue" + (f" ({flagged} need a look)" if flagged else "") + ".")
    print(f"REVIEW_URL: {review_url}")
    print(f"STAGED: {staged}")
    print(f"FLAGGED: {flagged}")
    return 0


def cmd_mint(args):
    payload = {
        "ingest_url": args.ingest_url.rstrip("/"),
        "app_url": args.app_url.rstrip("/"),
        "token": args.token,
    }
    if args.fund:
        payload["fund_name"] = args.fund
    if args.anon_key:
        payload["anon_key"] = args.anon_key
    code = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    print(code)
    return 0


def main():
    p = argparse.ArgumentParser(prog="union.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("connect"); c.add_argument("code"); c.set_defaults(fn=cmd_connect)
    sub.add_parser("cursor").set_defaults(fn=cmd_cursor)
    pub = sub.add_parser("publish"); pub.add_argument("csv", nargs="?"); pub.set_defaults(fn=cmd_publish)

    m = sub.add_parser("mint")
    m.add_argument("--ingest-url", dest="ingest_url", required=True)
    m.add_argument("--app-url", dest="app_url", required=True)
    m.add_argument("--token", required=True)
    m.add_argument("--fund", default=None)
    m.add_argument("--anon-key", dest="anon_key", default=None)
    m.set_defaults(fn=cmd_mint)

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
