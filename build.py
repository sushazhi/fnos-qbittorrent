#!/usr/bin/env python3
"""
build.py - 统一的 fnOS 应用打包脚本（跨平台，替代 build.ps1 / build.sh）

用法:
    python build.py [--version 5.2.3.2] [--arch arm64|amd64] [--force]

特性:
    - 自动检测操作系统 (Windows/Linux)，选择对应的 fnpack 构建工具
    - 参数与 build.ps1 / build.sh 兼容
    - 复用 .local-build 缓存，避免重复下载
    - 下载产物按类型校验（ELF 魔数 + 架构 / zip CRC / 可选 sha256），校验不过即构建失败
    - 使用内置 zipfile 解压，无需外部 unzip
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(PROJECT_DIR, ".local-build")
MANIFEST_FILE = os.path.join(PROJECT_DIR, "manifest")
VERSION_FILE = os.path.join(BUILD_DIR, "versions.json")

# 架构检测：arm64 的 fnpack 在 Linux 上叫 arm
FNPACK_BASE = "https://static2.fnnas.com/fnpack/fnpack-1.2.3"
FNPACK_VER = "1.2.3"  # 用于版本缓存判断，需与 FNPACK_BASE 中的版本一致

# GitHub 下载加速源（按顺序尝试，直连放在最后兜底）
#
# 选型依据（2026-10 实测，用仓库最新 release 的 39.6MB fpk 逐站测速）：
#   gh-proxy.com       多轮 0.95~6.4 MB/s，最稳，首选
#   v4.gh-proxy.org    与 gh-proxy.com 同一后端（实测 x-github-request-id / etag /
#                      x-cache-hits 完全一致），只能作为节点切换，不能当灾备
#   ghfast.top         独立运营，但抖动极大（1.8 MB/s ~ 100s 超时）
#   ghproxy.imciel.com 独立运营，0.5~0.9 MB/s
#   直连               github.com 可握手但返回 0 字节并超时，仅作最后兜底
#
# 已淘汰：gh.dpik.top（实测 0.09 MB/s，且 API 侧 403）。
GITHUB_PROXIES = [
    "https://gh-proxy.com/",
    "https://v4.gh-proxy.org/",
    "https://ghfast.top/",
    "https://ghproxy.imciel.com/",
]

QBT_API = "https://api.github.com/repos/userdocs/qbittorrent-nox-static/releases"
VUE_API = "https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest"

# ---------------------------------------------------------------------------
# 下载校验
#
# 为什么要有：这里的二进制/压缩包全部经 gh-proxy 等第三方代理下载，代理失败时
# 常返回 200 + HTML 错误页或空内容。以前只判「读到的内容非空」就写盘、写
# versions.json 并打进 fpk，等于把一页 HTML 当成 qbittorrent-nox 发布出去。
# 现在改为「先写临时文件 -> 按类型校验 -> 通过才原子替换到正式位置并记版本」，
# 校验不通过一律不落盘、不写 versions.json，并让本次构建失败（fail closed）。
#
# 可选的内容哈希：环境变量 QBT_NOX_SHA256 / VUETORRENT_SHA256 / FNPACK_SHA256
# （qBittorrent-nox 另有按架构的 QBT_NOX_SHA256_ARM64 / QBT_NOX_SHA256_AMD64，
# 因为两个架构的二进制不同，一个哈希覆盖不了）。给了哈希就必须一致，
# 否则立即失败——这是唯一能防住「代理换了一份合法但错误的二进制」的手段，
# 魔数校验做不到。
# ---------------------------------------------------------------------------
QBT_NOX_SHA256 = os.environ.get("QBT_NOX_SHA256", "").strip().lower()
QBT_NOX_SHA256_ARM64 = os.environ.get("QBT_NOX_SHA256_ARM64", "").strip().lower()
QBT_NOX_SHA256_AMD64 = os.environ.get("QBT_NOX_SHA256_AMD64", "").strip().lower()
VUETORRENT_SHA256 = os.environ.get("VUETORRENT_SHA256", "").strip().lower()
FNPACK_SHA256 = os.environ.get("FNPACK_SHA256", "").strip().lower()

# ELF e_machine 取值（见 elf.h）：EM_AARCH64=183，EM_X86_64=62
ELF_MACHINE = {"arm64": 183, "amd64": 62}

# 每次构建前必须清空的目录：它们的内容 100% 由仓库生成。
# 以前只做 makedirs + copytree(dirs_exist_ok=True)，从仓库删掉的文件会永久
# 留在 .local-build 里被打进 fpk——本地产物会悄悄和仓库不一致，且这种差异
# 在 git diff 里看不出来。下载缓存（qbittorrent-nox-*、fnpack-*、
# vuetorrent.zip、versions.json）都在 BUILD_DIR 根下，不在下列目录内，
# 因此只清这几个目录即可，绝不能整删 .local-build（那样每次构建都要重下 70MB）。
CLEAN_DIRS = ["app", "cmd", "config", "wizard"]


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


def qbt_sha256_for(arch):
    """qBittorrent-nox 按架构取哈希：arm64/amd64 的二进制不同，共用一个哈希没意义。"""
    per_arch = QBT_NOX_SHA256_ARM64 if arch == "arm64" else QBT_NOX_SHA256_AMD64
    return per_arch or QBT_NOX_SHA256


def sha256_of(path):
    """流式计算 sha256，避免把 70MB 二进制整个读进内存。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _remove_quiet(path):
    """删临时文件：失败不重要（下次会被覆盖），不要因此打断下载重试。"""
    try:
        os.remove(path)
    except OSError:
        pass


