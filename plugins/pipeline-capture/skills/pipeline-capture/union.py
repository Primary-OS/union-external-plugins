#!/usr/bin/env python3
"""union.py — connect the pipeline-capture skill to a fund's Union queue.

Ships next to SKILL.md. Whether the skill was installed as a plugin or copied to
~/.claude/skills/, find this file's absolute path with:
    find ~/.claude -name union.py -path '*pipeline-capture*' 2>/dev/null | head -1
then invoke it as `python3 <that path> <subcommand>`.

Bundled with the pipeline-capture skill. python3 stdlib, plus PyNaCl for the
`publish` step (auto-installed on first use) — publish end-to-end encrypts every
deal so Primary can't read anything you haven't approved. Subcommands:

  connect <code>     Decode a base64 connection code (issued by Primary) and write
                     the local config. Run once during setup.
  publish [csv]      Encrypt each row in pipeline.csv to the fund's public key
                     (sealed box) and POST the ciphertexts to Union's queue. The
                     plaintext never leaves this machine. Prints the review URL +
                     stored count, and advances the incremental cursor.
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

# Bump with the plugin version — reported in telemetry so Primary can see which
# funds are running which build without touching any deal content.
VERSION = "1.4.1"

# pipeline.csv column -> sealed payload field. This is the passed-deal schema
# (see SKILL.md "Output — the sealed deal payload"): each row is one deal the fund
# passed on, and pass_type / pass_reason / passed_at let the manager triage it in
# Union. Everything here is sealed to the fund's key before it leaves the machine.
FIELD_MAP = {
    # Founder anchor — at least one of these is required per row (see the publish
    # gate below and SKILL.md "Founder anchor"). Union keys the shared deal on the
    # founder, so these ride at the front of the payload.
    "founder_linkedin_url": "founder_linkedin_url",
    "founder_email": "founder_email",
    "company_name": "company_name",
    "domain": "domain",
    "date_added": "date_added",
    "passed_at": "passed_at",
    "pass_type": "pass_type",
    "pass_reason": "pass_reason",
    "stage_signal": "stage_signal",
    "sector": "sector",
    "founder_bio": "founder_bio",
    "hq_location": "hq_location",
}
PROVENANCE_MAP = {
    "confidence": "confidence",
    "evidence": "evidence",
    "synthesized_from": "synthesized_from",
    "description": "description",
    "company_linkedin_url": "company_linkedin_url",
}


def _load_config():
    cfg = {}
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    # Environment overrides — lets a scheduled cloud routine supply the connection
    # as secrets/env vars, with no interactive `connect` step. Env wins over file.
    env_map = {
        "UNION_INGEST_URL": "ingest_url",
        "UNION_APP_URL": "app_url",
        "UNION_INGEST_TOKEN": "token",
        "UNION_ANON_KEY": "anon_key",
        "UNION_FUND_NAME": "fund_name",
    }
    for env_key, cfg_key in env_map.items():
        v = os.environ.get(env_key)
        if v:
            cfg[cfg_key] = v.rstrip("/") if cfg_key.endswith("url") else v
    return cfg or None


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
    # Local cursor first (interactive installs persist it across runs).
    if cfg and cfg.get("last_pulled_at"):
        print(cfg["last_pulled_at"])
        return 0
    # Stateless fallback for scheduled cloud routines (fresh sandbox each run, no
    # local state): ask the server for the last publish time and resume from its
    # date. Best-effort — silence on any failure means "no cursor → full run".
    if cfg and cfg.get("token") and cfg.get("ingest_url"):
        try:
            req = urllib.request.Request(cfg["ingest_url"], headers=_ingest_headers(cfg), method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                last = json.loads(resp.read().decode("utf-8")).get("last_submission_at")
            if last:
                print(last[:10])  # YYYY-MM-DD
        except Exception:
            pass
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


def _ensure_nacl():
    """Import PyNaCl (audited libsodium binding); pip-install it once if missing.
    Publish end-to-end encrypts with a sealed box, so we use real crypto — never
    a hand-rolled implementation."""
    try:
        from nacl.public import PublicKey, SealedBox  # noqa: F401
        return True
    except ImportError:
        import subprocess
        print("Installing PyNaCl (one-time, for encrypted publish)…", file=sys.stderr)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pynacl"], check=True)
            from nacl.public import PublicKey, SealedBox  # noqa: F401
            return True
        except Exception as e:
            print(f"❌ Could not install PyNaCl ({e}). Run: {sys.executable} -m pip install pynacl", file=sys.stderr)
            return False


def _ingest_headers(cfg):
    headers = {"x-ingest-token": cfg["token"]}
    # Some Supabase gateways require an apikey even when the function disables JWT
    # verification — include it if the connection code carried one.
    if cfg.get("anon_key"):
        headers["apikey"] = cfg["anon_key"]
        headers["Authorization"] = f"Bearer {cfg['anon_key']}"
    return headers


def _emit_telemetry(cfg, event, fields=None):
    """POST a run event to /ingest/telemetry. Metadata only — never deal content.
    Best-effort: a telemetry failure must never fail or slow a real capture, so we
    swallow every error. Returns True on success (used by the CLI for exit codes)."""
    if not cfg or not cfg.get("token") or not cfg.get("ingest_url"):
        return False
    body = {"event": event, "plugin_version": VERSION}
    for k, v in (fields or {}).items():
        if v is not None:
            body[k] = v
    url = cfg["ingest_url"].rstrip("/") + "/telemetry"
    headers = {**_ingest_headers(cfg), "Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30):
            return True
    except Exception:
        return False


def cmd_telemetry(args):
    """Explicit telemetry event (the skill calls this at run start and on failure).
    Never errors out the routine — always exits 0."""
    cfg = _load_config()
    fields = {
        "run_id": args.run_id,
        "phase": args.phase,
        "status": args.status,
        "mode": args.mode,
        "threads_scanned": args.threads_scanned,
        "candidates_found": args.candidates_found,
        "deals_published": args.deals_published,
        "sources_synthesized": args.sources_synthesized,
        "window_start": args.window_start,
        "window_end": args.window_end,
        "duration_ms": args.duration_ms,
        "error": args.error,
    }
    _emit_telemetry(cfg, args.event, fields)
    return 0


def _get_public_key(cfg):
    """GET the fund's public key from the ingest endpoint (base64 X25519)."""
    req = urllib.request.Request(cfg["ingest_url"], headers=_ingest_headers(cfg), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["public_key"]


def _seal(pubkey_b64, payload):
    """Seal a deal to the fund's public key (libsodium crypto_box_seal). Returns
    standard base64 — matches what the browser decrypts."""
    from nacl.public import PublicKey, SealedBox
    box = SealedBox(PublicKey(base64.b64decode(pubkey_b64)))
    ct = box.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return base64.b64encode(ct).decode("ascii")


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
            # Admission = a founder anchor (LinkedIn URL or email), NOT a company
            # name. A stealth / pre-company founder is a first-class shareable row;
            # an anchorless row can't be identified or matched, so it's dropped.
            if payload.get("founder_linkedin_url") or payload.get("founder_email"):
                rows.append(payload)

    if not rows:
        print("⚠️  No rows to publish (empty pipeline.csv).", file=sys.stderr)
        # A legitimately empty run still *completed* — emit a terminal event with a
        # zero count so the operator can tell "ran, found nothing" apart from
        # "crashed mid-run" (which shows only run_started).
        _emit_telemetry(cfg, "run_completed", {
            "run_id": args.run_id,
            "mode": "sync" if args.sync else None,
            "deals_published": 0,
        })
        return 1

    if not _ensure_nacl():
        return 6

    # 1. Fetch the fund's public key. Only the public key is needed to encrypt —
    #    no secret ever lives in this routine.
    try:
        public_key = _get_public_key(cfg)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        if e.code == 404:
            print("❌ Encryption isn't set up for your fund yet. Open Union, set your "
                  "passphrase in onboarding, then re-run publish.", file=sys.stderr)
        elif e.code == 401:
            print("❌ Token invalid or revoked — ask Primary to re-issue your connection code.", file=sys.stderr)
        else:
            print(f"❌ Could not fetch your fund key (HTTP {e.code}): {detail}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"❌ Could not reach Union ({e}). pipeline.csv is kept locally — retry later.", file=sys.stderr)
        return 5

    # 2. Seal every deal to the public key. Plaintext never leaves this machine.
    ciphertexts = [_seal(public_key, payload) for payload in rows]

    # 3. POST the ciphertexts (batched to the endpoint's per-call cap).
    headers = {**_ingest_headers(cfg), "Content-Type": "application/json"}
    stored = 0
    BATCH = 2000
    for i in range(0, len(ciphertexts), BATCH):
        chunk = ciphertexts[i:i + BATCH]
        body = json.dumps({"source": "email-agent", "ciphertexts": chunk}).encode("utf-8")
        req = urllib.request.Request(cfg["ingest_url"], data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            stored += int(result.get("stored", 0))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            print(f"❌ Union rejected the upload (HTTP {e.code}): {detail}", file=sys.stderr)
            if e.code == 401:
                print("   The token is invalid or revoked — ask Primary to re-issue your connection code.", file=sys.stderr)
            return 4
        except Exception as e:
            print(f"❌ Could not reach Union ({e}). pipeline.csv is kept locally — retry later.", file=sys.stderr)
            return 5

    review_url = f"{cfg['app_url']}/review"

    # Advance the incremental cursor only on a successful publish.
    cfg["last_pulled_at"] = date.today().isoformat()
    _save_config(cfg)

    # Operational telemetry — record the successful publish (count only, no
    # content). Best-effort; never blocks the return. run_id (if the skill passed
    # one via --run-id) links this to the run_started event.
    _emit_telemetry(cfg, "run_completed", {
        "run_id": args.run_id,
        "mode": "sync" if args.sync else None,
        "deals_published": stored,
    })

    print(f"✅ Encrypted and sent {stored} deal(s) to your Union queue. Only you can read them.")
    print(f"   Unlock with your passphrase to review and choose what to share:")
    print(f"REVIEW_URL: {review_url}")
    print(f"STORED: {stored}")
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
    pub = sub.add_parser("publish")
    pub.add_argument("csv", nargs="?")
    pub.add_argument("--run-id", dest="run_id", default=None)
    pub.add_argument("--sync", action="store_true")
    pub.set_defaults(fn=cmd_publish)

    # telemetry: metadata-only run event; emitted by the skill at start/failure.
    t = sub.add_parser("telemetry")
    t.add_argument("event", choices=["run_started", "run_completed", "run_failed", "heartbeat"])
    t.add_argument("--run-id", dest="run_id", default=None)
    t.add_argument("--phase", default=None)
    t.add_argument("--status", default=None)
    t.add_argument("--mode", default=None)
    t.add_argument("--threads-scanned", dest="threads_scanned", type=int, default=None)
    t.add_argument("--candidates-found", dest="candidates_found", type=int, default=None)
    t.add_argument("--deals-published", dest="deals_published", type=int, default=None)
    t.add_argument("--sources-synthesized", dest="sources_synthesized", type=int, default=None)
    t.add_argument("--window-start", dest="window_start", default=None)
    t.add_argument("--window-end", dest="window_end", default=None)
    t.add_argument("--duration-ms", dest="duration_ms", type=int, default=None)
    t.add_argument("--error", default=None)
    t.set_defaults(fn=cmd_telemetry)

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
