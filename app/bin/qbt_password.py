#!/usr/bin/env python3
"""
qBittorrent Password Hash Generator

Generates PBKDF2-HMAC-SHA512 password hash compatible with qBittorrent's format.
qBittorrent stores passwords in qBittorrent.conf as:
  WebUI\\Password_PBKDF2=@ByteArray(base64_salt:base64_hash)

Usage:
  echo '<password>' | python3 qbt_password.py          # Generate hash (stdin, secure)
  python3 qbt_password.py <password>                    # Generate hash (argv, visible in ps)
  python3 qbt_password.py --check <password> <hash>     # Verify password

Algorithm (matching qBittorrent 5.x):
  - Salt: 12 random bytes
  - Algorithm: PBKDF2-HMAC-SHA512
  - Iterations: 100000
  - Derived key length: 64 bytes
  - Output format: @ByteArray(base64(salt):base64(dk))
"""
import hashlib
import base64
import os
import sys


def generate_hash(password: str) -> str:
    """Generate qBittorrent-compatible PBKDF2 password hash."""
    salt = os.urandom(12)
    dk = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        100000,
        dklen=64
    )
    salt_b64 = base64.b64encode(salt).decode('ascii')
    dk_b64 = base64.b64encode(dk).decode('ascii')
    return f"@ByteArray({salt_b64}:{dk_b64})"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored qBittorrent password hash."""
    if not stored_hash.startswith("@ByteArray(") or not stored_hash.endswith(")"):
        return False
    inner = stored_hash[len("@ByteArray("):-1]
    if ":" not in inner:
        return False
    salt_b64, hash_b64 = inner.split(":", 1)
    try:
        salt = base64.b64decode(salt_b64)
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        100000,
        dklen=64
    )
    expected_b64 = base64.b64encode(dk).decode('ascii')
    return hash_b64 == expected_b64


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--check':
        if len(sys.argv) < 4:
            print("Usage: python3 qbt_password.py --check <password> <hash>", file=sys.stderr)
            sys.exit(1)
        if verify_password(sys.argv[2], sys.argv[3]):
            print("OK")
            sys.exit(0)
        else:
            print("MISMATCH")
            sys.exit(1)

    # 获取密码：优先从 argv，其次从 stdin（管道输入更安全，不暴露在 ps 中）
    password = ""
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('--'):
        password = sys.argv[1]
    elif not sys.stdin.isatty():
        password = sys.stdin.read().strip()

    if not password:
        print("Usage:", file=sys.stderr)
        print("  echo '<password>' | python3 qbt_password.py     # Generate hash (stdin, secure)", file=sys.stderr)
        print("  python3 qbt_password.py <password>              # Generate hash (argv)", file=sys.stderr)
        print("  python3 qbt_password.py --check <pass> <hash>   # Verify password", file=sys.stderr)
        sys.exit(1)

    print(generate_hash(password))