def _verify_elf(path, expect_arch=None):
    """校验 ELF 魔数 + 位宽 + 架构（e_machine）。通过返回 None，失败返回原因。"""
    size = os.path.getsize(path)
    if size < 64:
        return f"文件只有 {size} 字节，不可能是静态 ELF 可执行文件"
    with open(path, "rb") as f:
        head = f.read(64)
    if head[:4] != b"\x7fELF":
        return f"缺少 ELF 魔数（前 4 字节 {head[:4]!r}，通常是代理返回的 HTML 错误页）"
    ei_class, ei_data = head[4], head[5]  # EI_CLASS: 1=32 位 2=64 位；EI_DATA: 1=小端 2=大端
    if ei_class not in (1, 2):
        return f"ELF 位宽字段非法（EI_CLASS={ei_class}）"
    if ei_data not in (1, 2):
        return f"ELF 字节序字段非法（EI_DATA={ei_data}）"
    # e_machine 在 ELF64/ELF32 头里都位于偏移 0x12，2 字节
    e_machine = int.from_bytes(head[18:20], "little" if ei_data == 1 else "big")
    if expect_arch:
        want = ELF_MACHINE[expect_arch]
        if e_machine != want:
            return (f"ELF 架构不匹配：e_machine={e_machine}，"
                    f"期望 {expect_arch}（e_machine={want}）")
    return None


def _verify_zip(path):
    """校验 zip 魔数 + 逐文件 CRC（testzip）。通过返回 None，失败返回原因。"""
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic != b"PK\x03\x04":
        return f"缺少 zip 魔数（前 4 字节 {magic!r}，通常是代理返回的 HTML 错误页）"
    try:
        with zipfile.ZipFile(path) as z:
            # testzip() 返回第一个损坏文件的名字，全部正常返回 None
            bad = z.testzip()
    except zipfile.BadZipFile as e:
        return f"zip 结构损坏：{e}"
    except Exception as e:  # 代理截断等异常形态统一按校验失败处理
        return f"zip 校验异常：{e}"
    if bad:
        return f"zip 内文件 CRC 校验失败：{bad}"
    return None


