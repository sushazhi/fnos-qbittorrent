#!/usr/bin/env python3
"""
通过 fnOS 内部 API 完成 qBittorrent 卸载与重装。

背景：App Center 的 CLI 会拒绝带卸载向导的应用（hasWizardConfig=true），
但底层 API 接受完整的 wizard 参数。这里直接走 API。

步骤：
  1. 登录拿 token
  2. 查询 uninstall/info 确认向导字段
  3. 带 wizard_data_action=keep 调用 uninstall/start
  4. 轮询直到卸载完成
  5. 重装 5.3.0.0
"""
import json
import os
import sys
import time

# paramiko 改为软导入：未安装时走 SKIP 而不是 ImportError；
# 本地 fpk 路径以脚本自身位置推导，不再硬编码维护者机器上的 Windows 路径。
try:
    import paramiko
except ImportError:
    paramiko = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOST = os.environ.get("QBT_NAS_HOST", "")
USER = os.environ.get("QBT_NAS_USER", "")
PASS = os.environ.get("QBT_NAS_PASS", "")
FPK = "/vol1/appcenter-downloads/qbittorrent-5.3.0.0-tpk"  # 已解包目录（远端路径）
LOCAL_FPK = os.path.join(REPO, "qbittorrent-5.3.0.0-arm64.fpk")


def skip(msg):
    """缺少 NAS 凭据/依赖时优雅跳过，退出码 0。"""
    print(f"[SKIP] {msg}")
    return 0


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15,
              allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, timeout=120):
    i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    err = "\n".join(l for l in err.splitlines() if "chdir" not in l).strip()
    return out.strip(), err


def main():
    # 先在入口处做依赖/凭据检查，避免在无 NAS 的本机或 CI 上崩掉
    if not HOST:
        return skip("缺少 QBT_NAS_HOST")
    if paramiko is None:
        return skip("未安装 paramiko")

    c = ssh()

    print("=" * 66)
    print("步骤 1：登录获取 token")
    print("=" * 66)
    login_cmd = (
        "curl -s -X POST http://127.0.0.1:8666/v1/auth/login "
        "-H 'Content-Type: application/json' "
        f"-d '{{\"username\":\"{USER}\",\"password\":\"{PASS}\"}}'"
    )
    out, err = sh(c, login_cmd)
    print(out[:600] if out else "(空)")
    try:
        data = json.loads(out)
    except Exception:
        print("登录响应不是 JSON，停止")
        c.close()
        return 1

    token = None
    for key in ("token", "accessToken", "access_token"):
        if isinstance(data, dict) and data.get(key):
            token = data[key]
            break
    if not token and isinstance(data, dict) and isinstance(data.get("data"), dict):
        for key in ("token", "accessToken", "access_token"):
            if data["data"].get(key):
                token = data["data"][key]
                break
    if not token:
        print("未从响应中找到 token，键:", list(data.keys()) if isinstance(data, dict) else type(data))
        c.close()
        return 1
    print(f"token 已获取（长度 {len(token)}）")

    auth = f"-H 'Authorization: Bearer {token}'"

    print()
    print("=" * 66)
    print("步骤 2：查询卸载向导信息")
    print("=" * 66)
    out, err = sh(c, f"curl -s {auth} 'http://127.0.0.1:8666/app-center/v1/uninstall/info?appName=qbittorrent'")
    print(out[:1200] if out else "(空)")
    if err:
        print("[err]", err[:300])

    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
