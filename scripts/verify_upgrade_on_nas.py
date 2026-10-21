#!/usr/bin/env python3
"""
在 NAS 真机上验证 upgrade_init 备份 + upgrade_callback 恢复的完整链路。

使用 /vol1/@appshare/qbittorrent/_e2e_probe 作为沙盒，复刻真实权限结构：
  - qBittorrent/config 目录权限 000（qBittorrent 的安全约定）
  - config 内含 qBittorrent.conf / qBittorrent-data.conf / rss 子目录
验证点：
  1. 备份阶段能把 000 权限目录下的数据完整拷出
  2. 备份阶段结束后原始权限精确还原为 000
  3. 恢复阶段能把数据放回，且权限恢复正常（750/640）
  4. 恢复后配置文件内容与原始一致
"""
import sys
import os
import paramiko

HOST = os.environ.get("QBT_NAS_HOST", "")
USER = os.environ.get("QBT_NAS_USER", "")
PASS = os.environ.get("QBT_NAS_PASS", "")
PROBE = "/vol1/@appshare/qbittorrent/_e2e_probe"
LIB = "/vol1/@appshare/qbittorrent/_e2e_probe/lib/upgrade_lock.sh"


def sh(c, cmd, timeout=90):
    i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    err = "\n".join(l for l in err.splitlines() if "chdir" not in l).strip()
    return out, err


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond and detail:
        print(f"        {detail}")
    return cond


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15,
              allow_agent=False, look_for_keys=False)

    results = []

    print("=" * 68)
    print("准备沙盒（复刻真实 000 权限结构）")
    print("=" * 68)
    setup = f'''
rm -rf {PROBE}; mkdir -p {PROBE}/src/qBittorrent/config/rss {PROBE}/src/qBittorrent/data {PROBE}/dst
printf '[BitTorrent]\\nSession\\\\DefaultSavePath=/vol1/downloads\\n[Preferences]\\nWebUI\\\\Port=8080\\n' > {PROBE}/src/qBittorrent/config/qBittorrent.conf
printf 'data-conf\\n' > {PROBE}/src/qBittorrent/config/qBittorrent-data.conf
printf '{{}}' > {PROBE}/src/qBittorrent/config/rss/rss.json
printf 'resume' > {PROBE}/src/qBittorrent/data/fastresume.dat
chmod 000 {PROBE}/src/qBittorrent/config/rss
chmod 000 {PROBE}/src/qBittorrent/config
chmod 755 {PROBE}/src/qBittorrent/data
ls -ld {PROBE}/src/qBittorrent/config
'''
    out, err = sh(c, setup)
    print(out.strip())
    results.append(check("沙盒 config 目录为 000", "d---------" in out, out))

    print()
    print("=" * 68)
    print("阶段 1：备份（模拟 upgrade_init 逻辑）")
    print("=" * 68)
    backup = f'''
DATA_DIR="{PROBE}/src"; BACKUP_DIR="{PROBE}/dst"
_perm_list=$(mktemp)
_qbt_dump_perms() {{
    local d="$1"; [ -d "$d" ] || return 0
    local m; m=$(stat -c '%a' "$d" 2>/dev/null) || return 0
    printf '%s %s\\n' "$m" "$d" >> "$_perm_list"
    chmod u+rX "$d" 2>/dev/null || true
    local sub
    for sub in "$d"/*/; do [ -d "$sub" ] || continue; _qbt_dump_perms "${{sub%/}}"; done
}}
_qbt_dump_perms "$DATA_DIR" 2>/dev/null || true
find "$DATA_DIR" -type f -exec chmod u+r {{}} \\; 2>/dev/null || true
cp -a "$DATA_DIR"/. "$BACKUP_DIR"/ 2>/dev/null && echo "CP=ok" || echo "CP=fail"
while IFS=' ' read -r _m _p; do [ -n "$_m" ] && [ -e "$_p" ] && chmod "$_m" "$_p" 2>/dev/null || true; done < "$_perm_list"
rm -f "$_perm_list"
rm -rf "$BACKUP_DIR/.locks"
find "$BACKUP_DIR" -type d -exec chmod 700 {{}} \\; 2>/dev/null || true
find "$BACKUP_DIR" -type f -exec chmod 600 {{}} \\; 2>/dev/null || true
echo "--- 备份文件清单 ---"; find "$BACKUP_DIR" -type f | sort
echo "--- 备份后源目录权限（应仍为 000）---"; ls -ld "$DATA_DIR/qBittorrent/config"
'''
    out, err = sh(c, backup)
    print(out.strip())
    results.append(check("cp -a 成功", "CP=ok" in out, out))
    results.append(check("备份含 qBittorrent.conf",
                         "dst/qBittorrent/config/qBittorrent.conf" in out, out))
    results.append(check("备份含 rss 子目录文件",
                         "dst/qBittorrent/config/rss/rss.json" in out, out))
    results.append(check("备份含 data 目录文件",
                         "dst/qBittorrent/data/fastresume.dat" in out, out))
    results.append(check("源目录权限还原为 000",
                         "d---------" in out.split("备份后源目录权限")[-1], out))

    print()
    print("=" * 68)
    print("阶段 2：恢复（模拟 upgrade_callback 逻辑）")
    print("=" * 68)
    restore = f'''
DATA_DIR="{PROBE}/restored"; BACKUP_DIR="{PROBE}/dst"
mkdir -p "$DATA_DIR"
find "$DATA_DIR" -mindepth 1 -maxdepth 1 ! -name '.locks' -exec rm -rf {{}} + 2>/dev/null || true
cp -a "$BACKUP_DIR"/. "$DATA_DIR"/ 2>/dev/null && echo "CP=ok" || echo "CP=fail"
chmod 755 "$DATA_DIR" 2>/dev/null || true
find "$DATA_DIR/qBittorrent" -type d -exec chmod 750 {{}} \\; 2>/dev/null || true
find "$DATA_DIR/qBittorrent" -type f -exec chmod 640 {{}} \\; 2>/dev/null || true
echo "--- 恢复后文件 ---"; find "$DATA_DIR" -type f | sort
echo "--- 恢复后权限 ---"; ls -ld "$DATA_DIR/qBittorrent/config"
echo "--- 配置内容 ---"; cat "$DATA_DIR/qBittorrent/config/qBittorrent.conf"
'''
    out, err = sh(c, restore)
    print(out.strip())
    results.append(check("恢复 cp 成功", "CP=ok" in out, out))
    results.append(check("配置文件已恢复",
                         "restored/qBittorrent/config/qBittorrent.conf" in out, out))
    results.append(check("配置文件内容完整",
                         r"Session\DefaultSavePath=/vol1/downloads" in out, out))
    results.append(check("恢复后目录权限为 750（非 000）",
                         "drwxr-x---" in out.split("恢复后权限")[-1], out))

    print()
    print("=" * 68)
    print("清理沙盒")
    print("=" * 68)
    sh(c, f'chmod -R 755 {PROBE} 2>/dev/null; rm -rf {PROBE} && echo cleaned')
    print("  cleaned")

    c.close()
    print()
    print("=" * 68)
    print(f"结果: {sum(results)}/{len(results)} 通过")
    print("=" * 68)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