def _verify_text(path):
    """校验纯文本（VueTorrent LICENSE）。

    这一项只挡「明显不是文本」的情况：代理的错误页通常是 HTML，会在这里被拦下；
    真正的许可证文本（ASCII/UTF-8）通过。故意不做长度/关键词匹配，
    因为许可证正文随上游版本变化，硬编码关键词迟早误杀。
    """
    with open(path, "rb") as f:
        head = f.read(256 * 1024)
    if not head.strip():
        return "内容为空"
    low = head.lstrip()[:64].lower()
    if low.startswith(b"<!doctype") or low.startswith(b"<html"):
        return "内容是 HTML 页面，不是许可证文本"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return "内容不是 UTF-8 文本"
    return None


# 类型 -> 校验器。raw 表示不校验内容（保留给未来可能的其它下载）
_VERIFIERS = {"elf": _verify_elf, "zip": _verify_zip, "text": _verify_text}


def verify_file(path, kind, expect_arch=None, expect_sha256=""):
    """按类型校验本地文件。通过返回 None，失败返回中文原因。

    返回字符串而不是抛异常：download() 需要据此「换下一个代理重试」，
    异常会把重试循环打断。
    """
    if not os.path.exists(path):
        return "文件不存在"
    size = os.path.getsize(path)
    if size <= 0:
        return "文件为空（0 字节）"
    # 哈希放在类型校验之前：sha256 不符说明内容根本不是这份东西，
    # 再讨论魔数没有意义。
    if expect_sha256:
        got = sha256_of(path)
        if got != expect_sha256.strip().lower():
            return f"sha256 不匹配：期望 {expect_sha256}，实际 {got}"
    verifier = _VERIFIERS.get(kind)
    if verifier is None:
        return None
    if kind == "elf":
        return verifier(path, expect_arch)
    return verifier(path)


def probe_elf_version(path, target_arch, expected_version):
    """尽力而为地跑一次 `--version`，比魔数更硬的证据。通过返回 None。

    只在「构建机架构 == 目标架构」且 POSIX 上尝试：跨架构跑不了（会 exec 失败），
    Windows 上也没有这个语义。
    跑不起来（缺 glibc、被沙箱拦住、返回码非 0）只告警不失败——魔数 + 架构已经
    能排除代理错误页，不能因为开发机环境差异让构建失败。
    但如果真的跑起来了、输出了版本号且与期望不符，则判定失败：那说明下到的是
    另一份「合法但错误」的二进制，魔数校验发现不了。
    """
    if os.name != "posix" or target_arch != get_platform_arch():
        log("    (目标架构与构建机不同，跳过 --version 探测)", "gray")
        return None
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, timeout=60)
    except Exception as e:
        log(f"    (无法执行 --version：{e}；已通过 ELF 魔数与架构校验)", "yellow")
        return None
    out = (proc.stdout or b"").decode("utf-8", "replace")
    out += (proc.stderr or b"").decode("utf-8", "replace")
    out = out.strip()
    if proc.returncode != 0 or not out:
        log("    (--version 无有效输出；已通过 ELF 魔数与架构校验)", "yellow")
        return None
    first = out.splitlines()[0].strip()
    log(f"    --version -> {first}", "green")
    if expected_version:
        # 按「完整版本片段」匹配，避免 5.2.4 命中 5.2.40
        if not re.search(r"(?<![\d.])%s(?![\d.])" % re.escape(expected_version), out):
            return f"--version 输出与期望版本 {expected_version} 不一致（{first}）"
    return None


