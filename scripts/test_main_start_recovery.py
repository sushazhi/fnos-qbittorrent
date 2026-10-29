#!/usr/bin/env python3
"""
本地回归测试：cmd/main 的启动自愈逻辑。

覆盖三类曾经把现场带偏的场景：
  1. 残留实例锁（死 PID / 读不出来的 lockfile）——qBittorrent 启动后 1 秒静默退出；
  2. 启动失败被误报成“WebUI 端口被占用”——实际只是日志里别处（MCP 8082）的 bind 报错；
  3. 端口真被占用——应自动顺延并写回配置，而不是让应用启动失败。

测试用桩程序代替 qbittorrent-nox，全程在临时目录里跑，不碰真机数据：
    python3 scripts/test_main_start_recovery.py
"""
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_SH = os.path.join(REPO, "cmd", "main")

STUB = """#!/bin/bash
# 桩程序：记录参数，按 mode 决定行为
echo "$@" >> "$STUB_DIR/argv"
case "$(cat "$STUB_DIR/mode" 2>/dev/null)" in
    fastquit) exit 0 ;;
    *)        sleep 30 ;;
esac
"""

CONFIG = """[BitTorrent]
Session\\DefaultSavePath={tmp}/downloads/

[Preferences]
General\\Locale=zh_CN

[WebUI]
Address=0.0.0.0
Port={port}
AlternativeUIEnabled=true
"""

FAILURES = []


def check(name, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + detail) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


