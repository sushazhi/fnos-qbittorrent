#!/usr/bin/env python3
"""
qBittorrent MCP Server — Streamable HTTP 传输，零第三方依赖（仅标准库）。

让 AI 客户端（CodeBuddy / Cherry Studio / Claude 等）通过 MCP 协议管理 qBittorrent：

  客户端 --HTTP POST /mcp (JSON-RPC 2.0)--> 本服务 --HTTP--> qBittorrent WebUI API (127.0.0.1)

鉴权：
  - 请求头 Authorization: Bearer <key> 或 X-Api-Key: <key>
  - key 为 qBittorrent「Web API Key」（VueTorrent：设置 → WebUI → Web API Key 复制），
    从 qBittorrent.conf 的 WebUI\\WebAPIKey / WebUI\\APIKey 读取（每次请求实时读取，轮换即生效）
  - 未配置 API Key 时仅允许来自 127.0.0.1 的请求

启动：
  python3 mcp-server.py --port 8081 --config /path/qBittorrent.conf --webui-port 8080 \
    [--allow-dangerous]

高危操作开关：
  - 默认禁用高危工具（qb_delete_torrents / qb_stop_torrents / qb_start_torrents），
    调用时直接返回错误，tools/list 中的描述会标注「已被管理员禁用」
  - 传入 --allow-dangerous 才开放（由 gateway-proxy 按 mcp.conf 的
    MCP_ALLOW_DANGEROUS 透传，WebUI 设置面板可随时切换并热重启）

完整 API 接入：
  - qb_api_request 工具可透传调用任意 /api/v2 端点（GET 与低风险写操作
    始终允许，其余写操作受高危开关管控；auth/*、app/setPreferences、
    app/rotateAPIKey 等敏感端点一律禁止透传）

MCP 客户端配置示例（Streamable HTTP）：
  { "mcpServers": { "qbittorrent": { "type": "http", "url": "http://NAS_IP:8081/mcp",
    "headers": { "Authorization": "Bearer <你的API Key>" } } } }
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
SUPPORTED_PROTOCOL_VERSIONS = {"2025-03-26", "2025-06-18"}
SERVER_INFO = {"name": "qbittorrent-mcp", "version": "1.0.0"}

WEBUI_PORT = 8080
CONFIG_PATH = None
ALLOW_DANGEROUS = False

# 配置文件键（qBittorrent 5.2 Web API Key，兼容两种历史键名）
_RE_API_KEY = re.compile(
    r'^WebUI\\(?:WebAPIKey|APIKey)=(.+)$', re.MULTILINE
)

_key_cache = {"key": None, "mtime": -1.0}
_key_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 配置读取
# ---------------------------------------------------------------------------
def _conf_mtime():
    try:
        return os.path.getmtime(CONFIG_PATH)
    except OSError:
        return -1.0


def get_api_key():
    """实时读取 Web API Key（带 mtime 缓存，Key 轮换无需重启）。"""
    if not CONFIG_PATH:
        return ""
    with _key_lock:
        mtime = _conf_mtime()
        if mtime == _key_cache["mtime"]:
            return _key_cache["key"]
        key = ""
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8", errors="replace") as f:
                m = _RE_API_KEY.search(f.read())
            if m:
                key = m.group(1).strip()
        except Exception:
            key = ""
        _key_cache["key"] = key
        _key_cache["mtime"] = mtime
        return key


# ---------------------------------------------------------------------------
# qBittorrent API 调用（localhost 免密，LocalHostAuth=false）
# ---------------------------------------------------------------------------
def qbt_api(method, path, body=None, headers=None):
    """调用 qBittorrent WebUI API，返回 (status, parsed_json_or_text)。失败返回 (None, None)。"""
    import http.client
    try:
        conn = http.client.HTTPConnection("127.0.0.1", WEBUI_PORT, timeout=15)
        hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            hdrs.update(headers)
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        status = resp.status
        conn.close()
        try:
            return status, json.loads(data)
        except Exception:
            return status, data.decode("utf-8", "replace")
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# 工具实现（返回 (text, is_error)）
# ---------------------------------------------------------------------------
def _trim_torrent(t):
    """压缩 torrent 字段，减少 token 占用。"""
    return {
        "hash": t.get("hash"),
        "name": t.get("name"),
        "state": t.get("state"),
        "progress": round(t.get("progress", 0) * 100, 1),
        "size": t.get("size"),
        "dlspeed": t.get("dlspeed"),
        "upspeed": t.get("upspeed"),
        "eta": t.get("eta"),
        "ratio": t.get("ratio"),
        "category": t.get("category") or "",
        "tags": t.get("tags") or [],
        "save_path": t.get("save_path"),
    }


def _ok(text):
    return text, False


def _err(msg):
    return msg, True


def tool_app_info(_args):
    s1, ver = qbt_api("GET", "/api/v2/app/version")
    if s1 != 200:
        return _err("无法连接 qBittorrent（HTTP %s），请确认应用正在运行" % s1)
    s2, webui = qbt_api("GET", "/api/v2/app/webuiVersion")
    return _ok(json.dumps({
        "qbit_version": ver,
        "webui_version": webui if s2 == 200 else None,
        "mcp_server": SERVER_INFO,
    }, ensure_ascii=False))


def tool_global_status(_args):
    status, data = qbt_api("GET", "/api/v2/transfer/info")
    if status != 200 or not isinstance(data, dict):
        return _err("获取全局状态失败 (HTTP %s)" % status)
    keys = ("dl_info_speed", "dl_info_data", "up_info_speed", "up_info_data",
            "dl_rate_limit", "up_rate_limit", "connection_status", "dht_nodes")
    return _ok(json.dumps({k: data.get(k) for k in keys}, ensure_ascii=False))


def tool_list_torrents(args):
    params = {}
    for k in ("filter", "category", "tag", "sort", "limit"):
        if args.get(k) not in (None, ""):
            params[k] = str(args[k])
    qs = ("?" + urlencode(params)) if params else ""
    status, data = qbt_api("GET", "/api/v2/torrents/info" + qs)
    if status != 200 or not isinstance(data, list):
        return _err("获取任务列表失败 (HTTP %s)" % status)
    limit = int(args.get("limit") or 50)
    out = [_trim_torrent(t) for t in data[:limit]]
    return _ok(json.dumps({
        "total": len(data), "returned": len(out), "torrents": out,
    }, ensure_ascii=False, indent=1))


def tool_torrent_detail(args):
    h = (args.get("hash") or "").strip()
    if not h:
        return _err("缺少参数 hash")
    s1, files = qbt_api("GET", "/api/v2/torrents/files?hash=" + h)
    s2, props = qbt_api("GET", "/api/v2/torrents/properties?hash=" + h)
    if s1 != 200 and s2 != 200:
        return _err("获取任务详情失败 (HTTP %s/%s)，请确认 hash 是否有效" % (s1, s2))
    out = {"hash": h}
    if s2 == 200 and isinstance(props, dict):
        out["properties"] = {k: props.get(k) for k in (
            "save_path", "total_size", "piece_size", "dl_limit", "up_limit",
            "seeding_time", "time_elapsed", "share_ratio", "addition_date",
            "completion_date", "created_by", "comment")}
    if s1 == 200 and isinstance(files, list):
        out["files"] = [{
            "name": f.get("name"), "size": f.get("size"),
            "progress": round(f.get("progress", 0) * 100, 1),
        } for f in files]
    return _ok(json.dumps(out, ensure_ascii=False, indent=1))


def tool_add_torrent(args):
    urls = args.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        return _err("缺少参数 urls（磁力链接或 .torrent 的 HTTP(S) 地址，可多个）")
    body = {"urls": "\n".join(urls)}
    if args.get("savepath"):
        body["savepath"] = args["savepath"]
    if args.get("category"):
        body["category"] = args["category"]
    if args.get("stopped"):
        body["stopped"] = "true"
    status, data = qbt_api(
        "POST", "/api/v2/torrents/add",
        body=urlencode(body).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if status == 200:
        return _ok("已提交 %d 个下载任务（qBittorrent 返回 Ok.）" % len(urls))
    return _err("添加失败 (HTTP %s) %s" % (status, data))


def _torrents_action(actions, hashes):
    """依次尝试 qbt 5.x 与 4.x 的端点名（stop/pause、start/resume）。"""
    hs = "|".join(hashes) if isinstance(hashes, list) else str(hashes or "all")
    if not hs:
        return _err("缺少参数 hashes（任务 hash 数组或 \"all\"）")
    last = (None, None)
    for act in actions:
        status, data = qbt_api(
            "POST", "/api/v2/torrents/" + act,
            body=urlencode({"hashes": hs}).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if status == 200:
            return _ok("操作成功 (%s)" % act)
        last = (status, data)
    return _err("操作失败 (HTTP %s) %s" % last)


def tool_start_torrents(args):
    return _torrents_action(("start", "resume"), args.get("hashes"))


def tool_stop_torrents(args):
    return _torrents_action(("stop", "pause"), args.get("hashes"))


def tool_delete_torrents(args):
    hashes = args.get("hashes") or []
    if isinstance(hashes, str):
        hashes = [hashes]
    hashes = [h.strip() for h in hashes if h and h.strip()]
    if not hashes:
        return _err("缺少参数 hashes（任务 hash 数组）")
    body = {
        "hashes": "|".join(hashes),
        "deleteFiles": "true" if args.get("delete_files") else "false",
    }
    status, data = qbt_api(
        "POST", "/api/v2/torrents/delete",
        body=urlencode(body).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if status == 200:
        return _ok("已删除 %d 个任务 (deleteFiles=%s)" % (len(hashes), body["deleteFiles"]))
    return _err("删除失败 (HTTP %s) %s" % (status, data))


# ---------------------------------------------------------------------------
# 通用 API 透传（完整覆盖 qBittorrent WebUI API）
# ---------------------------------------------------------------------------
_API_PREFIX = "/api/v2/"
# 敏感端点：透传一律禁止（防止锁死鉴权 / 破坏 WebUI 安全配置）
_BLOCKED_POST_ENDPOINTS = ("auth/", "app/rotateAPIKey", "app/setPreferences", "app/logout", "app/exit")
# 免高危开关的写操作端点（低风险常用操作）
_SAFE_POST_ENDPOINTS = frozenset({
    "torrents/add",
    "torrents/setCategory", "torrents/setTags", "torrents/addTags",
    "torrents/removeTags", "torrents/rename", "torrents/setLocation",
    "torrents/setShareLimits", "torrents/setDownloadLimit",
    "torrents/setUploadLimit", "torrents/setSuperSeeding",
    "torrents/reannounce", "torrents/recheck",
    "torrents/topPrio", "torrents/bottomPrio", "torrents/increasePrio",
    "torrents/decreasePrio", "torrents/filePrio",
    "transfer/setSpeedLimitsMode", "transfer/setDownloadLimit",
    "transfer/setUploadLimit", "transfer/toggleSpeedLimitsMode",
    "rss/addFolder", "rss/addFeed", "rss/setRule", "rss/renameItem",
    "rss/removeItem", "rss/moveItem", "rss/markAsRead", "rss/setFeedURL",
})


def _normalize_api_path(p):
    """规整 API 路径：接受 'torrents/info'、'/torrents/info'、'/api/v2/torrents/info'。"""
    p = (p or "").strip()
    if not p:
        return None
    p = p.split("?")[0]  # 查询串应放 params，不接受拼在 path 里
    if p.startswith(_API_PREFIX):
        return p
    if not p.startswith("/"):
        p = "/" + p
    if p.startswith("/api/"):
        return None
    return _API_PREFIX + p.lstrip("/")


def tool_api_request(args):
    method = (args.get("method") or "GET").upper()
    if method not in ("GET", "POST"):
        return _err("仅支持 GET / POST")
    path = _normalize_api_path(args.get("path"))
    if not path:
        return _err("参数 path 无效：需为 /api/v2/ 下的端点，如 /api/v2/torrents/info")
    ep = path[len(_API_PREFIX):]

    # 安全管控
    if method == "POST":
        if ep.startswith(_BLOCKED_POST_ENDPOINTS):
            return _err("端点被禁止透传: %s（涉及鉴权或全局安全配置，防止 AI 锁死访问能力）" % path)
        if ep not in _SAFE_POST_ENDPOINTS and not ALLOW_DANGEROUS:
            return _err(
                "POST 请求属于写操作 (%s)，当前已被管理员禁用。"
                "请在 qBittorrent 应用标题栏「MCP 服务设置」中开启「允许高危操作」后重试。" % path
            )

    params = args.get("params") or {}
    if not isinstance(params, dict):
        return _err("参数 params 需为键值对对象")
    form = urlencode({k: str(v) for k, v in params.items()})

    if method == "GET":
        status, data = qbt_api("GET", path + (("?" + form) if form else ""))
    else:
        status, data = qbt_api(
            "POST", path, body=form.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if status is None:
        return _err("无法连接 qBittorrent，请确认应用正在运行")
    if status == 404:
        return _err("端点不存在 (404): %s，请核对 WebUI API 文档" % path)
    if status != 200:
        return _err("调用失败 (HTTP %s): %s" % (status, data))
    if isinstance(data, str):
        data = {"message": data}  # Ok. 等纯文本响应
    return _ok(json.dumps(data, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# 工具清单（name / description / inputSchema）
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "qb_app_info",
        "description": "获取 qBittorrent 版本信息与 MCP 服务信息",
        "inputSchema": {"type": "object", "properties": {}},
        "impl": tool_app_info,
    },
    {
        "name": "qb_global_status",
        "description": "获取全局传输状态（当前下载/上传速度、总量、连接状态等）",
        "inputSchema": {"type": "object", "properties": {}},
        "impl": tool_global_status,
    },
    {
        "name": "qb_list_torrents",
        "description": "列出下载任务。filter 可选 all/downloading/seeding/completed/stopped 等",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "状态过滤，如 downloading/completed"},
                "category": {"type": "string", "description": "按分类过滤"},
                "tag": {"type": "string", "description": "按标签过滤"},
                "sort": {"type": "string", "description": "排序字段，如 dlspeed/name"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 50"},
            },
        },
        "impl": tool_list_torrents,
    },
    {
        "name": "qb_torrent_detail",
        "description": "获取单个任务的详情（属性 + 文件列表）",
        "inputSchema": {
            "type": "object",
            "properties": {"hash": {"type": "string", "description": "任务 hash（来自列表的 hash 字段）"}},
            "required": ["hash"],
        },
        "impl": tool_torrent_detail,
    },
    {
        "name": "qb_add_torrent",
        "description": "添加下载任务（磁力链接或 .torrent 的 HTTP(S) 地址）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "磁力链接 / torrent 地址数组",
                },
                "savepath": {"type": "string", "description": "可选：保存目录（绝对路径）"},
                "category": {"type": "string", "description": "可选：分类"},
                "stopped": {"type": "boolean", "description": "可选：添加后不自动开始"},
            },
            "required": ["urls"],
        },
        "impl": tool_add_torrent,
    },
    {
        "name": "qb_start_torrents",
        "description": "开始（恢复）下载任务",
        "dangerous": True,
        "inputSchema": {
            "type": "object",
            "properties": {
                "hashes": {"description": "任务 hash 数组或 \"all\"", "type": "array", "items": {"type": "string"}},
            },
            "required": ["hashes"],
        },
        "impl": tool_start_torrents,
    },
    {
        "name": "qb_stop_torrents",
        "description": "停止（暂停）下载任务",
        "dangerous": True,
        "inputSchema": {
            "type": "object",
            "properties": {
                "hashes": {"description": "任务 hash 数组或 \"all\"", "type": "array", "items": {"type": "string"}},
            },
            "required": ["hashes"],
        },
        "impl": tool_stop_torrents,
    },
    {
        "name": "qb_delete_torrents",
        "description": "删除下载任务",
        "dangerous": True,
        "inputSchema": {
            "type": "object",
            "properties": {
                "hashes": {"description": "任务 hash 数组", "type": "array", "items": {"type": "string"}},
                "delete_files": {"type": "boolean", "description": "是否同时删除已下载的文件，默认 false"},
            },
            "required": ["hashes"],
        },
        "impl": tool_delete_torrents,
    },
    {
        "name": "qb_api_request",
        "description": (
            "通用 API 透传：调用任意 qBittorrent WebUI API 端点"
            "（完整 API 文档: https://github.com/qbittorrent/qBittorrent/wiki/"
            "WebUI-API-(qBittorrent-5.0)）。"
            "GET 查询始终允许；POST 中常用低风险操作（添加任务/分类/标签/限速/RSS 等）允许，"
            "其余写操作需管理员开启「允许高危操作」；鉴权与全局配置类端点（auth/*、app/setPreferences 等）已屏蔽。"
            "优先使用上方专用工具，仅在缺少对应封装时使用本工具。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP 方法，默认 GET",
                },
                "path": {
                    "type": "string",
                    "description": "API 路径，如 /api/v2/torrents/info（可省略 /api/v2 前缀，写作 torrents/info）",
                },
                "params": {
                    "type": "object",
                    "description": "参数键值对：GET 拼接为查询串，POST 作为表单提交（如 {\"hashes\": \"<hash>|all\"}）",
                },
            },
            "required": ["path"],
        },
        "impl": tool_api_request,
    },
]

_TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}
_TOOLS_SCHEMA = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]


def _build_tools_schema():
    """构建 tools/list 返回值；高危工具被禁用时在描述中标注，便于 AI 客户端识别。"""
    schema = []
    for t in TOOLS:
        desc = t["description"]
        if t.get("dangerous") and not ALLOW_DANGEROUS:
            desc += "（注意：该工具已被管理员禁用，调用会返回错误）"
        schema.append({
            "name": t["name"],
            "description": desc,
            "inputSchema": t["inputSchema"],
            "annotations": {"readOnlyHint": not t.get("dangerous", False)},
        })
    return schema


# ---------------------------------------------------------------------------
# JSON-RPC 分发
# ---------------------------------------------------------------------------
def handle_message(msg):
    """处理单条 JSON-RPC 消息，返回响应 dict；通知类消息返回 None。"""
    method = msg.get("method")
    mid = msg.get("id")

    def result(res):
        return {"jsonrpc": "2.0", "id": mid, "result": res}

    def error(code, message):
        return {"jsonrpc": "2.0", "id": mid if mid is not None else None,
                "error": {"code": code, "message": message}}

    if method == "initialize":
        client_ver = (msg.get("params") or {}).get("protocolVersion", "")
        proto = client_ver if client_ver in SUPPORTED_PROTOCOL_VERSIONS else "2025-03-26"
        return result({
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })

    if method and method.startswith("notifications/"):
        return None  # 通知无需响应

    if method == "ping":
        return result({})

    if method == "tools/list":
        return result({"tools": _build_tools_schema()})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name") or ""
        tool = _TOOLS_BY_NAME.get(name)
        if not tool:
            return error(-32602, "未知工具: %s" % name)
        if tool.get("dangerous") and not ALLOW_DANGEROUS:
            return result({
                "content": [{
                    "type": "text",
                    "text": "该操作属于高危操作（%s），当前已被管理员禁用。"
                            "请在 qBittorrent 应用标题栏「MCP 服务设置」中开启「允许高危操作」后重试。" % name,
                }],
                "isError": True,
            })
        try:
            text, is_error = tool["impl"](params.get("arguments") or {})
        except Exception as e:
            text, is_error = "工具执行异常: %s" % e, True
        return result({
            "content": [{"type": "text", "text": text}],
            "isError": bool(is_error),
        })

    return error(-32601, "Method not found: %s" % method)


# ---------------------------------------------------------------------------
# HTTP 服务（Streamable HTTP 传输）
# ---------------------------------------------------------------------------
class McpHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "qbittorrent-mcp/1.0.0"

    # -- 基础响应 -----------------------------------------------------------
    def _send(self, status, body=None, content_type="application/json", extra=None):
        data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data) if data else 0))
        self.end_headers()
        if data and self.command != "HEAD":
            self.wfile.write(data)

    def _rpc_error(self, status, code, message):
        self._send(status, {"jsonrpc": "2.0", "id": None,
                            "error": {"code": code, "message": message}})

    # -- 鉴权 ---------------------------------------------------------------
    def _check_auth(self):
        """返回错误消息字符串；通过则返回 None。"""
        key = get_api_key()
        got = self.headers.get("X-Api-Key") or ""
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            got = got or auth[7:].strip()
        if key:
            if got and got == key:
                return None
            return "未授权：请携带 qBittorrent 的 Web API Key（Authorization: Bearer <key> 或 X-Api-Key）。"
        # 未配置 Key：仅允许本机访问
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return None
        return "未授权：qBittorrent 尚未生成 Web API Key，请先在 VueTorrent（设置→WebUI→Web API Key）生成后重试。"

    # -- 路由 ---------------------------------------------------------------
    def do_OPTIONS(self):
        self._send(204, b"", extra={
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key, Mcp-Session-Id",
        })

    def do_GET(self):
        # Streamable HTTP：服务端不主动推送（SSE 可选），GET 一律拒绝
        if urlparse(self.path).path == "/mcp":
            self._rpc_error(405, -32000, "本服务仅支持 POST /mcp（Streamable HTTP，无 SSE 推送）")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/mcp":
            self._send(404, {"error": "not found"})
            return

        auth_err = self._check_auth()
        if auth_err:
            self._send(401, {"error": auth_err})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            self._rpc_error(400, -32700, "Parse error: 请求体不是合法 JSON")
            return

        # 批量消息（兼容处理）
        if isinstance(msg, list):
            responses = [r for m in msg if isinstance(m, dict) for r in [handle_message(m)] if r]
            if responses:
                self._send(200, responses)
            else:
                self._send(202, b"")
            return

        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            self._rpc_error(400, -32600, "Invalid Request: 缺少 jsonrpc 字段或格式错误")
            return

        try:
            resp = handle_message(msg)
        except Exception as e:
            logging_safe("tools dispatch error: %r" % (e,))
            resp = {"jsonrpc": "2.0", "id": msg.get("id"),
                    "error": {"code": -32603, "message": "Internal error"}}
        if resp is None:  # 纯通知
            self._send(202, b"")
        else:
            self._send(200, resp)

    def log_message(self, fmt, *args):
        pass  # 静默访问日志，避免刷 qBittorrent 日志


def logging_safe(msg):
    sys.stderr.write("[mcp] %s\n" % msg)
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    global WEBUI_PORT, CONFIG_PATH, ALLOW_DANGEROUS
    parser = argparse.ArgumentParser(description="qBittorrent MCP Server (Streamable HTTP)")
    parser.add_argument("--port", type=int, required=True, help="监听端口（建议 WebUI 端口 +1）")
    parser.add_argument("--config", required=True, help="qBittorrent.conf 路径（读取 Web API Key）")
    parser.add_argument("--webui-port", type=int, default=8080, help="qBittorrent WebUI 端口")
    parser.add_argument("--allow-dangerous", action="store_true",
                        help="允许高危操作（删除/启停任务），默认禁用")
    args = parser.parse_args()

    WEBUI_PORT = args.webui_port
    CONFIG_PATH = args.config
    ALLOW_DANGEROUS = args.allow_dangerous

    server = ThreadingHTTPServer(("0.0.0.0", args.port), McpHandler)
    server.daemon_threads = True
    logging_safe("started: http://0.0.0.0:%d/mcp (webui=%d, config=%s, allow_dangerous=%s)"
                 % (args.port, WEBUI_PORT, CONFIG_PATH, ALLOW_DANGEROUS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
