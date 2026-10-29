#!/usr/bin/env python3
"""
本地回归测试：cmd/profile_acl.sh（profile 权限 / 实例锁自愈）。

这两件事曾各自写在不同脚本里，升级路径漏了默认 ACL 修复 → 用户升级后
qBittorrent 写出的 lockfile 属主自己都读不了，启动 1 秒静默退出，
再被启动脚本误报成"端口 8080 被占用"。本测试锁死修复口径。

运行：python3 scripts/test_profile_acl.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "cmd", "profile_acl.sh")
FAILURES = []


def check(name, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run_helper(data_dir, funcs):
    """在子 shell 里 source 脚本并调用若干函数，返回 (stdout, rc)。"""
    script = ". %s\n%s\n" % (
        subprocess.list2cmdline([HELPER]).replace("\\", "/"),
        "\n".join("%s %s" % (f, subprocess.list2cmdline([data_dir]).replace("\\", "/")) for f in funcs),
    )
    # 上面的 list2cmdline 只为转义；POSIX 下统一走 shlex
    import shlex
    script = ". %s\n%s\n" % (
        shlex.quote(HELPER),
        "\n".join("%s %s" % (f, shlex.quote(data_dir)) for f in funcs),
    )
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return r.stdout, r.returncode, r.stderr


def acl_of_dir(path):
    r = subprocess.run(["getfacl", "-p", path], capture_output=True, text=True)
    return r.stdout


def acl_of_file(path):
    r = subprocess.run(["getfacl", "-p", path], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("user::"):
            return line.split(":", 2)[2]
    return ""


def make_profile(port=8080):
    root = tempfile.mkdtemp(prefix="qbt-acl-")
    data = os.path.join(root, "appdata")
    cfg_dir = os.path.join(data, "qBittorrent", "config")
    data_dir = os.path.join(data, "qBittorrent", "data", "BT_backup")
    os.makedirs(cfg_dir)
    os.makedirs(data_dir)
    with open(os.path.join(cfg_dir, "qBittorrent.conf"), "w", encoding="utf-8") as f:
        f.write("[WebUI]\nPort=%d\n" % port)
    with open(os.path.join(data_dir, "abc.torrent"), "w", encoding="utf-8") as f:
        f.write("dummy")
    return root, data, cfg_dir, data_dir


def test_repair_acl():
    """default:user::--- 与被剥掉属主权限的文件都必须修回来，且不动 group:Users。"""
    if not (shutil.which("getfacl") and shutil.which("setfacl")):
        print("  [SKIP] 环境无 getfacl/setfacl")
        return
    root, data, cfg_dir, bt_dir = make_profile()
    try:
        probe = subprocess.run(["setfacl", "-m", "d:u::---", cfg_dir], capture_output=True, text=True)
        if probe.returncode != 0:
            print("  [SKIP] 文件系统不支持 ACL")
            return
        subprocess.run(["setfacl", "-m", "d:u::---", bt_dir], check=False)
        # group:Users 是 fnOS 的授权组；非 fnOS 环境（如 GitHub runner）没有这个组，
        # setfacl 会直接失败。这条断言只在组真实存在时才有意义。
        grp = subprocess.run(["setfacl", "-m", "g:Users:rw-", cfg_dir], capture_output=True, text=True)
        has_users_group = grp.returncode == 0

        lock = os.path.join(cfg_dir, "lockfile")
        with open(lock, "w", encoding="utf-8") as f:
            f.write("999999\nqbittorrent-nox\nhost\nuuid\n")
        subprocess.run(["chmod", "000", lock], check=False)
        subprocess.run(["setfacl", "-m", "u::---", lock], check=False)

        out, rc, err = run_helper(data, ["qbt_repair_profile_acls"])
        check("退出码为 0", rc == 0, err)
        check("config 默认 ACL 已修复", "default:user::rw-" in acl_of_dir(cfg_dir), acl_of_dir(cfg_dir))
        check("BT_backup 默认 ACL 已修复", "default:user::rw-" in acl_of_dir(bt_dir), acl_of_dir(bt_dir))
        check("文件属主可读", acl_of_file(lock) != "---", acl_of_file(lock))
        if has_users_group:
            check("fnOS 的 group:Users 授权保留", "group:Users:rw-" in acl_of_dir(cfg_dir), acl_of_dir(cfg_dir))
        else:
            print("  [SKIP] 本机无 Users 组（非 fnOS 环境），跳过 group 授权保留断言")
        check("有修复日志", "已修复" in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_clean_lock():
    """死 PID 的 lockfile 要删掉；被存活进程持有的要保留。"""
    root, data, cfg_dir, _ = make_profile()
    try:
        lock = os.path.join(cfg_dir, "lockfile")
        with open(lock, "w", encoding="utf-8") as f:
            f.write("999999\nqbittorrent-nox\nhost\nuuid\n")
        out, rc, err = run_helper(data, ["qbt_clean_profile_lock"])
        check("死 PID 锁被清理", not os.path.exists(lock), out + err)
        check("清理有日志", "已清理残留实例锁" in out, out)

        # 用当前 python 进程的 PID 冒充存活持有者
        os.makedirs(cfg_dir, exist_ok=True)
        with open(lock, "w", encoding="utf-8") as f:
            f.write("%d\nqbittorrent-nox\nhost\nuuid\n" % os.getpid())
        out2, _, _ = run_helper(data, ["qbt_clean_profile_lock"])
        check("存活持有的锁被保留", os.path.exists(lock), out2)
        check("保留时给出提示", "仍被存活进程" in out2, out2)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("profile_acl.sh 回归测试")
    print("=" * 60)
    for fn in (test_repair_acl, test_clean_lock):
        print(fn.__name__ + "  " + (fn.__doc__ or "").strip())
        fn()
    print("=" * 60)
    if FAILURES:
        print("失败 %d 项：%s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