class Sandbox:
    """搭一套 TRIM_* 目录，让 cmd/main 以为自己跑在真机上。"""

    def __init__(self, port=18080, mode="alive", config_extra=""):
        self.root = tempfile.mkdtemp(prefix="qbt-main-test-")
        self.appdest = os.path.join(self.root, "appdest")
        self.pkgvar = os.path.join(self.root, "pkgvar")
        self.pkgtmp = os.path.join(self.root, "pkgtmp")
        self.stub_dir = os.path.join(self.root, "stub")
        self.config = os.path.join(self.pkgvar, "qBittorrent", "config", "qBittorrent.conf")
        self.log = os.path.join(self.pkgvar, "qbittorrent.log")
        self.temp_log = os.path.join(self.root, "trim_temp.log")
        self.port = port

        for d in (os.path.join(self.appdest, "bin"), self.pkgvar, self.pkgtmp, self.stub_dir):
            os.makedirs(d, exist_ok=True)

        stub = os.path.join(self.appdest, "bin", "qbittorrent-nox")
        with open(stub, "w", encoding="utf-8") as f:
            f.write(STUB)
        os.chmod(stub, os.stat(stub).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        with open(os.path.join(self.stub_dir, "mode"), "w", encoding="utf-8") as f:
            f.write(mode)

        os.makedirs(os.path.dirname(self.config), exist_ok=True)
        with open(self.config, "w", encoding="utf-8") as f:
            f.write(CONFIG.format(tmp=self.root, port=port) + config_extra)

    def env(self):
        return {
            "PATH": os.environ["PATH"],
            "HOME": self.root,
            "TRIM_APPDEST": self.appdest,
            "TRIM_PKGVAR": self.pkgvar,
            "TRIM_PKGTMP": self.pkgtmp,
            "TRIM_TEMP_LOGFILE": self.temp_log,
            "STUB_DIR": self.stub_dir,
        }

    def run(self, action="start"):
        return subprocess.run(
            ["bash", MAIN_SH, action],
            env=self.env(), cwd=REPO, capture_output=True, text=True, timeout=120,
        )

    def read(self, path, default=""):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return default

    def temp_log_text(self):
        return self.read(self.temp_log)

    def argv_text(self):
        return self.read(os.path.join(self.stub_dir, "argv"))

    def running_pid(self):
        pid_file = os.path.join(self.pkgtmp, "qbittorrent.pid")
        try:
            return int(self.read(pid_file).strip())
        except (ValueError, OSError):
            return 0

    def stop_stub(self):
        pid = self.running_pid()
        if pid:
            try:
                os.kill(pid, 15)
            except OSError:
                pass

    def cleanup(self):
        self.stop_stub()
        shutil.rmtree(self.root, ignore_errors=True)


def test_stale_lockfile_removed():
    """残留实例锁：死 PID 的 lockfile 必须在启动前被清掉。"""
    sb = Sandbox(mode="fastquit")
    try:
        lock = os.path.join(sb.pkgvar, "qBittorrent", "config", "lockfile")
        with open(lock, "w", encoding="utf-8") as f:
            f.write("999999\nqbittorrent-nox\nhost\nuuid\n")
        os.chmod(lock, 0o000)   # 模拟 ACL 把属主读权限剥掉的情形
        out = sb.run("start")
        check("残留实例锁被清理", not os.path.exists(lock),
              "lockfile 仍存在；stdout=%r" % out.stdout[-300:])
        check("清理动作有日志", "已清理残留实例锁" in out.stdout, out.stdout[-300:])
    finally:
        sb.cleanup()


def test_no_false_port_report():
    """启动秒退 + 日志里有历史 bind 报错 → 不能再报“端口被占用”。"""
    sb = Sandbox(mode="fastquit")
    try:
        with open(sb.log, "w", encoding="utf-8") as f:
            f.write("[2026-10-28 18:36:33] gateway-proxy started: ... -> 127.0.0.1:8080\n"
                    "Traceback (most recent call last):\n"
                    "OSError: [Errno 98] Address already in use\n")
        out = sb.run("start")
        text = sb.temp_log_text()
        check("秒退时退出码为 1", out.returncode == 1, "rc=%d" % out.returncode)
        check("不误报端口被占用", "被其他程序占用" not in text, text[-300:])
        check("给出通用失败提示", "启动失败" in text, text[-300:])
    finally:
        sb.cleanup()


def test_port_occupied_auto_shift():
    """WebUI 端口真被占用 → 顺延一个可用端口并写回配置。"""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        holder.bind(("0.0.0.0", 18090))
        holder.listen(1)
        sb = Sandbox(port=18090, mode="alive")
        try:
            out = sb.run("start")
            conf = sb.read(sb.config)
            check("端口被占用时自动顺延", "Port=18091" in conf, conf[-200:])
            check("启动参数使用新端口", "--webui-port=18091" in sb.argv_text(), sb.argv_text())
            check("启动成功退出码 0", out.returncode == 0, out.stdout[-300:] + out.stderr[-200:])
            check("顺延有明确提示", "18091" in out.stdout, out.stdout[-300:])
        finally:
            sb.cleanup()
    finally:
        holder.close()


def test_reads_section_port():
    """端口写在 [WebUI] 段内时必须能读回，不能被默认 8080 覆盖。"""
    sb = Sandbox(port=18095, mode="alive")
    try:
        sb.run("start")
        check("读取 [WebUI] Port", "--webui-port=18095" in sb.argv_text(), sb.argv_text())
    finally:
        sb.cleanup()


def test_legacy_duplicate_key_removed():
    """历史遗留的 WebUI\\Port= 重复键应被丢弃，且端口改写落到 [WebUI] 段内。"""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        holder.bind(("0.0.0.0", 18100))
        holder.listen(1)
        sb = Sandbox(port=18100, mode="alive",
                     config_extra="WebUI\\Port=18100\nWebUI\\Address=0.0.0.0\n")
        try:
            sb.run("start")
            conf = sb.read(sb.config)
            check("重复键已清除", "WebUI\\Port=" not in conf, conf[-300:])
            check("端口改写进 [WebUI] 段", re.search(r"\[WebUI\](?:.|\n)*?^Port=18101$", conf, re.M) is not None,
                  conf[-300:])
        finally:
            sb.cleanup()
    finally:
        holder.close()


def test_config_address_not_shifted():
    """配置里的监听地址在本机不可绑（写错 IP）→ 不该当成端口被占用而顺延。"""
    sb = Sandbox(port=18105, mode="alive",
                 config_extra="")
    try:
        conf = sb.read(sb.config).replace("Address=0.0.0.0", "Address=192.0.2.1")
        with open(sb.config, "w", encoding="utf-8") as f:
            f.write(conf)
        sb.run("start")
        check("地址异常不顺延端口", "--webui-port=18105" in sb.argv_text(), sb.argv_text())
    finally:
        sb.cleanup()


def test_broken_default_acl_repaired():
    """目录默认 ACL 被写成 default:user::--- 时必须修回来（否则 lockfile 读不了）。"""
    if not (shutil.which("getfacl") and shutil.which("setfacl")):
        print("  [SKIP] 环境无 getfacl/setfacl")
        return
    sb = Sandbox(mode="alive")
    cfg_dir = os.path.dirname(sb.config)
    probe = subprocess.run(["setfacl", "-m", "d:u::---", cfg_dir],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        print("  [SKIP] 该文件系统不支持 ACL：%s" % probe.stderr.strip())
        sb.cleanup()
        return
    try:
        sb.run("start")
        acl = subprocess.run(["getfacl", "-p", cfg_dir], capture_output=True, text=True).stdout
        check("默认 ACL 已修复", "default:user::rw-" in acl, acl)
    finally:
        sb.cleanup()


def test_legacy_key_normalized_without_shift():
    """端口没被占用时，[WebUI] 段内的历史重复键也应被规范化掉。"""
    sb = Sandbox(port=18110, mode="alive",
                 config_extra="WebUI\\Port=18110\n")
    try:
        sb.run("start")
        conf = sb.read(sb.config)
        check("无顺延时也清理重复键", "WebUI\\Port=" not in conf, conf[-300:])
        check("端口保持用户值", "Port=18110" in conf, conf[-300:])
        check("启动参数未变", "--webui-port=18110" in sb.argv_text(), sb.argv_text())
    finally:
        sb.cleanup()


def main():
    if not os.path.exists(MAIN_SH):
        print("找不到 cmd/main：%s" % MAIN_SH)
        return 2

    print("cmd/main 启动自愈回归测试")
    print("=" * 60)
    for fn in (test_stale_lockfile_removed,
               test_no_false_port_report,
               test_port_occupied_auto_shift,
               test_reads_section_port,
               test_legacy_duplicate_key_removed,
               test_legacy_key_normalized_without_shift,
               test_config_address_not_shifted,
               test_broken_default_acl_repaired):
        print(fn.__name__ + "  " + (fn.__doc__ or "").strip())
        start = time.time()
        fn()
        print("  用时 %.1fs" % (time.time() - start))

    print("=" * 60)
    if FAILURES:
        print("失败 %d 项：%s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
