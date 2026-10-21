#!/usr/bin/env python3
"""
端到端复现用户报障场景：

用户装的是 5.2.4（或任何 <=5.3.0.0），上次升级中断，TRIM_PKGTMP 里残留了
qbittorrent.upgrade.lock。此后每次点升级都会报
"错误：另一个升级进程正在运行，请稍后重试"，且无进程在跑。

本测试验证 5.3.0.1 的两处修复能否让他自动恢复：
  A. upgrade_init 会清理 TRIM_PKGTMP 里的历史残留锁并成功拿到新锁
  B. 即便 upgrade_init 没机会跑，install_callback 也会清理残留锁
  C. 新锁位置在 TRIM_PKGVAR，即使 TRIM_PKGTMP 被 fnOS 清空也不受影响
"""
import os
import subprocess
import sys
import tempfile

BASH = r"C:\Program Files\Git\bin\bash.exe"
PROJ = r"D:/fnos/fnos-qbittorrent"


def sandbox():
    base = tempfile.mkdtemp(prefix="qbt_e2e_")
    var = os.path.join(base, "var")
    tmp = os.path.join(base, "pkgtmp")
    os.makedirs(var)
    os.makedirs(tmp)
    return base, var.replace("\\", "/"), tmp.replace("\\", "/")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond and detail:
        print(f"        {detail}")
    return cond


results = []

print("=" * 70)
print("场景 A：5.2.4 用户带有 TRIM_PKGTMP 残留锁（无进程持有）")
print("=" * 70)
base, var, tmp = sandbox()
legacy = f"{tmp}/qbittorrent.upgrade.lock"
open(os.path.join(base, "pkgtmp", "qbittorrent.upgrade.lock"), "w").write(
    "12345 1750000000 upgrade_init\n")
print(f"  预置残留锁: {legacy}")

script = f'''
# flock 可用性：本机无 flock，用函数模拟"无人持有 -> 可上加锁"
flock() {{
  case "$1" in
    -n) return 0 ;;      # 尝试加锁成功
    -u) return 0 ;;      # 解锁
  esac
  return 0
}}
export TRIM_PKGVAR="{var}"
export TRIM_PKGTMP="{tmp}"
. "{PROJ}/cmd/upgrade_lock.sh"
qbt_lock "qbittorrent.upgrade.lock" 2
echo "LOCK_RC=$?"
echo "NEW_LOCK=$(ls "{var}/.locks" 2>/dev/null)"
echo "LEGACY_LEFT=$([ -f "{tmp}/qbittorrent.upgrade.lock" ] && echo yes || echo no)"
qbt_unlock
'''
r = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
out = r.stdout
print("  " + out.replace("\n", "\n  ").rstrip())

results.append(check("upgrade_init 成功获取锁", "LOCK_RC=0" in out, out))
results.append(check("历史残留锁已被清理", "LEGACY_LEFT=no" in out, out))
results.append(check("新锁位于 TRIM_PKGVAR/.locks", "qbittorrent.upgrade.lock" in out.split("NEW_LOCK=")[-1].splitlines()[0], out))

print()
print("=" * 70)
print("场景 B：install_callback 清理历史残留锁")
print("=" * 70)
base, var, tmp = sandbox()
stale_paths = [os.path.join(base, "pkgtmp", "qbittorrent.upgrade.lock"),
               os.path.join(base, "pkgtmp", "qbittorrent.lock")]
for p in stale_paths:
    open(p, "w").write("12345 1750000000 upgrade_init\n")
print(f"  预置残留锁: {len(stale_paths)} 个")

# 只抽取清理逻辑段执行，避免跑完整 install_callback
with open(os.path.join(PROJ, "cmd", "install_callback"), encoding="utf-8") as f:
    content = f.read()
start = content.index("# 清理历史版本")
end = content.index("unset _stale_lock") + len("unset _stale_lock")
snippet = content[start:end]

script = f'''
flock() {{ return 0; }}
APP_NAME="qbittorrent"
export TRIM_PKGTMP="{tmp}"
{snippet}
echo "REMAIN=$(ls "{tmp}" 2>/dev/null | wc -l)"
'''
r = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
out = r.stdout
print("  " + out.replace("\n", "\n  ").rstrip())
results.append(check("install_callback 清空了残留锁", "REMAIN=0" in out, out))

print()
print("=" * 70)
print("场景 C：TRIM_PKGTMP 被清空后，升级锁依然可用")
print("=" * 70)
base, var, tmp = sandbox()
script = f'''
flock() {{ case "$1" in -n|-u) return 0 ;; esac; return 0; }}
export TRIM_PKGVAR="{var}"
export TRIM_PKGTMP="{tmp}"
. "{PROJ}/cmd/upgrade_lock.sh"
qbt_lock "qbittorrent.upgrade.lock" 2 >/dev/null
echo "FIRST=$?"
qbt_unlock
# 模拟 fnOS 在升级中清空临时目录
rm -rf "{tmp}"; mkdir -p "{tmp}"
qbt_lock "qbittorrent.upgrade.lock" 2 >/dev/null
echo "SECOND=$?"
qbt_unlock
'''
r = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
out = r.stdout
print("  " + out.replace("\n", "\n  ").rstrip())
results.append(check("临时目录清空前后都能加锁",
                     "FIRST=0" in out and "SECOND=0" in out, out))

print()
print("=" * 70)
print(f"结果: {sum(results)}/{len(results)} 通过")
print("=" * 70)
sys.exit(0 if all(results) else 1)