def download(url, out_file, description, component, version, force, use_proxy=True,
             kind="elf", expect_arch=None, expect_sha256="", probe_version=""):
    """带缓存 + 内容校验的下载。

    命中缓存也要校验（魔数/CRC，给了哈希再校验哈希），因为缓存自己也可能被
    之前版本的脚本写坏；校验不过就当作未命中重新下载。
    """
    tmp_file = out_file + ".part"

    if not force and os.path.exists(out_file) and version_match(component, version):
        err = verify_file(out_file, kind, expect_arch, expect_sha256)
        if err is None:
            log(f"  Using cached {description} (version {version})", "green")
            return True
        log(f"  Cached {description} 校验失败（{err}），重新下载...", "yellow")

    log(f"  Downloading {description}...", "yellow")

    # 代理优先、直连最后：实测本机直连 github.com 会 0 字节超时，
    # 把直连放最前会让每次构建先白等一轮超时。
    url_list = []
    if use_proxy:
        url_list = [proxy + url for proxy in GITHUB_PROXIES] + [url]
    else:
        url_list = [url]

    last_err = ""
    for u in url_list:
        try:
            log(f"    Trying {u[:60]}...", "gray")
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
            # 部分代理在失败时会返回 200 + 错误页/空内容。这里一律先落临时文件，
            # 校验通过后才原子替换到 out_file —— 坏内容永远不会出现在正式路径上，
            # 也就不会被复用、不会被记进 versions.json、不会被打进 fpk。
            if not data:
                last_err = "空内容（0 字节）"
                continue
            with open(tmp_file, "wb") as f:
                f.write(data)
            if kind == "elf" and os.name == "posix":
                # 探测 --version 需要可执行位；也顺带满足「下载后可执行」
                os.chmod(tmp_file, 0o755)
            err = verify_file(tmp_file, kind, expect_arch, expect_sha256)
            if err is None and probe_version:
                err = probe_elf_version(tmp_file, expect_arch or get_platform_arch(),
                                        probe_version)
            if err:
                host = urllib.parse.urlsplit(u).netloc
                last_err = f"{host} 返回的内容校验失败：{err}"
                log(f"    {last_err}", "yellow")
                _remove_quiet(tmp_file)
                continue
            os.replace(tmp_file, out_file)
            save_version(component, version)
            log(f"  Downloaded {description}", "green")
            return True
        except Exception as e:
            last_err = str(e)
            _remove_quiet(tmp_file)
    _remove_quiet(tmp_file)
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


