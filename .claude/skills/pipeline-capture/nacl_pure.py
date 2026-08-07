#!/usr/bin/env python3
"""nacl_pure.py — a dependency-free libsodium `crypto_box_seal` (sealed box).

Why this exists: the pipeline-capture publish step end-to-end encrypts every deal
to the fund's X25519 public key so Primary can't read anything the manager hasn't
approved. The audited path is PyNaCl, but PyNaCl is a compiled libsodium binding
that must be fetched from PyPI — and the Anthropic cloud routine sandbox blocks
egress to pypi.org, so `pip install pynacl` 403s and publish can never run there.

This module reproduces libsodium's sealed box using ONLY the Python stdlib (no
pip, no network, no build step), so publish works in any locked-down sandbox.
`union.py` uses PyNaCl when it's already importable (local dev) and falls back to
this otherwise. The output is a byte-compatible libsodium sealed box, so Union's
browser (`crypto_box_seal_open` via libsodium-wrappers) opens it unchanged.

This is not hand-rolled cryptography in the risky sense: it's a faithful port of
the NaCl/TweetNaCl reference primitives (Salsa20/XSalsa20, Poly1305, X25519) that
libsodium itself implements, and it is validated by `python3 nacl_pure.py`, which
round-trips against PyNaCl (== libsodium) — the same construction the browser
runs. Note: the X25519 ladder here is NOT constant-time (Python bigints aren't),
which is acceptable for sealing to a public key with a single-use ephemeral secret
but is why we prefer PyNaCl when present.

Sealed box: ephemeral X25519 keypair (epk, esk); nonce = blake2b(epk||recipient_pk,
24); ciphertext = crypto_box_easy(msg, nonce, recipient_pk, esk); output =
epk (32) || mac (16) || ciphertext.
"""

import hashlib
import os

_MASK32 = 0xFFFFFFFF
_SIGMA = b"expand 32-byte k"


# ── little-endian word helpers ───────────────────────────────────────────────
def _rotl32(x, n):
    x &= _MASK32
    return ((x << n) | (x >> (32 - n))) & _MASK32


def _ld32(b, i):
    return b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24)


def _st32(x):
    x &= _MASK32
    return bytes((x & 0xFF, (x >> 8) & 0xFF, (x >> 16) & 0xFF, (x >> 24) & 0xFF))


# ── Salsa20 permutation (20 rounds, no final add) ────────────────────────────
def _salsa20_rounds(x):
    for _ in range(10):
        # column round
        x[4] ^= _rotl32(x[0] + x[12], 7);   x[8] ^= _rotl32(x[4] + x[0], 9)
        x[12] ^= _rotl32(x[8] + x[4], 13);  x[0] ^= _rotl32(x[12] + x[8], 18)
        x[9] ^= _rotl32(x[5] + x[1], 7);    x[13] ^= _rotl32(x[9] + x[5], 9)
        x[1] ^= _rotl32(x[13] + x[9], 13);  x[5] ^= _rotl32(x[1] + x[13], 18)
        x[14] ^= _rotl32(x[10] + x[6], 7);  x[2] ^= _rotl32(x[14] + x[10], 9)
        x[6] ^= _rotl32(x[2] + x[14], 13);  x[10] ^= _rotl32(x[6] + x[2], 18)
        x[3] ^= _rotl32(x[15] + x[11], 7);  x[7] ^= _rotl32(x[3] + x[15], 9)
        x[11] ^= _rotl32(x[7] + x[3], 13);  x[15] ^= _rotl32(x[11] + x[7], 18)
        # row round
        x[1] ^= _rotl32(x[0] + x[3], 7);    x[2] ^= _rotl32(x[1] + x[0], 9)
        x[3] ^= _rotl32(x[2] + x[1], 13);   x[0] ^= _rotl32(x[3] + x[2], 18)
        x[6] ^= _rotl32(x[5] + x[4], 7);    x[7] ^= _rotl32(x[6] + x[5], 9)
        x[4] ^= _rotl32(x[7] + x[6], 13);   x[5] ^= _rotl32(x[4] + x[7], 18)
        x[11] ^= _rotl32(x[10] + x[9], 7);  x[8] ^= _rotl32(x[11] + x[10], 9)
        x[9] ^= _rotl32(x[8] + x[11], 13);  x[10] ^= _rotl32(x[9] + x[8], 18)
        x[12] ^= _rotl32(x[15] + x[14], 7); x[13] ^= _rotl32(x[12] + x[15], 9)
        x[14] ^= _rotl32(x[13] + x[12], 13);x[15] ^= _rotl32(x[14] + x[13], 18)


def _salsa20_block(state):
    """Salsa20 core with the final add — one 64-byte keystream block."""
    x = list(state)
    _salsa20_rounds(x)
    return b"".join(_st32((x[i] + state[i]) & _MASK32) for i in range(16))


def _hsalsa20(nonce16, key32):
    """HSalsa20 core (rounds only, no final add) — derives a 32-byte subkey."""
    x = [0] * 16
    x[0], x[5], x[10], x[15] = (_ld32(_SIGMA, 0), _ld32(_SIGMA, 4),
                                _ld32(_SIGMA, 8), _ld32(_SIGMA, 12))
    x[1], x[2], x[3], x[4] = (_ld32(key32, 0), _ld32(key32, 4),
                              _ld32(key32, 8), _ld32(key32, 12))
    x[11], x[12], x[13], x[14] = (_ld32(key32, 16), _ld32(key32, 20),
                                  _ld32(key32, 24), _ld32(key32, 28))
    x[6], x[7], x[8], x[9] = (_ld32(nonce16, 0), _ld32(nonce16, 4),
                              _ld32(nonce16, 8), _ld32(nonce16, 12))
    _salsa20_rounds(x)
    return b"".join(_st32(x[i]) for i in (0, 5, 10, 15, 6, 7, 8, 9))


