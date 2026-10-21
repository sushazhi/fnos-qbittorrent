#!/usr/bin/env python3
"""
模拟 qbt_lock 的两种失败分支，验证 upgrade_init 的错误提示是否准确。

本机 MSYS2 缺少 flock 且不认无执行位的脚本桩，因此改用 bash 函数覆盖 flock，
在同一进程内替换真实 flock 的行为，从而真实检验 qbt_lock 的判定逻辑与返回码。
"""
import os
import subprocess
import sys
import tempfile

BASH = r"C:\Program Files\Git\bin\bash.exe"
LIB = r"D:/fnos/fnos-qbittorrent/cmd/upgrade_lock.sh"


def run_case(flock_behavior, owner_pid, label, expect_busy):
    """flock_behavior: 'free' 成功 / 'busy' 恒失败"""
    base = tempfile.mkdtemp(prefix="qbtcase_")
    var = os.path.join(base, "var")
    tmp = os.path.join(base, "tmp")
    os.makedirs(var)
    os.makedirs(tmp)
    lockdir = os.path.join(var, ".locks")
    os.makedirs(lockdir)
    lockfile = os.path.join(lockdir, "qbittorrent.upgrade.lock")
    with open(lockfile, "w") as f:
        f.write(f"{owner_pid} 1750000000 upgrade_init\n")

    if flock_behavior == "free":
        flock_fn = "flock() { return 0; }"
    else:
        flock_fn = "flock() { return 1; }"

    # 持有者 PID 用「bash 自身 $$」写入并在同进程内读取。
    # 原因：MSYS2 的 kill -0 无法探测非 MSYS 进程（Windows PID 空间不同），
    # 用 Python 的 PID 会造成假阴性；Linux 上两种都等价。
    script = f'''
{flock_fn}
export TRIM_PKGVAR="{var.replace(chr(92), "/")}"
export TRIM_PKGTMP="{tmp.replace(chr(92), "/")}"
. "{LIB}"
if [ "{owner_pid}" = "SELF" ]; then owner="$$"; else owner="{owner_pid}"; fi
printf '%s 1750000000 upgrade_init\\n' "$owner" > "{lockfile.replace(chr(92), "/")}"
qbt_lock "qbittorrent.upgrade.lock" 2
echo "RC=$?"
echo "BUSY=${{QBT_LOCK_BUSY_PID:-<empty>}}"
echo "EXPECT_PID=$owner"
'''
    r = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
    out = r.stdout
    rc_val = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("RC=")), "?")
    busy_val = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("BUSY=")), "?")
    expect_pid = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("EXPECT_PID=")), "?")

    expect_rc = "0" if flock_behavior == "free" else "2"
    expect_busy_val = expect_pid if expect_busy else "<empty>"
    ok = rc_val == expect_rc and busy_val == expect_busy_val

    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"        rc={rc_val} busy={busy_val}   期望 rc={expect_rc} busy={expect_busy_val}")
    if not ok and r.stderr.strip():
        print(f"        stderr: {r.stderr.strip()[:200]}")
    return ok


print("=" * 66)
print("qbt_lock 分支判定（使用 bash 函数覆盖 flock）")
print("=" * 66)

results = []

results.append(run_case(
    "free", "999999",
    "无竞争 -> 加锁成功 rc=0", expect_busy=False))

results.append(run_case(
    "busy", "SELF",
    "锁被存活进程持有 -> rc=2 且报出 PID", expect_busy=True))

results.append(run_case(
    "busy", "999999",
    "锁记录已死 PID 且重开仍失败 -> rc=2 不报 PID", expect_busy=False))

print()
print("=" * 66)
print(f"结果: {sum(results)}/{len(results)} 通过")
print("=" * 66)
sys.exit(0 if all(results) else 1)
