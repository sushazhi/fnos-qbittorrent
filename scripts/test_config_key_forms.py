#!/usr/bin/env python3
"""
本地回归测试：qBittorrent.conf 的键名写法兼容性。

背景：qBittorrent 5.x 保存配置时把 WebUI 相关键写在 [WebUI] 段内且不带前缀
（`Port=9090`、`APIKey=xxx`、`AlternativeUIEnabled=true`…），而项目里多处代码
历史上只认 `WebUI\\Port=` 这类带前缀的写法。读不到键的后果都不报错，只是
静默失效：端口发现失效、MCP 鉴权恒 401、UI 切换后缓存不刷新、覆盖安装
把用户端口改回 8080、甚至把死键写进 [WebUI] 段。

本测试覆盖：
  A. cmd/install_callback 的配置合并 awk（端口保留、键写进正确的段）
  B. app/bin/gateway-proxy.py 的端口/API Key/UI 解析
  C. app/bin/mcp-server.py 的 API Key 解析

运行：python3 scripts/test_config_key_forms.py
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []

CANONICAL = """[BitTorrent]
Session\\DefaultSavePath=/downloads/

[Preferences]
General\\Locale=zh_CN

[WebUI]
Address=0.0.0.0
Port=9090
AlternativeUIEnabled=true
RootFolder=/ui/vuetorrent
APIKey=qbt_canonical_key
"""

LEGACY = """[BitTorrent]
Session\\DefaultSavePath=/downloads/