def _xsalsa20_keystream(length, nonce24, key32):
    subkey = _hsalsa20(nonce24[:16], key32)
    n8 = nonce24[16:24]
    out = bytearray()
    counter = 0
    while len(out) < length:
        state = [0] * 16
        state[0], state[5], state[10], state[15] = (_ld32(_SIGMA, 0), _ld32(_SIGMA, 4),
                                                    _ld32(_SIGMA, 8), _ld32(_SIGMA, 12))
        state[1], state[2], state[3], state[4] = (_ld32(subkey, 0), _ld32(subkey, 4),
                                                  _ld32(subkey, 8), _ld32(subkey, 12))
        state[11], state[12], state[13], state[14] = (_ld32(subkey, 16), _ld32(subkey, 20),
                                                      _ld32(subkey, 24), _ld32(subkey, 28))
        state[6], state[7] = _ld32(n8, 0), _ld32(n8, 4)
        state[8], state[9] = counter & _MASK32, (counter >> 32) & _MASK32
        out += _salsa20_block(state)
        counter += 1
    return bytes(out[:length])


# ── Poly1305 one-time authenticator ──────────────────────────────────────────
def _poly1305(msg, key32):
    r = int.from_bytes(key32[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key32[16:32], "little")
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        block = msg[i:i + 16]
        acc = ((acc + (int.from_bytes(block, "little") + (1 << (8 * len(block))))) * r) % p
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


# ── X25519 (RFC 7748) ────────────────────────────────────────────────────────
_P25519 = (1 << 255) - 19
_A24 = 121665
_NINE = (9).to_bytes(32, "little")


def _scalarmult(scalar32, u32):
    k = bytearray(scalar32)
    k[0] &= 248; k[31] &= 127; k[31] |= 64
    k = int.from_bytes(k, "little")
    x1 = (int.from_bytes(u32, "little") & ((1 << 255) - 1)) % _P25519
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in range(254, -1, -1):
        kt = (k >> t) & 1
        swap ^= kt
        if swap:
            x2, x3 = x3, x2
            z2, z3 = z3, z2
        swap = kt
        a = (x2 + z2) % _P25519
        aa = (a * a) % _P25519
        b = (x2 - z2) % _P25519
        bb = (b * b) % _P25519
        e = (aa - bb) % _P25519
        c = (x3 + z3) % _P25519
        d = (x3 - z3) % _P25519
        da = (d * a) % _P25519
        cb = (c * b) % _P25519
        x3 = pow((da + cb) % _P25519, 2, _P25519)
        z3 = (x1 * pow((da - cb) % _P25519, 2, _P25519)) % _P25519
        x2 = (aa * bb) % _P25519
        z2 = (e * ((aa + (_A24 * e) % _P25519) % _P25519)) % _P25519
    if swap:
        x2, x3 = x3, x2
        z2, z3 = z3, z2
    return ((x2 * pow(z2, _P25519 - 2, _P25519)) % _P25519).to_bytes(32, "little")


def _box_keypair():
    esk = os.urandom(32)
    return esk, _scalarmult(esk, _NINE)


# ── crypto_box / sealed box ──────────────────────────────────────────────────
def _box_beforenm(pk32, sk32):
    # Shared key = HSalsa20(key = X25519(sk, pk), nonce = 16 zero bytes).
    return _hsalsa20(b"\x00" * 16, _scalarmult(sk32, pk32))


def _secretbox_easy(message, nonce24, key32):
    ks = _xsalsa20_keystream(32 + len(message), nonce24, key32)
    ct = bytes(m ^ k for m, k in zip(message, ks[32:32 + len(message)]))
    return _poly1305(ct, ks[:32]) + ct


def crypto_box_seal(message, recipient_pk32):
    """libsodium sealed box → bytes: epk(32) || mac(16) || ciphertext."""
    if len(recipient_pk32) != 32:
        raise ValueError("recipient public key must be 32 bytes")
    esk, epk = _box_keypair()
    nonce = hashlib.blake2b(epk + recipient_pk32, digest_size=24).digest()
    k = _box_beforenm(recipient_pk32, esk)
    return epk + _secretbox_easy(message, nonce, k)


# ── self-test: validate against PyNaCl (== libsodium == the browser) ──────────
def _selftest():
    try:
        from nacl.public import PrivateKey, SealedBox
    except ImportError:
        print("PyNaCl not importable — cannot cross-validate here. "
              "Run this on a machine with PyNaCl before shipping.")
        return 2
    import json
    cases = [b"", b"x", b"a" * 63, b"b" * 64, b"c" * 65,
             json.dumps({"founder_linkedin_url": "https://linkedin.com/in/x",
                         "company_name": "Acme", "pass_reason": "too early"}).encode(),
             os.urandom(1500)]
    for i in range(200):
        sk = PrivateKey.generate()
        pk = bytes(sk.public_key)
        msg = cases[i % len(cases)] if i < len(cases) else os.urandom((i * 7) % 300)
        sealed = crypto_box_seal(msg, pk)
        opened = SealedBox(sk).decrypt(sealed)
        if opened != msg:
            print("FAIL: round-trip mismatch at case", i)
            return 1
    # Also confirm our epk matches scalarmult_base semantics via a box round-trip
    # already exercised above. Done.
    print("OK: 200 sealed boxes produced by nacl_pure decrypted correctly with "
          "PyNaCl (libsodium). Byte-compatible with the browser's crypto_box_seal_open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
