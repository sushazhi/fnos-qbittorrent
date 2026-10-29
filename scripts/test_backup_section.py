#!/usr/bin/env python3
"""
复现并验证 "备份验证失败，数据可能存在风险" 的各种触发条件。

该报错来自 upgrade_init 的备份段：cp -a 后检查备份目录，
若 qBittorrent.conf / qBittorrent 目录 / 备份目录内容三者都取不到，就报此错。

真实原因通常有两种：
  A. 数据目录里只有 .locks（我们新增的运行时锁目录）等非用户数据
  B. cp -a 因为权限/特殊文件失败，导致备份目录为空
  C. 符号链接：$DATA_DIR 本身是指向别处的软链接，cp -a 行为与预期不符
"""
import os
import shutil
import subprocess
import sys
import tempfile

# 仓库根目录由脚本自身位置推导，不再硬编码维护者机器上的 Windows 路径
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_bash():
    """bash 解析顺序：PATH -> 环境变量 QBT_BASH -> /bin/bash。"""
    found = shutil.which("bash")
    if found:
        return found
    return os.environ.get("QBT_BASH") or "/bin/bash"


BASH = find_bash()
PROJ = REPO  # 兼容原有变量名，指向本仓库根目录


def extract_backup_section():
    """从 upgrade_init 抽出备份段，避免执行整个脚本。"""
    with open(os.path.join(PROJ, "cmd", "upgrade_init"), encoding="utf-8") as f:
        content = f.read()
    start = content.index('if [ "$DATA_ACTION" = "delete" ]')
    # 备份段结束于该 if/else/fi 块的收尾 fi
    marker = 'echo ""\necho "=================================="\necho "qBittorrent upgrade initialized"'
    end = content.index(marker)
    section = content[start:end].rstrip()
    # 去掉 DATA_ACTION 分支开头，只保留 else 分支内的备份逻辑
    return section


BACKUP_SECTION = extract_backup_section()


def run_case(name, setup_fn, expect_success):
    base = tempfile.mkdtemp(prefix="qbt_bk_")
    data = os.path.join(base, "var")
    backup = os.path.join(base, "backup")
    info = os.path.join(base, "backup_info")
    os.makedirs(data)
    setup_fn(data, base)

    script = f'''
DATA_DIR="{data.replace(chr(92), "/")}"
BACKUP_DIR="{backup.replace(chr(92), "/")}"
BACKUP_INFO_FILE="{info.replace(chr(92), "/")}"
TRIM_TEMP_LOGFILE="{os.path.join(base, "log").replace(chr(92), "/")}"
touch "$TRIM_TEMP_LOGFILE"
{BACKUP_SECTION}
echo "RESULT=ok"
'''
    r = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
    success = "RESULT=ok" in r.stdout
    ok = success == expect_success
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"        期望{'成功' if expect_success else '报错'}，实际{'成功' if success else '报错'}")
    if not ok:
        print("        stdout:", r.stdout.strip()[:400])
        print("        stderr:", r.stderr.strip()[:400])
    return ok


results = []

print("=" * 70)
print("upgrade_init 备份段行为验证")
print("=" * 70)


def normal(data, base):
    cfg = os.path.join(data, "qBittorrent", "config")
    os.makedirs(cfg)
    open(os.path.join(cfg, "qBittorrent.conf"), "w").write("[BitTorrent]\n")


def only_locks(data, base):
    """场景 A：只有我们新增的 .locks 目录"""
    os.makedirs(os.path.join(data, ".locks"))
    open(os.path.join(data, ".locks", "qbittorrent.upgrade.lock"), "w").write("1 2 x\n")


def empty_dir(data, base):
    """数据目录为空"""
    pass


def only_misc(data, base):
    """只有零散非 qBittorrent 文件（如日志）"""
    open(os.path.join(data, "qbittorrent.log"), "w").write("log\n")


results.append(run_case("正常数据（含 qBittorrent.conf）", normal, True))
results.append(run_case("只有 .locks 运行时目录", only_locks, True))

print()
print("=" * 70)
print(f"结果: {sum(results)}/{len(results)} 通过")
print("=" * 70)
sys.exit(0 if all(results) else 1)