def clean_build_dirs():
    """构建前清空由仓库内容生成的目录（见 CLEAN_DIRS 的说明）。

    只删 CLEAN_DIRS 里那几个目录本身，不碰 BUILD_DIR 根下的下载缓存；
    目录不存在时跳过，因此可以重复执行（幂等）。
    """
    for d in CLEAN_DIRS:
        p = os.path.join(BUILD_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
            log(f"  Cleaned stale {d}/", "gray")


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


def _fix_tar_permissions(tar_bytes, outer_patterns):
    """重建 tar：对匹配 outer_patterns 的文件设置 0755；app.tgz 递归处理其内部 bin/*。

    Windows 上 fnpack 打包会把所有文件写成 0666（无执行位），
    安装到 fnOS 后 cmd/* 生命周期脚本与 bin/* 可执行文件不可执行，
    导致升级回调的 `-x $MAIN_SCRIPT` 检查失败（"未找到主脚本"）。
    """
    src = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r")
    out_buf = io.BytesIO()
    dst = tarfile.open(fileobj=out_buf, mode="w", format=tarfile.USTAR_FORMAT)
    for m in src.getmembers():
        if m.isreg():
            data = src.extractfile(m).read()
            if m.name == "app.tgz":
                inner = gzip.decompress(data)
                inner_fixed = _fix_tar_permissions(inner, re.compile(r"^bin/"))
                data = gzip.compress(inner_fixed, compresslevel=6)
                m.size = len(data)
            elif outer_patterns.match(m.name):
                m.mode = 0o755
            ti = tarfile.TarInfo(m.name)
            ti.mode = m.mode
            ti.size = len(data)
            ti.mtime = m.mtime
            ti.type = m.type
            ti.uname = m.uname
            ti.gname = m.gname
            dst.addfile(ti, io.BytesIO(data))
        else:
            dst.addfile(m)
    dst.close()
    return out_buf.getvalue()


def fix_fpk_permissions(fpk_path):
    """修正 fpk 内 cmd/* 与 app.tgz 内 bin/* 的可执行权限（Windows 打包产物为 0666）。"""
    with gzip.open(fpk_path, "rb") as f:
        raw = f.read()
    fixed = _fix_tar_permissions(raw, re.compile(r"^cmd/[^/]+$"))
    with gzip.open(fpk_path, "wb") as f:
        f.write(fixed)
    log("  Fixed cmd/* and bin/* executable permissions in fpk", "green")


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

    # 获取 VueTorrent 最新版本（不锁定版本；旧内核兼容问题由 gateway-proxy.py
    # 注入的"内核兼容性检测"脚本兜底：内核过旧时显示提示而非静默空白）
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
    # 先清空再建：不清空的话，从仓库删掉的文件会永远留在产物里（详见 CLEAN_DIRS）
    clean_build_dirs()
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
    # 复制许可证与第三方许可说明，随 fpk 分发以满足 GPL-2.0 / MIT 合规要求
    for lic in ["LICENSE", "THIRD_PARTY_LICENSES.md"]:
        p = os.path.join(PROJECT_DIR, lic)
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
                    f"qbittorrent-nox_{arch}", qbt_tag, force,
                    kind="elf", expect_arch=arch,
                    expect_sha256=qbt_sha256_for(arch), probe_version=qbt_ver):
        log("  ERROR: qBittorrent-nox 下载/校验失败，构建中止"
            "（不写缓存、不写 versions.json）", "red")
        sys.exit(1)
    shutil.copy2(daemon_cache, daemon_target)
    if os.name == "posix":
        # copy2 保留缓存文件的权限，这里再显式兜一次，避免缓存来自旧脚本时没有执行位
        os.chmod(daemon_target, 0o755)

    # 复制 Python 脚本
    for script in ["gateway-proxy.py", "qbt_password.py", "mcp-server.py"]:
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
        if not download(vue_url, vue_cache, f"VueTorrent {vue_ver}", "vuetorrent", vue_ver, force,
                        kind="zip", expect_sha256=VUETORRENT_SHA256):
            log("  ERROR: VueTorrent 压缩包下载/校验失败（可能是代理返回的错误页），构建中止", "red")
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
        # 保留 VueTorrent 的 MIT 许可证文本（MIT 要求随分发保留版权与许可声明）
        vue_license_url = f"https://raw.githubusercontent.com/VueTorrent/VueTorrent/v{vue_ver}/LICENSE"
        if not download(vue_license_url, os.path.join(vue_target, "LICENSE"),
                       f"VueTorrent LICENSE {vue_ver}", "vuetorrent-license", vue_ver, force,
                       kind="text"):
            log("  Warning: 未能下载 VueTorrent LICENSE，fpk 内可能缺少 MIT 声明", "yellow")
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
    # 缓存判定和校验统一交给 download()：以前这里单独判「文件存在且大小非零」，
    # 缓存里一个被代理写入的 HTML 文件能一路走到 fnpack build 才炸。
    # 注意 fnpack 不校验架构字节：Linux arm64 构建机用的官方包是 32 位 linux-arm，
    # e_machine 与构建机不同，只校验 ELF 魔数（+ 可选 sha256）。
    if not download(fnpack_url, fnpack_path, "fnpack", "fnpack", FNPACK_VER, force,
                    use_proxy=False, kind="elf", expect_sha256=FNPACK_SHA256):
        log("  ERROR: fnpack 下载/校验失败，构建中止", "red")
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

    # Windows 上 fnpack 打包产物所有文件均为 0666（无执行位），
    # 修正 cmd/* 与 app.tgz 内 bin/* 的执行权限，否则升级时找不到可执行主脚本
    fix_fpk_permissions(fpk_out)

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