[Preferences]
General\\Locale=zh_CN
WebUI\\Address=0.0.0.0
WebUI\\Port=9090
WebUI\\AlternativeUIEnabled=true
WebUI\\RootFolder=/ui/vuetorrent
WebUI\\APIKey=qbt_legacy_key
"""


def check(name, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def load_module(name, path, argv=None):
    old_argv = sys.argv
    if argv is not None:
        sys.argv = argv
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.argv = old_argv


# ---------------------------------------------------------------------------
# A. install_callback 的配置合并 awk
# ---------------------------------------------------------------------------
def extract_merge_awk():
    src = open(os.path.join(REPO, "cmd", "install_callback"), encoding="utf-8").read()
    start = src.index("awk -v alt_ui=")
    body_start = src.index("'", start) + 1
    body_end = src.index("' \"$CONFIG_FILE\"", body_start)
    return src[body_start:body_end]


def run_merge(awk_body, config_text, alt_ui="true", cur_port=8080,
              save_path="/downloads", new_pass="", root="/ui/vuetorrent"):
    tmp = tempfile.mkdtemp(prefix="qbt-merge-")
    try:
        conf = os.path.join(tmp, "qBittorrent.conf")
        script = os.path.join(tmp, "merge.awk")
        with open(conf, "w", encoding="utf-8") as f:
            f.write(config_text)
        with open(script, "w", encoding="utf-8") as f:
            f.write(awk_body)
        r = subprocess.run(
            ["awk", "-v", "alt_ui=" + alt_ui, "-v", "save_path=" + save_path,
             "-v", "new_pass=" + new_pass, "-v", "root=" + root,
             "-v", "cur_port=" + str(cur_port), "-f", script, conf],
            capture_output=True, text=True)
        return r.stdout, r.stderr
    finally:
        subprocess.run(["rm", "-rf", tmp])


def section_body(text, section):
    m = re.search(r'^\[%s\][ \t]*\n(.*?)(?=^\[|\Z)' % re.escape(section), text,
                  re.MULTILINE | re.DOTALL)
    return m.group(1) if m else ""


def test_install_merge():
    awk = extract_merge_awk()

    # 1) qbt 原生配置 + 用户在 WebUI 里把端口改成 9090 + 本次选择原生 UI
    out, err = run_merge(awk, CANONICAL, alt_ui="false", cur_port=9090)
    webui = section_body(out, "WebUI")
    check("A1 用户端口未被改回 8080", "Port=8080" not in out, out)
    check("A1 端口保持在 [WebUI] 段内", re.search(r'^Port=9090$', webui, re.M) is not None, webui)
    check("A1 UI 开关生效（改为 native）", re.search(r'^AlternativeUIEnabled=false$', webui, re.M) is not None, webui)
    check("A1 未产生 WebUI\\ 死键", "WebUI\\" not in out, out)
    check("A1 保存路径已更新", "Session\\DefaultSavePath=/downloads" in out, out)

    # 2) 历史配置（[Preferences] 里的 WebUI\xxx）应原样保留并可被改写
    out2, _ = run_merge(awk, LEGACY, alt_ui="false", cur_port=9090)
    check("A2 历史写法端口保留", "WebUI\\Port=9090" in out2, out2)
    check("A2 历史写法 UI 开关生效", "WebUI\\AlternativeUIEnabled=false" in out2, out2)

    # 3) 配置里完全没有 WebUI 相关键：补键必须落在 [WebUI] 段内而不是文件末尾
    bare = "[BitTorrent]\nSession\\DefaultSavePath=/old/\n\n[RSS]\nAutoDownloader\\DownloadRepacks=true\n"
    out3, _ = run_merge(awk, bare, alt_ui="true", cur_port=7777)
    webui3 = section_body(out3, "WebUI")
    check("A3 缺键时补出 [WebUI] 段", webui3.strip() != "", out3)
    check("A3 补的端口在 [WebUI] 段内", re.search(r'^Port=7777$', webui3, re.M) is not None, webui3)
    check("A3 未追加 WebUI\\ 死键", "WebUI\\Port=" not in out3, out3)

    # 4) 老端口键重复出现时不应产生两条端口
    dup = CANONICAL + "WebUI\\Port=8080\n"
    out4, _ = run_merge(awk, dup, alt_ui="true", cur_port=9090)
    check("A4 段内死键被清除", "WebUI\\Port=" not in out4, out4)
    check("A4 端口只保留一条", len(re.findall(r'^Port=\d+$', out4, re.M)) == 1, out4)


# ---------------------------------------------------------------------------
# B/C. 代理与 MCP 的配置解析
# ---------------------------------------------------------------------------
def test_proxy_parsers():
    proxy = load_module(
        "gp_under_test",
        os.path.join(REPO, "app", "bin", "gateway-proxy.py"),
        argv=["gateway-proxy.py", "/tmp/qbt-test.sock", "127.0.0.1", "8080", "/tmp/qbt-test.conf"],
    )

    check("B1 规范写法解析端口", proxy.parse_config_port(CANONICAL) == 9090,
          proxy.parse_config_port(CANONICAL))
    check("B1 历史写法解析端口", proxy.parse_config_port(LEGACY) == 9090,
          proxy.parse_config_port(LEGACY))
    check("B1 无端口时返回 None", proxy.parse_config_port("[Preferences]\nA=1\n") is None,
          proxy.parse_config_port("[Preferences]\nA=1\n"))
    check("B1 越界端口不采信",
          proxy.parse_config_port("[WebUI]\nPort=70000\n") is None,
          proxy.parse_config_port("[WebUI]\nPort=70000\n"))

    check("B2 规范写法解析 API Key", proxy.parse_config_api_key(CANONICAL) == "qbt_canonical_key",
          proxy.parse_config_api_key(CANONICAL))
    check("B2 历史写法解析 API Key", proxy.parse_config_api_key(LEGACY) == "qbt_legacy_key",
          proxy.parse_config_api_key(LEGACY))

    alt, root = proxy.parse_config_ui(CANONICAL)
    check("B3 规范写法解析 UI 开关", alt == "true" and root == "/ui/vuetorrent", (alt, root))
    alt2, root2 = proxy.parse_config_ui(LEGACY)
    check("B3 历史写法解析 UI 开关", alt2 == "true" and root2 == "/ui/vuetorrent", (alt2, root2))

    # 真机配置（存在则一并验证）
    live = "/vol1/@appdata/qbittorrent/qBittorrent/config/qBittorrent.conf"
    if os.path.exists(live):
        txt = open(live, encoding="utf-8", errors="replace").read()
        port = proxy.parse_config_port(txt)
        key = proxy.parse_config_api_key(txt)
        check("B4 真机配置能解析出端口", bool(port), port)
        check("B4 真机配置能解析出 API Key", bool(key), repr(key))


def test_mcp_parser():
    mcp = load_module("mcp_under_test", os.path.join(REPO, "app", "bin", "mcp-server.py"))
    check("C1 规范写法解析 API Key", mcp.parse_config_api_key(CANONICAL) == "qbt_canonical_key",
          mcp.parse_config_api_key(CANONICAL))
    check("C1 历史写法解析 API Key", mcp.parse_config_api_key(LEGACY) == "qbt_legacy_key",
          mcp.parse_config_api_key(LEGACY))


def main():
    print("qBittorrent.conf 键名写法兼容性回归测试")
    print("=" * 62)
    for fn in (test_install_merge, test_proxy_parsers, test_mcp_parser):
        print(fn.__name__ + "  " + (fn.__doc__ or "").strip())
        fn()
    print("=" * 62)
    if FAILURES:
        print("失败 %d 项：%s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
