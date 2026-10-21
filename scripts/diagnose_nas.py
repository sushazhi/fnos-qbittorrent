#!/usr/bin/env python3
"""通过 SSH 在 NAS 上执行只读诊断命令。"""
import sys
import os
import paramiko

HOST = os.environ.get("QBT_NAS_HOST", "")
USER = os.environ.get("QBT_NAS_USER", "")
PASS = os.environ.get("QBT_NAS_PASS", "")

COMMANDS = [
    ("宿主机信息", "uname -a; id"),
    ("qBittorrent 应用数据目录", "ls -la /vol1/@appdata/qbittorrent/ 2>&1 | head -30"),
    ("qBittorrent 子目录", "ls -la /vol1/@appdata/qbittorrent/qBittorrent/ 2>&1 | head -30"),
    ("config 目录", "ls -la /vol1/@appdata/qbittorrent/qBittorrent/config/ 2>&1 | head -30"),
    ("共享备份目录", "ls -la /vol1/@appshare/qbittorrent/ 2>&1 | head -20"),
    ("备份目录内容", "ls -laR /vol1/@appshare/qbittorrent/.data_backup/ 2>&1 | head -40"),
    ("临时目录锁", "ls -la /tmp/*qbittorrent* /var/tmp/*qbittorrent* 2>/dev/null"),
    ("已安装版本", "cat /vol1/@appdata/qbittorrent/../qbittorrent/manifest 2>/dev/null | head -5; ls -d /vol*/@appcenter/qbittorrent* 2>/dev/null"),
    ("App Center 应用目录", "ls -la /vol1/@appcenter/ 2>/dev/null | grep -i qbit"),
    ("安装日志", "ls -lt /tmp/*.log /var/log/*qbittorrent* 2>/dev/null | head -10"),
    ("用户与组", "getent passwd qbittorrent; getent group qbittorrent"),
    ("磁盘空间", "df -h /vol1 2>/dev/null"),
]


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PASS, timeout=15,
                       allow_agent=False, look_for_keys=False)
    except Exception as e:
        print(f"连接失败: {type(e).__name__}: {e}")
        return 1

    print(f"已连接 {HOST}\n")
    for title, cmd in COMMANDS:
        print("=" * 70)
        print(f"# {title}")
        print(f"$ {cmd}")
        print("-" * 70)
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
            out = stdout.read().decode("utf-8", "replace").strip()
            err = stderr.read().decode("utf-8", "replace").strip()
            if out:
                print(out)
            if err:
                print(f"[stderr] {err}")
            if not out and not err:
                print("(无输出)")
        except Exception as e:
            print(f"[执行异常] {e}")
        print()

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
