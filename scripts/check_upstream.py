#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_upstream.py — 检查 qBittorrent 上游版本并按需更新 manifest

上游仓库: userdocs/qbittorrent-nox-static
  release tag 形如: release-<qBittorrent 版本>_v<libtorrent 版本>
  例: release-5.2.4_v2.0.15

manifest 版本形如 5.2.4.0:
  前 3 段 = 上游 qBittorrent 版本
  第 4 段 = 本仓库修订号（同一上游版本需要重新打包时递增）

判定规则:
  1) 上游 qBittorrent 版本 > manifest 前 3 段
       -> 有新版本，新版本号 = <上游版本>.0
  2) 上游 qBittorrent 版本 == manifest 前 3 段，
     但 libtorrent 版本高于 manifest changelog 中记录的值
       -> 需要重新打包，第 4 段 +1
  3) 其余情况 -> 无更新
     （libtorrent 降级或相同都不触发，避免把旧版本写回 changelog）

用法:
  python3 scripts/check_upstream.py                        # 只检查，打印结果
  python3 scripts/check_upstream.py --write                # 检查并改写 manifest
  python3 scripts/check_upstream.py --force --write        # 强制产生一次更新
  python3 scripts/check_upstream.py --github-output "$GITHUB_OUTPUT" --write

退出码:
  0 检查成功（无论是否有更新）
  2 manifest 不存在或缺少 version 字段
  3 无法获取上游 release 列表
  4 上游 release 中没有可识别的 tag

环境变量:
  GITHUB_TOKEN / GH_TOKEN   可选，仅用于直连 api.github.com 时提高速率限制
