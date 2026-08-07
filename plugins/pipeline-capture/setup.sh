#!/usr/bin/env bash
# Optional Cloud Environment setup script for the pipeline-capture routine.
#
# Paste the contents of this file into the routine's Cloud Environment → "Setup
# script" field. It runs ONCE at environment build (with network access) and the
# result is cached into the environment snapshot, so PyNaCl is preinstalled for
# every scheduled run without a per-run install.
#
# WHY (optional): union.py's `publish` step end-to-end encrypts each deal with a
# libsodium sealed box. It uses the audited PyNaCl binding when present and
# otherwise falls back to the bundled pure-Python sealed box (nacl_pure.py) — no
# pip, no network. So publish ALREADY works without this script, even when the
# sandbox blocks PyPI. This script just makes the routine prefer the audited
# binding when the environment permits it.
#
# REQUIRES: the routine's Network access = "Trusted" (PyPI is in the default
# allowlist) or "Custom" including pypi.org + files.pythonhosted.org. If PyPI is
# unreachable, the install is skipped and the pure-Python fallback is used — the
# routine still publishes.
python3 -m pip install --quiet pynacl \
  || echo "pipeline-capture setup: PyNaCl install skipped (no PyPI egress) — publish will use the bundled pure-Python fallback." >&2
# Always succeed: a missing PyNaCl is not fatal (the fallback covers it), and a
# setup script that exits non-zero fails the whole environment build.
exit 0
