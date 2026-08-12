#!/usr/bin/env python3
"""
build.py - 统一的 fnOS 应用打包脚本（跨平台，替代 build.ps1 / build.sh）

用法:
    python build.py [--version 5.2.3.2] [--arch arm64|amd64] [--force]

特性:
    - 自动检测操作系统 (Windows/Linux)，选择对应的 fnpack 构建工具
    - 参数与 build.ps1 / build.sh 兼容
    - 复用 .local-build 缓存，避免重复下载
    - 使用内置 zipfile 解压，无需外部 unzip
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(PROJECT_DIR, ".local-build")
MANIFEST_FILE = os.path.join(PROJECT_DIR, "manifest")
VERSION_FILE = os.path.join(BUILD_DIR, "versions.json")

# 架构检测：arm64 的 fnpack 在 Linux 上叫 arm
FNPACK_BASE = "https://static2.fnnas.com/fnpack/fnpack-1.2.3"
FNPACK_VER = "1.2.1"  # 用于版本缓存判断

# 下载源（按顺序尝试）
MAIN_PROXY = "https://gh-proxy.com/"
BINARY_PROXY = "https://ghfast.top/"

QBT_API = "https://api.github.com/repos/userdocs/qbittorrent-nox-static/releases"
VUE_API = "https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest"


def log(msg, color="cyan"):
    """简单日志输出。Windows 下不强制 ANSI 颜色，避免乱码。"""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# 官方 fnpack 支持的平台映射（实测，参考 https://developer.fnnas.com/docs/cli/fnpack/）
#   Windows  : windows-amd64
#   Linux    : linux-amd64 / linux-arm
#   macOS    : darwin-amd64 / darwin-arm64
# 注意：Linux arm64 的官方文件名是 "linux-arm"（非 linux-arm64），已实测验证
def get_platform():
    """返回 'windows' / 'linux' / 'darwin'（macOS）。"""
    s = platform.system().lower()
    if s.startswith("win"):
        return "windows"
    if s.startswith("darwin"):
        return "darwin"
    return "linux"


def get_platform_arch():
    """返回当前机器的 CPU 架构标识（amd64 / arm64）。"""
    m = platform.machine().lower()
    if m in ("aarch64", "arm64", "armv8l", "arm"):
        return "arm64"
    return "amd64"


def get_fnpack_url(arch):
    """根据平台和架构返回 fnpack 下载地址，覆盖 Windows/Linux/macOS。

    - 构建工具 fnpack 必须用【当前开发机】的平台，而非目标应用平台
    - 因此这里用 get_platform() + get_platform_arch() 自动检测开发机
    """
    plat = get_platform()
    if plat == "windows":
        fnpack_arch = "amd64"
    elif plat == "darwin":
        # macOS Apple Silicon 用 arm64，Intel 用 amd64
        fnpack_arch = get_platform_arch()
    else:  # linux
        # Linux arm64 官方文件名为 linux-arm
        fnpack_arch = "arm" if get_platform_arch() == "arm64" else "amd64"
    return f"{FNPACK_BASE}-{plat}-{fnpack_arch}"


def load_versions():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_version(component, version):
    os.makedirs(BUILD_DIR, exist_ok=True)
    versions = load_versions()
    versions[component] = version
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)


def version_match(component, expected):
    return load_versions().get(component) == expected


def download(url, out_file, description, component, version, force, use_proxy=True):
    """带缓存的下载：命中缓存直接返回，否则按代理顺序尝试。"""
    if not force and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        if version_match(component, version):
            log(f"  Using cached {description} (version {version})", "green")
            return True
        log(f"  Version mismatch for {description}, re-downloading...", "yellow")

    log(f"  Downloading {description}...", "yellow")

    url_list = []
    if use_proxy:
        url_list = [MAIN_PROXY + url, BINARY_PROXY + url, url]
    else:
        url_list = [url]

    last_err = ""
    for i, u in enumerate(url_list):
        try:
            log(f"    Trying {u[:60]}...", "gray")
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
            if data and len(data) > 0:
                with open(out_file, "wb") as f:
                    f.write(data)
                save_version(component, version)
                log(f"  Downloaded {description}", "green")
                return True
            last_err = "empty download"
        except Exception as e:
            last_err = str(e)
    log(f"  ERROR: Failed to download {description}: {last_err}", "red")
    return False


def extract_zip(zip_path, dest_dir):
    """用内置 zipfile 解压，跨平台无需外部 unzip。"""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)


def copy_tree(src, dst):
    if os.path.exists(src):
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)


def read_manifest_version():
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("version"):
                return line.split("=", 1)[1].strip()
    return ""


def update_manifest(build_dir, version):
    """复制 manifest 并更新版本号。"""
    dest = os.path.join(build_dir, "manifest")
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    content = re.sub(r"(?m)^version\s*=.*", f"version = {version}", content)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)


def inject_version(vue_index_html, version, arch):
    """向 VueTorrent index.html 注入更新检查脚本。"""
    if not os.path.exists(vue_index_html):
        log("  Warning: VueTorrent index.html not found", "yellow")
        return
    with open(vue_index_html, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    if re.search(r"window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'", content):
        content = re.sub(
            r"window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'",
            f"window.QBITTORRENT_APP_VERSION = '{version}'",
            content,
        )
        if re.search(r"window\.QBITTORRENT_APP_ARCH\s*=\s*'[^']*'", content):
            content = re.sub(
                r"window\.QBITTORRENT_APP_ARCH\s*=\s*'[^']*'",
                f"window.QBITTORRENT_APP_ARCH = '{arch}'",
                content,
            )
        else:
            content = content.replace(
                f"window.QBITTORRENT_APP_VERSION = '{version}'",
                f"window.QBITTORRENT_APP_VERSION = '{version}'\n        window.QBITTORRENT_APP_ARCH = '{arch}'",
                1,
            )
    elif "</body>" in content:
        inject = (
            f"    <script>\n"
            f"        window.QBITTORRENT_APP_VERSION = '{version}';\n"
            f"        window.QBITTORRENT_APP_ARCH = '{arch}';\n"
            f"    </script>\n"
            f"    <script src=\"update-check.js\"></script>\n"
        )
        content = content.replace("</body>", inject + "</body>", 1)

    with open(vue_index_html, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"  Update check version/arch updated to {version}/{arch}", "green")


def main():
    parser = argparse.ArgumentParser(description="fnOS 应用统一打包脚本")
    parser.add_argument("--version", "-v", default="", help="打包版本号（默认读 manifest）")
    parser.add_argument("--arch", "-a", default="arm64", choices=["arm64", "amd64"], help="目标架构")
    parser.add_argument("--force", "-f", action="store_true", help="强制重新下载所有依赖")
    args = parser.parse_args()

    arch = args.arch
    force = args.force

    # 版本号：命令行优先，否则读 manifest
    app_version = args.version.strip()
    if not app_version:
        app_version = read_manifest_version()
        if not app_version:
            log("ERROR: 无法从 manifest 读取版本号", "red")
            sys.exit(1)
        log(f"Using version from manifest: {app_version}", "cyan")
    else:
        log(f"Using version from parameter: {app_version}", "cyan")

    log(f"Target architecture: {arch}", "cyan")
    log(f"Platform: {get_platform()}", "cyan")

    # qBittorrent-nox 版本 = 应用版本前 3 段
    qbt_ver = ".".join(app_version.split(".")[:3])
    log(f"qBittorrent-nox version: {qbt_ver}", "cyan")

    # 获取最新 qBittorrent-nox release tag（匹配 qbt_ver）
    qbt_tag = ""
    try:
        log("Fetching latest qBittorrent-nox release...", "cyan")
        req = urllib.request.Request(QBT_API, headers={"User-Agent": "build.py"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            releases = json.loads(resp.read().decode())
        pattern = f"^release-{qbt_ver}_v"
        for rel in releases:
            tag = rel.get("tag_name", "")
            if tag.startswith(pattern) or tag.startswith(f"release-{qbt_ver}_"):
                qbt_tag = tag
                break
    except Exception as e:
        log(f"  (网络获取 release 失败，尝试缓存: {e})", "yellow")

    # 回退到缓存
    cached_qbt = load_versions().get(f"qbittorrent-nox_{arch}")
    if not qbt_tag and cached_qbt:
        qbt_tag = cached_qbt
        log(f"  Fallback to cached qBittorrent-nox: {qbt_tag}", "yellow")
    if not qbt_tag:
        log(f"ERROR: 未找到 qBittorrent-nox release for {qbt_ver}", "red")
        sys.exit(1)
    log(f"  -> qBittorrent-nox release: {qbt_tag}", "cyan")

    # 获取 VueTorrent 最新版本
    vue_ver = ""
    try:
        log("Fetching latest VueTorrent version...", "cyan")
        req = urllib.request.Request(VUE_API, headers={"User-Agent": "build.py"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            rel = json.loads(resp.read().decode())
        vue_ver = rel.get("tag_name", "").lstrip("v")
    except Exception as e:
        log(f"  (网络获取 VueTorrent 失败，尝试缓存: {e})", "yellow")
    if not vue_ver:
        vue_ver = load_versions().get("vuetorrent", "")
        if vue_ver:
            log(f"  Fallback to cached VueTorrent: {vue_ver}", "yellow")
    if not vue_ver:
        log("ERROR: 无法获取 VueTorrent 版本", "red")
        sys.exit(1)
    log(f"  -> VueTorrent version: {vue_ver}", "cyan")

    log("========================================", "cyan")
    log(f"  fnOS Application - Local Build", "cyan")
    log(f"  Version: {app_version}  Arch: {arch}", "cyan")
    log("========================================", "cyan")

    # [1/5] 构建目录
    log("[1/5] Setting up build directory...", "yellow")
    for d in ["app/bin", "app/ui/vuetorrent", "cmd", "config", "wizard"]:
        os.makedirs(os.path.join(BUILD_DIR, d), exist_ok=True)
    log("  Build directory ready", "green")

    # [2/5] 复制项目文件
    log("[2/5] Copying project files...", "yellow")
    for sub in ["cmd", "config", "wizard"]:
        src = os.path.join(PROJECT_DIR, sub)
        if os.path.isdir(src):
            copy_tree(src, os.path.join(BUILD_DIR, sub))
    update_manifest(BUILD_DIR, app_version)
    for icon in ["ICON.PNG", "ICON_256.PNG"]:
        p = os.path.join(PROJECT_DIR, icon)
        if os.path.exists(p):
            shutil.copy2(p, BUILD_DIR)
    for ui_sub in ["config", "images", "index.html"]:
        p = os.path.join(PROJECT_DIR, "app", "ui", ui_sub)
        if os.path.exists(p):
            copy_tree(p, os.path.join(BUILD_DIR, "app", "ui", ui_sub))
    log("  Project files copied", "green")

    # [3/5] qBittorrent-nox
    log("[3/5] Preparing qBittorrent-nox...", "yellow")
    binary_arch = "aarch64" if arch == "arm64" else "x86_64"
    daemon_cache = os.path.join(BUILD_DIR, f"qbittorrent-nox-{arch}")
    daemon_target = os.path.join(BUILD_DIR, "app", "bin", "qbittorrent-nox")
    qbt_url = f"https://github.com/userdocs/qbittorrent-nox-static/releases/download/{qbt_tag}/{binary_arch}-qbittorrent-nox"
    if not download(qbt_url, daemon_cache, f"qBittorrent-nox {qbt_tag} ({binary_arch})",
                    f"qbittorrent-nox_{arch}", qbt_tag, force):
        sys.exit(1)
    shutil.copy2(daemon_cache, daemon_target)

    # 复制 Python 脚本
    for script in ["gateway-proxy.py", "qbt_password.py"]:
        p = os.path.join(PROJECT_DIR, "app", "bin", script)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(BUILD_DIR, "app", "bin", script))

    # [4/5] VueTorrent
    log("[4/5] Preparing VueTorrent WebUI...", "yellow")
    vue_cache = os.path.join(BUILD_DIR, "vuetorrent.zip")
    vue_target = os.path.join(BUILD_DIR, "app", "ui", "vuetorrent")
    vue_ready = os.path.exists(os.path.join(vue_target, "public", "index.html")) and version_match("vuetorrent", vue_ver)
    if not force and vue_ready:
        log(f"  Using cached VueTorrent {vue_ver}", "green")
    else:
        vue_url = f"https://github.com/VueTorrent/VueTorrent/releases/download/v{vue_ver}/vuetorrent.zip"
        if not download(vue_url, vue_cache, f"VueTorrent {vue_ver}", "vuetorrent", vue_ver, force):
            sys.exit(1)
        log("  Extracting VueTorrent...", "gray")
        extract_zip(vue_cache, os.path.join(BUILD_DIR, "temp-vuetorrent"))
        src = os.path.join(BUILD_DIR, "temp-vuetorrent", "vuetorrent")
        if os.path.isdir(src):
            copy_tree(src, vue_target)
        shutil.rmtree(os.path.join(BUILD_DIR, "temp-vuetorrent"), ignore_errors=True)
        screenshots = os.path.join(vue_target, "public", "screenshots")
        if os.path.exists(screenshots):
            shutil.rmtree(screenshots, ignore_errors=True)
        log("  VueTorrent ready", "green")

    # 复制 update-check.js
    uc_src = os.path.join(PROJECT_DIR, "app", "ui", "update-check.js")
    if os.path.exists(uc_src):
        shutil.copy2(uc_src, os.path.join(BUILD_DIR, "app", "ui", "vuetorrent", "public", "update-check.js"))
        shutil.copy2(uc_src, os.path.join(BUILD_DIR, "app", "ui", "update-check.js"))
        log("  update-check.js copied", "green")

    # [4.5/5] 注入版本信息
    log("[4.5/5] Injecting update check into WebUIs...", "yellow")
    inject_version(os.path.join(BUILD_DIR, "app", "ui", "vuetorrent", "public", "index.html"), app_version, arch)

    # [5/5] 构建 fpk
    log("[5/5] Building package...", "yellow")
    fnpack_url = get_fnpack_url(arch)
    fnpack_name = fnpack_url.rsplit("/", 1)[-1]
    fnpack_path = os.path.join(BUILD_DIR, fnpack_name)
    if not force and os.path.exists(fnpack_path) and os.path.getsize(fnpack_path) > 0 and version_match("fnpack", FNPACK_VER):
        log(f"  Using cached fnpack {FNPACK_VER}", "green")
    else:
        if not download(fnpack_url, fnpack_path, "fnpack", "fnpack", FNPACK_VER, force, use_proxy=False):
            sys.exit(1)

    if get_platform() == "windows":
        os.chmod(fnpack_path, 0o755) if os.name == "posix" else None
    else:
        os.chmod(fnpack_path, 0o755)

    fpk_out = os.path.join(BUILD_DIR, "qbittorrent.fpk")
    if os.path.exists(fpk_out):
        os.remove(fpk_out)

    log("  Running fnpack build...", "gray")
    old_cwd = os.getcwd()
    os.chdir(BUILD_DIR)
    try:
        if get_platform() == "windows":
            proc = subprocess.run([fnpack_path, "build", "."], capture_output=True)
        else:
            proc = subprocess.run(["./" + fnpack_name, "build", "."], capture_output=True)
    finally:
        os.chdir(old_cwd)

    if not os.path.exists(fpk_out):
        log("  ERROR: fnpack build failed", "red")
        if proc.stderr:
            log("  " + proc.stderr.decode("utf-8", "replace")[:2000], "red")
        sys.exit(1)

    final_name = f"qbittorrent-{app_version}-{arch}.fpk"
    shutil.move(fpk_out, os.path.join(PROJECT_DIR, final_name))
    log("  Build successful!", "green")

    log("", "cyan")
    log("========================================", "green")
    log("  Build Complete!", "green")
    log(f"  Output: {final_name}", "green")
    log("========================================", "green")


if __name__ == "__main__":
    main()