"""

import argparse
import json
import os
import re
import sys
import urllib.request

UPSTREAM_REPO = "userdocs/qbittorrent-nox-static"
API_BASE = "https://api.github.com"
# 直连不可用时的镜像（仅代理 GitHub API 的只读请求，不携带令牌）
API_PROXIES = ("https://gh.dpik.top/", "https://gh-proxy.org/")
RELEASES_PATH = "/repos/%s/releases?per_page=100" % UPSTREAM_REPO

TAG_RE = re.compile(r"^release-(\d+(?:\.\d+)*)_v(\d+(?:\.\d+)*)$")
VERSION_LINE_RE = re.compile(r"(?m)^version\s*=.*$")
CHANGELOG_LINE_RE = re.compile(r"(?m)^changelog\s*=.*$")
LIBTORRENT_RE = re.compile(r"libtorrent\s+(\d+(?:\.\d+)*)")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MANIFEST = os.path.join(PROJECT_DIR, "manifest")


def log(msg):
    sys.stdout.write("%s\n" % msg)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# 版本工具
# ---------------------------------------------------------------------------
def parse_version(value):
    return tuple(int(p) for p in str(value).split(".") if p != "")


def pad_version(parts, size=4):
    parts = list(parts)
    while len(parts) < size:
        parts.append(0)
    return tuple(parts)


def compare_versions(a, b):
    """a > b -> 1；a < b -> -1；相等 -> 0。按段比较，缺省段视为 0。"""
    pa, pb = pad_version(parse_version(a)), pad_version(parse_version(b))
    if pa > pb:
        return 1
    if pa < pb:
        return -1
    return 0


# ---------------------------------------------------------------------------
# 上游 release
# ---------------------------------------------------------------------------
def http_get_json(url, token=None, timeout=30):
    headers = {
        "User-Agent": "fnos-qbittorrent-upstream-check",
        "Accept": "application/vnd.github+json",
    }
    # 仅在直连 api.github.com 时附带令牌，避免经第三方镜像时泄露凭证
    if token and url.startswith(API_BASE):
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_releases(token=None, api_base=""):
    if api_base:
        bases = [api_base.rstrip("/")]
    else:
        bases = [API_BASE] + [p + API_BASE for p in API_PROXIES]

    errors = []
    for base in bases:
        url = base + RELEASES_PATH
        try:
            data = http_get_json(url, token=token)
        except Exception as exc:
            errors.append("%s -> %s" % (url, exc))
            continue
        if isinstance(data, list) and data:
            return data
        errors.append("%s -> 响应不是非空 release 列表" % url)

    raise RuntimeError("获取上游 release 列表失败：\n  " + "\n  ".join(errors))


def pick_latest_release(releases):
    """在所有 release 中挑出 qBittorrent 版本最高的一个（同版本取 libtorrent 更高者）。

    优先只看正式版；若上游把全部 release 都标为 prerelease，则退化为包含 prerelease，
    避免误判为「无法识别上游版本」。
    """
    for include_prerelease in (False, True):
        best_key = None
        best = None
        for rel in releases:
            if rel.get("draft"):
                continue
            if rel.get("prerelease") and not include_prerelease:
                continue
            tag = rel.get("tag_name") or ""
            match = TAG_RE.match(tag)
            if not match:
                continue
            qbt, libtorrent = match.group(1), match.group(2)
            key = (pad_version(parse_version(qbt)), pad_version(parse_version(libtorrent)))
            if best_key is None or key > best_key:
                best_key = key
                best = {
                    "tag": tag,
                    "qbt": qbt,
                    "libtorrent": libtorrent,
                    "prerelease": bool(rel.get("prerelease")),
                    "published_at": rel.get("published_at", ""),
                    "html_url": rel.get("html_url", ""),
                }
        if best is not None:
            return best
    return None


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def read_manifest_version(text):
    match = VERSION_LINE_RE.search(text)
    if not match:
        raise RuntimeError("manifest 中未找到 version 字段")
    return match.group(0).split("=", 1)[1].strip()


def read_manifest_libtorrent(text):
    """从 changelog 行解析当前记录的 libtorrent 版本，解析不到返回空串。

    历史 manifest 里可能残留多条 changelog 行（手工累加/重复键所致），
    这里以最后一条为准，与 render_manifest「只保留最新一条」的语义保持一致。
    """
    matches = list(CHANGELOG_LINE_RE.finditer(text))
    if not matches:
        return ""
    inner = LIBTORRENT_RE.search(matches[-1].group(0))
    return inner.group(1) if inner else ""


def render_manifest(text, version, qbt, libtorrent, reason=""):
    """写回 version 与 changelog；只替换这两行，其余内容原样保留。

    changelog 的措辞随更新原因变化，避免「重新打包」被描述成「同步上游版本」：
      - qBittorrent 版本升级 -> 同步上游版本
      - libtorrent 变更/强制重打包 -> 重新打包

    changelog 只保留本次这一条：若 manifest 中残留了历史累加的多条 changelog 行
    （手工维护或重复键所致），除第一条位置外的其余条目一律删除。
    否则 build-and-release.yml 的 `grep "^changelog"` 会把多条拼进 Release 说明，
    造成「更新日志一直累加」。
    """
    if reason.startswith("上游 qBittorrent 升级"):
        detail = "1. 同步上游版本qbittorrent %s libtorrent %s" % (qbt, libtorrent)
    else:
        detail = "1. 重新打包（上游 qbittorrent %s libtorrent %s）" % (qbt, libtorrent)
    changelog = "v%s<br>%s" % (version, detail)

    text = VERSION_LINE_RE.sub(lambda _m: "version = %s" % version, text, 1)
    matches = list(CHANGELOG_LINE_RE.finditer(text))
    if matches:
        # 只保留第一条 changelog 的位置：第一条之前的文本原样保留，
        # 首条到末条之间的历史条目（含其行尾换行与空行分隔）整体删除，
        # 末条之后的内容原样保留，因此不会残留空行，也不改变文件收尾换行。
        text = text[:matches[0].start()] + "changelog = " + changelog + text[matches[-1].end():]
    else:
        text = text.rstrip("\n") + "\n\n"
        if "# 更新日志" not in text:
            text += "# 更新日志\n"
        text += "changelog = " + changelog + "\n"
    return text


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------
def decide(current_version, current_libtorrent, upstream, force=False):
    parts = current_version.split(".")
    current_qbt = ".".join(parts[:3])
    revision = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

    result = {
        "has_update": False,
        "new_version": "",
        "reason": "",
        "warning": "",
        "current_qbt": current_qbt,
        "current_revision": revision,
    }

    qbt_cmp = compare_versions(upstream["qbt"], current_qbt)

    if qbt_cmp > 0:
        result["has_update"] = True
        result["new_version"] = "%s.0" % upstream["qbt"]
        result["reason"] = "上游 qBittorrent 升级 %s -> %s" % (current_qbt, upstream["qbt"])
    elif qbt_cmp == 0 and current_libtorrent and \
            compare_versions(upstream["libtorrent"], current_libtorrent) > 0:
        result["has_update"] = True
        result["new_version"] = "%s.%d" % (current_qbt, revision + 1)
        result["reason"] = "上游 libtorrent 变更 %s -> %s" % (current_libtorrent, upstream["libtorrent"])
    elif qbt_cmp == 0 and not current_libtorrent:
        # changelog 中解析不到 libtorrent 版本 -> libtorrent 规则无法生效。
        # 明确告警，避免上游 libtorrent 升级被静默漏掉。
        result["warning"] = ("manifest changelog 中未记录 libtorrent 版本，"
                             "无法判断上游 libtorrent 是否变更（上游为 %s）"
                             % upstream["libtorrent"])

    if force and not result["has_update"]:
        # 强制模式：上游版本相同时递增修订号，保证总能产出新包
        result["has_update"] = True
        result["new_version"] = "%s.%d" % (current_qbt, revision + 1)
        result["reason"] = "强制更新（--force，上游版本未变化）"

    return result


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="检查 qBittorrent 上游版本并按需更新 manifest")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help="manifest 文件路径（默认：仓库根目录的 manifest）")
    parser.add_argument("--write", action="store_true",
                        help="将新版本号与 changelog 写回 manifest")
    parser.add_argument("--force", action="store_true",
                        help="忽略版本比较，强制产生一次更新")
    parser.add_argument("--github-output", default="",
                        help="把结果追加写入该文件（GitHub Actions 的 $GITHUB_OUTPUT）")
    parser.add_argument("--api-base", default="",
                        help="覆盖 GitHub API 地址（调试或使用镜像时使用）")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    manifest_path = os.path.abspath(args.manifest)
    if not os.path.exists(manifest_path):
        log("ERROR: manifest 不存在: %s" % manifest_path)
        return 2

    text = read_text(manifest_path)
    try:
        current_version = read_manifest_version(text)
    except RuntimeError as exc:
        log("ERROR: %s" % exc)
        return 2
    current_libtorrent = read_manifest_libtorrent(text)
    current_qbt = ".".join(current_version.split(".")[:3])
    log("当前 manifest 版本: %s (qBittorrent %s / libtorrent %s)"
        % (current_version, current_qbt, current_libtorrent or "未记录"))

    try:
        releases = fetch_releases(token=token, api_base=args.api_base)
    except Exception as exc:
        log("ERROR: %s" % exc)
        return 3

    upstream = pick_latest_release(releases)
    if not upstream:
        log("ERROR: 上游 release 中没有形如 release-<版本>_v<版本> 的 tag")
        return 4
    log("上游最新版本: qBittorrent %s / libtorrent %s  (tag %s, %s)"
        % (upstream["qbt"], upstream["libtorrent"], upstream["tag"],
           upstream["published_at"] or "未知发布时间"))
    if upstream.get("prerelease"):
        log("WARNING: 上游没有正式版 release，回退采用预发布 tag %s" % upstream["tag"])

    decision = decide(current_version, current_libtorrent, upstream, force=args.force)

    if upstream.get("prerelease"):
        note = ("上游仅有预发布版本（tag %s），本次结果基于 prerelease"
                % upstream["tag"])
        decision["warning"] = (decision.get("warning") + "；" + note
                               if decision.get("warning") else note)

    if decision.get("warning"):
        log("WARNING: %s" % decision["warning"])
        log("::warning::%s" % decision["warning"])

    outputs = {
        "has_update": "true" if decision["has_update"] else "false",
        "current_version": current_version,
        "current_qbt": current_qbt,
        "current_libtorrent": current_libtorrent,
        "upstream_tag": upstream["tag"],
        "upstream_qbt": upstream["qbt"],
        "upstream_libtorrent": upstream["libtorrent"],
        "upstream_published_at": upstream["published_at"],
        "new_version": decision["new_version"],
        "reason": decision["reason"],
        "warning": decision.get("warning", ""),
        "upstream_prerelease": "true" if upstream.get("prerelease") else "false",
    }
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                # 单行值直接写；含换行的值按 GITHUB_OUTPUT 的 heredoc 规则写
                value = "" if value is None else str(value)
                if "\n" in value:
                    handle.write("%s<<__EOF__\n%s\n__EOF__\n" % (key, value))
                else:
                    handle.write("%s=%s\n" % (key, value))

    if not decision["has_update"]:
        log("=> 上游无更新，跳过（当前 %s 已是上游最新）" % current_version)
        return 0

    log("=> 发现更新: %s -> %s  [%s]"
        % (current_version, decision["new_version"], decision["reason"]))

    if not args.write:
        log("   （未指定 --write，manifest 保持不变）")
        return 0

    new_text = render_manifest(text, decision["new_version"],
                               upstream["qbt"], upstream["libtorrent"],
                               decision["reason"])
    if new_text == text:
        log("   manifest 内容无变化，未写入")
        return 0

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    log("   已更新 manifest: version = %s" % decision["new_version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
