#!/usr/bin/env python3
"""
在 NAS 真机上验证 install_callback 的配置合并逻辑（awk）。

抽取 install_callback 中真实的 awk 程序与 CUR_PORT 提取逻辑，
用真实 awk 执行真实配置样本，验证用户自定义设置是否被完整保留。

覆盖场景：
  1. 用户自定义端口 9999 / 地址 / 本地认证 / Downloads 路径 -> 必须全部保留
  2. 配置缺少端口键 -> 补默认 8080
  3. 端口值非法（非数字）-> 回退 8080
  4. 输出中不得出现重复的 section 或重复的 DefaultSavePath
"""
import base64
import os
import re
import sys

# 仓库根目录由脚本自身位置推导，不再硬编码维护者机器上的 Windows 路径；
# paramiko 改为使用时再导入，未安装时走 SKIP 而不是 ImportError。
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOST = os.environ.get("QBT_NAS_HOST", "")
USER = os.environ.get("QBT_NAS_USER", "")
PASS = os.environ.get("QBT_NAS_PASS", "")
LOCAL = os.path.join(REPO, "cmd", "install_callback")


def extract_awk_and_port_logic():
    with open(LOCAL, encoding="utf-8") as f:
        content = f.read()
    start = content.index("    awk -v alt_ui=")
    body_start = content.index("'", start) + 1
    body_end = content.index('\' "$CONFIG_FILE" > "$TMP_CONFIG"', body_start)
    awk_body = content[body_start:body_end]

    # 完整提取 CUR_PORT 段：从赋值行到 `echo "Preserving WebUI port` 之前，
    # 必须包含 case 兜底与 -gt 0 检查，否则非法值/缺失值不会被回退。
    # 起点兼容历史写法 CUR_PORT=$(grep …) 与现写法 CUR_PORT=$(awk …)。
    lines = content.splitlines()
    start_idx = end_idx = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("CUR_PORT=$("):
            start_idx = idx
        if start_idx is not None and "Preserving WebUI port" in line:
            end_idx = idx
            break
    if start_idx is None or end_idx is None:
        return awk_body, ""
    port_logic = "\n".join(lines[start_idx:end_idx])
    return awk_body, port_logic


CASES = [
    (
        "自定义端口 9999 + 自定义地址/认证/下载路径",
        r"""[BitTorrent]
Session\DefaultSavePath=/vol1/downloads
Session\Port=6881
Session\MaxConnec=500
[Preferences]
WebUI\Port=9999
WebUI\Address=127.0.0.1
WebUI\LocalHostAuth=true
WebUI\AlternativeUIEnabled=false
Downloads\SavePath=/my/dl
General\Locale=en_US
[Application]
FileLogger\Backup=true
""",
        [
            ("WebUI\\Port=9999", True, "用户端口必须保留"),
            ("WebUI\\Port=8080", False, "不得写入默认端口"),
            ("WebUI\\Address=127.0.0.1", True, "用户地址保留"),
            ("WebUI\\LocalHostAuth=true", True, "用户本地认证设置保留"),
            ("Downloads\\SavePath=/my/dl", True, "用户下载路径保留"),
            ("Session\\Port=6881", True, "BT 监听端口保留"),
            ("Session\\MaxConnec=500", True, "BT 连接数设置保留"),
            ("General\\Locale=en_US", True, "语言设置保留"),
            ("FileLogger\\Backup=true", True, "Application 段保留"),
        ],
    ),
    (
        "缺少端口键 -> 补默认 8080",
        r"""[BitTorrent]
Session\DefaultSavePath=/x
[Preferences]
WebUI\Address=0.0.0.0
""",
        [
            ("Port=8080", True, "缺失时补默认端口（写进 [WebUI] 段，qBittorrent 5.x 规范）"),
            ("WebUI\\Address=0.0.0.0", True, "地址保留"),
        ],
    ),
    (
        "端口值非法（abc）-> 回退 8080",
        r"""[Preferences]
WebUI\Port=abc
""",
        [
            ("WebUI\\Port=8080", True, "非法值回退为 8080"),
            ("WebUI\\Port=abc", False, "非法值不得保留"),
        ],
    ),
]


def main():
    awk_body, port_grep = extract_awk_and_port_logic()
    if not port_grep:
        print("FAIL: 未能从 install_callback 提取 CUR_PORT 逻辑")
        return 1

    awk_b64 = base64.b64encode(awk_body.encode()).decode()

    # 缺少 NAS 凭据或 paramiko 时优雅跳过，退出码 0（本机/CI 无 NAS 也可运行）
    if not HOST:
        print("[SKIP] 缺少 QBT_NAS_HOST")
        return 0
    try:
        import paramiko
    except ImportError:
        print("[SKIP] 未安装 paramiko")
        return 0

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15,
              allow_agent=False, look_for_keys=False)

    passed = failed = 0

    for title, conf, expects in CASES:
        print("=" * 70)
        print(f"# {title}")
        print("=" * 70)

        conf_b64 = base64.b64encode(conf.encode()).decode()

        remote = f'''
W=$(mktemp -d)
echo "{awk_b64}" | base64 -d > "$W/s.awk"
echo "{conf_b64}" | base64 -d > "$W/in.conf"

CONFIG_FILE="$W/in.conf"
{port_grep}

awk -v alt_ui="true" -v save_path="/vol1/newdl" -v new_pass="" \\
    -v root="/vol1/@appcenter/qbittorrent/ui/vuetorrent" -v cur_port="$CUR_PORT" \\
    -f "$W/s.awk" "$CONFIG_FILE" > "$W/out.conf"

cat "$W/out.conf"
rm -rf "$W"
'''
        i, o, e = c.exec_command(remote, timeout=60)
        out = o.read().decode("utf-8", "replace")

        print(out.strip())
        print()

        for needle, should_exist, desc in expects:
            present = needle in out
            ok = present == should_exist
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}  [{needle}]")
            if ok:
                passed += 1
            else:
                failed += 1

        # 结构完整性：section 不应重复
        for sec in ("[BitTorrent]", "[Preferences]", "[Application]"):
            n = out.count(sec)
            if n > 1:
                print(f"  FAIL  重复 section: {sec} 出现 {n} 次")
                failed += 1
            elif n == 1:
                print(f"  PASS  section 唯一: {sec}")
                passed += 1

        # DefaultSavePath 不应重复
        n_save = len(re.findall(r"Session\\DefaultSavePath=", out))
        if n_save > 1:
            print(f"  FAIL  DefaultSavePath 重复 {n_save} 行")
            failed += 1
        elif n_save == 1:
            print("  PASS  DefaultSavePath 唯一")
            passed += 1
        print()

    c.close()
    print("=" * 70)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
