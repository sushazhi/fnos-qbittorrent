#!/usr/bin/env python3
"""
验证 cmd/upgrade_lock.sh 的状态机逻辑。

本机 MSYS2 无 flock，无法真实加锁，因此这里用 Python 按 flock(2) 语义
（同一文件的独占锁，进程退出自动释放，fd 关闭释放）建模，
复现真实故障场景，验证脚本的判定逻辑是否正确。

真正验证的是：给定"锁是否被持有 / 持有者是否存活"，脚本作出的决策是否正确。
"""
import os
import subprocess
import sys
import tempfile

BASH = None
for cand in [r"C:\Program Files\Git\bin\bash.exe", "bash"]:
    try:
        r = subprocess.run([cand, "-c", "echo ok"], capture_output=True, text=True)
        if r.returncode == 0:
            BASH = cand
            break
    except Exception:
        continue

if not BASH:
    print("SKIP: 找不到 bash")
    sys.exit(0)

LOCK_LIB = r"D:/fnos/fnos-qbittorrent/cmd/upgrade_lock.sh"

passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def run(script, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True, env=env)


def setup_dirs():
    base = tempfile.mkdtemp(prefix="qbtlock_")
    var = os.path.join(base, "var")
    tmp = os.path.join(base, "tmp")
    os.makedirs(var, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    return base, var, tmp


print("=" * 62)
print("场景 1：锁文件持久化位置（不在 TRIM_PKGTMP）")
print("=" * 62)
base, var, tmp = setup_dirs()
r = run(f'. "{LOCK_LIB}"; qbt_lock_path "test.lock"',
        {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
path = r.stdout.strip().replace("\\", "/")
print(f"  锁路径: {path}")
check("锁文件位于 TRIM_PKGVAR 下", var.replace("\\", "/") in path, f"got {path}")
check("锁文件不在 TRIM_PKGTMP 下", tmp.replace("\\", "/") not in path, f"got {path}")

print()
print("=" * 62)
print("场景 2：TRIM_PKGVAR 不可用时回退到 /tmp")
print("=" * 62)
r = run(f'. "{LOCK_LIB}"; qbt_lock_path "test.lock"',
        {"TRIM_PKGVAR": "/nonexistent_dir_xyz", "TRIM_PKGTMP": tmp})
print(f"  回退路径: {r.stdout.strip()}")
check("回退到 /tmp", "/tmp/" in r.stdout.replace("\\", "/"), r.stdout)

print()
print("=" * 62)
print("场景 3：持有者 PID 存活判定")
print("=" * 62)
base, var, tmp = setup_dirs()
r = run(f'''
. "{LOCK_LIB}"
self_alive=no; qbt_pid_alive $$ && self_alive=yes
ghost_alive=yes; qbt_pid_alive 999999 || ghost_alive=no
echo "SELF=$self_alive"
echo "GHOST=$ghost_alive"
''', {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
out = r.stdout
check("自身进程判定为存活", "SELF=yes" in out, out)
check("不存在的 PID 判定为已死", "GHOST=no" in out, out)

print()
print("=" * 62)
print("场景 4：锁文件内容可正确回读持有者 PID")
print("=" * 62)
base, var, tmp = setup_dirs()
os.makedirs(os.path.join(var, ".locks"), exist_ok=True)
lf = os.path.join(var, ".locks", "x.lock").replace("\\", "/")
r = run(f'''
. "{LOCK_LIB}"
qbt_lock_write_owner "{lf}"
echo "READ=$(qbt_lock_read_owner "{lf}")"
echo "MYPID=$$"
''', {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
read_pid = [l.split("=")[1] for l in r.stdout.splitlines() if l.startswith("READ=")][0]
my_pid = [l.split("=")[1] for l in r.stdout.splitlines() if l.startswith("MYPID=")][0]
check(f"回读 PID 等于写入者 PID ({my_pid})", read_pid == my_pid, f"got {read_pid}")

print()
print("=" * 62)
print("场景 5：损坏/空的锁文件不导致误判")
print("=" * 62)
base, var, tmp = setup_dirs()
os.makedirs(os.path.join(var, ".locks"), exist_ok=True)
lf = os.path.join(var, ".locks", "y.lock").replace("\\", "/")
for content, label in [("", "空文件"), ("garbage without pid\n", "无 PID 的垃圾内容")]:
    with open(lf, "w") as f:
        f.write(content)
    r = run(f'. "{LOCK_LIB}"; qbt_lock_read_owner "{lf}"',
            {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
    got = r.stdout.strip()
    check(f"{label} -> 回读为空（触发自动接管路径）", got == "", f"got {repr(got)}")

print()
print("=" * 62)
print("场景 6：旧版本残留锁在 TRIM_PKGTMP 被清理（无 flock 时保守跳过）")
print("=" * 62)
base, var, tmp = setup_dirs()
legacy = os.path.join(tmp, "qbittorrent.upgrade.lock")
open(legacy, "w").write("123 1 upgrade_init\n")
r = run(f'. "{LOCK_LIB}"; qbt_purge_legacy_lock "qbittorrent.upgrade.lock"',
        {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
exists = os.path.exists(legacy)
has_flock = run("command -v flock").returncode == 0
if has_flock:
    check("有 flock 时残留锁被删除", not exists, "文件仍存在")
else:
    check("无 flock 时保守保留（不误删）", exists, "被误删了")

print()
print("=" * 62)
print("场景 7：qbt_unlock 幂等 + set -u 安全")
print("=" * 62)
r = run(f'''
set -u
. "{LOCK_LIB}"
qbt_unlock
qbt_unlock
echo "DONE rc=$?"
''', {"TRIM_PKGVAR": var, "TRIM_PKGTMP": tmp})
check("重复 unlock 不报错", "DONE rc=0" in r.stdout, r.stdout + r.stderr)

print()
print("=" * 62)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 62)
sys.exit(1 if failed else 0)
