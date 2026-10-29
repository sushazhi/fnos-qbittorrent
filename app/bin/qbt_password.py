#!/usr/bin/env python3
# Copyright (C) 2024-2026 yukihana
# SPDX-License-Identifier: GPL-2.0
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
import binascii
import hmac
import os
import sys

# qBittorrent 自己用 100000 轮 PBKDF2-HMAC-SHA512 / 12 字节盐（低于 OWASP 建议的
# 210k 轮），这里必须保持一致才能与 qBittorrent 互认，不能单方面提高。
PBKDF2_ITERATIONS = 100000
SALT_BYTES = 12
DK_LEN = 64


def generate_hash(password: str) -> str:
    """Generate qBittorrent-compatible PBKDF2 password hash."""
    salt = os.urandom(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=DK_LEN
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
    # 严格解码：非 base64 字符/长度不符直接判失败，不靠宽松解码的副作用
    try:
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
    except (binascii.Error, ValueError):
        return False
    if len(salt) != SALT_BYTES or len(expected) != DK_LEN:
        return False
    dk = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=DK_LEN
    )
    # 恒定时间比较：字符串 == 会在首个不同字节处提前返回，可被用来逐字节猜哈希
    return hmac.compare_digest(dk, expected)


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
        # 只去掉行尾换行：strip() 会把用户口令里有意的前后空格、制表符也吞掉
        password = sys.stdin.read().rstrip("\r\n")

    if not password:
        print("Usage:", file=sys.stderr)
        print("  echo '<password>' | python3 qbt_password.py     # Generate hash (stdin, secure)", file=sys.stderr)
        print("  python3 qbt_password.py <password>              # Generate hash (argv)", file=sys.stderr)
        print("  python3 qbt_password.py --check <pass> <hash>   # Verify password", file=sys.stderr)
        sys.exit(1)

    print(generate_hash(password))
