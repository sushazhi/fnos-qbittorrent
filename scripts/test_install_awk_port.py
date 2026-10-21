#!/usr/bin/env python3
"""
在 NAS 真机上验证 install_callback 的 awk 是否会覆盖用户自定义端口。

从 install_callback 中抽取真实的 awk 程序，用真实 awk 执行，
检查用户设置的 WebUI\\Port=9999 是否被强行改回 8080。
"""
import base64
import sys

import os
import paramiko

HOST = os.environ.get("QBT_NAS_HOST", "")
USER = os.environ.get("QBT_NAS_USER", "")
PASS = os.environ.get("QBT_NAS_PASS", "")
LOCAL = r"D:/fnos/fnos-qbittorrent/cmd/install_callback"


def main():
    with open(LOCAL, encoding="utf-8") as f:
        content = f.read()

    # 抽出 awk 脚本体（单引号包裹的部分）
    start = content.index("awk -v alt_ui=")
    body_start = content.index("'", start) + 1
    body_end = content.index("' \"$CONFIG_FILE\" > \"$TMP_CONFIG\"", body_start)
    awk_body = content[body_start:body_end]

    print("=" * 68)
    print("抽取到的 awk 片段（前 12 行）")
    print("=" * 68)
    for line in awk_body.splitlines()[:12]:
        print("  " + line)

    b64 = base64.b64encode(awk_body.encode()).decode()

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15,
              allow_agent=False, look_for_keys=False)

    remote = f'''
set -e
W=$(mktemp -d)
echo "{b64}" | base64 -d > "$W/script.awk"
cat > "$W/in.conf" << 'CONF'
[BitTorrent]
Session\\DefaultSavePath=/vol1/downloads
Session\\TempPath=/vol1/temp
[Preferences]
WebUI\\Port=9999
WebUI\\Address=0.0.0.0
WebUI\\AltUI=keepme
General\\Locale=zh_CN
CONF
awk -v alt_ui="true" -v save_path="/vol1/downloads" -v new_pass="" -v root="/root" \\
    -f "$W/script.awk" "$W/in.conf" > "$W/out.conf"
echo "=== 输入 ==="
cat "$W/in.conf"
echo "=== 输出 ==="
cat "$W/out.conf"
rm -rf "$W"
'''
    i, o, e = c.exec_command(remote, timeout=60)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    print()
    print(out.strip())
    if err.strip():
        print("[stderr]", err.strip()[:400])

    print()
    print("=" * 68)
    if "WebUI\\Port=9999" in out:
        print("结论：端口 9999 保留 —— 无此 bug")
    elif "WebUI\\Port=8080" in out:
        print("结论：用户端口 9999 被重置为 8080 —— 确认 BUG")
    else:
        print("结论：未找到端口行，需人工检查")

    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
