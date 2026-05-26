#!/usr/bin/env python3
"""
fnOS 统一网关反向代理 — qBittorrent WebUI 代理

监听 Unix socket (fnOS 网关) → 转发 HTTP/WS 到 127.0.0.1:PORT (qBittorrent)
核心功能：
  - 自动剥离 /app/qbittorrent 路径前缀
  - HTML 注入 JS polyfill（fetch/XHR/WebSocket 路径重写 + 反逃逸）
  - WebSocket Upgrade 透传（原始 TCP 双向隧道）
  - 静态资源 LRU 缓存（JS/CSS/图片/字体）
  - 动态端口发现（从 qBittorrent.conf 实时读取）
  - GitHub 更新检测 & fpk 下载
  - HEAD 请求正确响应（不返回 body）
  - 连接池复用后端 TCP 连接
  - 线程池限制最大并发数
"""

import http.server
import socket
import sys
import os
import signal
import re
import time
import threading
import gzip
import zlib
import select
import traceback
import json
import queue
import concurrent.futures
import logging
from http.client import HTTPConnection
from collections import OrderedDict

# ---------------------------------------------------------------------------
# brotli 可选支持
# ---------------------------------------------------------------------------
try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

# ---------------------------------------------------------------------------
# 编译好的正则（模块级，避免运行时反复编译）
# ---------------------------------------------------------------------------
_RE_CONFIG_PORT = re.compile(r'^WebUI\\Port=(\d+)', re.MULTILINE)
_RE_REFERER = re.compile(r'^https?://[^/]+')
_RE_HTML_ATTR = re.compile(rb'(src|href|action)=([\'"])/(?!/?(?:app|cgi)/)')
_RE_SAME_COOKIE_ATTR = re.compile(r';\s*[Ss]ame[Ss]ite\s*=\s*[^;\s]+')

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
PREFIX = "/app/qbittorrent"
UPDATE_REPO = "sushazhi/fnos-qbittorrent"
UPDATE_API = "https://api.github.com"
UPDATE_PROXY = "https://ghfast.top/"
STATIC_EXTENSIONS = frozenset({
    'js', 'css', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico',
    'woff', 'woff2', 'ttf', 'eot',
})
FPK_MAX_SIZE = 100 * 1024 * 1024  # 100 MB

# ---------------------------------------------------------------------------
# 架构检测
# ---------------------------------------------------------------------------
import platform as _platform
_RAW_ARCH = _platform.machine()
if _RAW_ARCH in ('aarch64', 'arm64', 'armv8l'):
    CURRENT_ARCH = 'arm64'
else:
    CURRENT_ARCH = 'amd64'

# ---------------------------------------------------------------------------
# 注入脚本
# ---------------------------------------------------------------------------
INJECT_SCRIPT = (
    '<script>window.QBITTORRENT_APP_ARCH="%s";</script><script>'
    '(function(){'
    'var P="%s";'
    'var _f=window.fetch;'
    'window.fetch=function(u,o){'
    'if(typeof u==="string"&&u.charAt(0)==="/"&&!u.startsWith(P)){u=P+u;}'
    'return _f.call(this,u,o);'
    '};'
    'var _o=XMLHttpRequest.prototype.open;'
    'XMLHttpRequest.prototype.open=function(m,u,s){'
    'if(typeof u==="string"&&u.charAt(0)==="/"&&!u.startsWith(P)){arguments[1]=P+u;}'
    'return _o.apply(this,arguments);'
    '};'
    'var _cw=window.WebSocket;'
    'if(_cw){'
    'window.WebSocket=function(u,p){'
    'if(typeof u==="string"&&u.charAt(0)==="/"&&!u.startsWith(P)){'
    'var _proto=location.protocol==="https:"?"wss:":"ws:";'
    'u=_proto+"//"+location.host+P+u;'
    '}'
    'else if(typeof u==="string"&&u.startsWith("ws")){'
    'var r=new RegExp("^(wss?)://([^/]+)(/.*)$");'
    'var m=u.match(r);'
    'if(m&&!m[3].startsWith(P)){u=m[1]+"://"+m[2]+P+m[3];}'
    '}'
    'return p?new _cw(u,p):new _cw(u);'
    '};'
    'window.WebSocket.prototype=_cw.prototype;'
    'window.WebSocket.CONNECTING=_cw.CONNECTING;'
    'window.WebSocket.OPEN=_cw.OPEN;'
    'window.WebSocket.CLOSING=_cw.CLOSING;'
    'window.WebSocket.CLOSED=_cw.CLOSED;'
    '}'
    'try{'
    'var _td=Object.getOwnPropertyDescriptor(top,"location");'
    'if(_td&&_td.set){'
    'Object.defineProperty(top,"location",{'
    'set:function(v){console.warn("[qB] Blocked top.location:",v);},'
    'get:function(){return window.location;}'
    '});'
    '}'
    '}catch(e){}'
    'setInterval(function(){'
    'try{'
    'document.querySelectorAll(".overlay,.desktop-overlay,#overlay,.MuiDialog-root").forEach(function(el){el.style.display="none";});'
    '}catch(ex){}'
    '},500);'
    '})();'
    '</script>'
) % (CURRENT_ARCH, PREFIX)

INJECT_SCRIPT_B = INJECT_SCRIPT.encode()

# ---------------------------------------------------------------------------
# 命令行参数
# ---------------------------------------------------------------------------
SOCK_PATH = sys.argv[1]
TARGET_HOST = sys.argv[2]
INITIAL_PORT = int(sys.argv[3])
CONFIG_PATH = sys.argv[4] if len(sys.argv) > 4 else None

# ---------------------------------------------------------------------------
# 连接池
# ---------------------------------------------------------------------------
class ConnectionPool:
    """HTTPConnection 连接池，复用 TCP 连接避免反复握手。"""

    def __init__(self, host, port, maxsize=10, timeout=30):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._pool = queue.Queue(maxsize)

    def acquire(self):
        """从池中取一个连接，没有则新建。"""
        try:
            conn = self._pool.get_nowait()
            if conn.sock is not None:
                try:
                    conn.sock.getpeername()
                    return conn
                except (OSError, AttributeError):
                    pass
            conn.close()
        except queue.Empty:
            pass
        return HTTPConnection(self._host, self._port, timeout=self._timeout)

    def release(self, conn):
        """归还连接，池满则关闭。"""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    def close_all(self):
        while True:
            try:
                self._pool.get_nowait().close()
            except queue.Empty:
                break


# ---------------------------------------------------------------------------
# 静态资源缓存（LRU）
# ---------------------------------------------------------------------------
class StaticCache:
    def __init__(self, max_size=30):
        self._cache = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key, status, headers, body):
        with self._lock:
            if len(self._cache) >= self._max:
                self._cache.popitem(last=False)
            self._cache[key] = (status, headers, body)


_static_cache = StaticCache()


def _is_static_cacheable(method, path):
    if method != 'GET':
        return False
    if path.startswith('/api/'):
        return False
    idx = path.rfind('.')
    if idx < 0:
        return False
    return path[idx + 1:].lower() in STATIC_EXTENSIONS


# ---------------------------------------------------------------------------
# 解压缩工具
# ---------------------------------------------------------------------------
def decompress(data, encoding):
    try:
        if encoding == 'gzip':
            return gzip.decompress(data)
        elif encoding == 'deflate':
            return zlib.decompress(data)
        elif encoding == 'br' and HAS_BROTLI:
            return brotli.decompress(data)
    except Exception as e:
        logging.warning("decompress(%s) failed: %s", encoding, e)
    return None


# ---------------------------------------------------------------------------
# HTML 重写
# ---------------------------------------------------------------------------
def rewrite_html(data):
    """注入 JS polyfill + 重写 src/href/action 绝对路径。"""
    data = data.replace(b'</head>', INJECT_SCRIPT_B + b'</head>', 1)
    data = _RE_HTML_ATTR.sub(rb'\1=\2' + PREFIX.encode() + rb'/', data)
    return data


# ---------------------------------------------------------------------------
# 动态端口发现
# ---------------------------------------------------------------------------
_current_port = INITIAL_PORT
_port_check_time = 0
_port_lock = threading.Lock()


def get_target_port():
    global _current_port, _port_check_time
    with _port_lock:
        now = time.time()
        if CONFIG_PATH and (now - _port_check_time) > 5:
            _port_check_time = now
            try:
                with open(CONFIG_PATH, 'r') as f:
                    m = _RE_CONFIG_PORT.search(f.read())
                    if m:
                        _current_port = int(m.group(1))
            except Exception as e:
                logging.warning("read config port failed: %s", e)
        return _current_port


# ---------------------------------------------------------------------------
# 版本比较
# ---------------------------------------------------------------------------
def _compare_version(v1, v2):
    """返回 1: v2>v1, -1: v2<v1, 0: 相等"""
    p1 = [int(x) for x in v1.split('.')]
    p2 = [int(x) for x in v2.split('.')]
    for i in range(max(len(p1), len(p2))):
        n1 = p1[i] if i < len(p1) else 0
        n2 = p2[i] if i < len(p2) else 0
        if n2 > n1:
            return 1
        if n2 < n1:
            return -1
    return 0


# ---------------------------------------------------------------------------
# 更新逻辑（GitHub API + 下载 + 校验）
# ---------------------------------------------------------------------------

def _fetch_latest_version():
    import urllib.request
    url = "%s/repos/%s/releases/latest" % (UPDATE_API, UPDATE_REPO)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "fnos-qbittorrent-updater",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    version = data.get("tag_name", "").lstrip("v")
    arch_suffix = "-" + CURRENT_ARCH + ".fpk"
    fpk_asset = None
    for a in data.get("assets", []):
        name = a.get("name", "")
        if name.endswith(arch_suffix) and "qbittorrent" in name:
            fpk_asset = a
            break
    if not fpk_asset:
        for a in data.get("assets", []):
            name = a.get("name", "")
            if name.endswith(".fpk") and "qbittorrent" in name:
                fpk_asset = a
                break
    return {
        "version": version,
        "changelog": data.get("body", ""),
        "publishedAt": data.get("published_at", ""),
        "releaseUrl": data.get("html_url", ""),
        "fpkUrl": fpk_asset.get("browser_download_url", "") if fpk_asset else "",
        "fpkSize": fpk_asset.get("size", 0) if fpk_asset else 0,
    }


def _get_current_version():
    paths = []
    appdest = os.environ.get("TRIM_APPDEST", "")
    if appdest:
        paths.append(os.path.join(appdest, "manifest"))
    if CONFIG_PATH:
        parent = os.path.dirname(CONFIG_PATH)
        paths.append(os.path.join(parent, "..", "manifest"))
    paths.append("/var/apps/qbittorrent/manifest")
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    for line in f:
                        if line.strip().startswith("version"):
                            return line.split("=", 1)[1].strip()
        except Exception:
            pass
    v = os.environ.get("TRIM_APPVER", "")
    return v if v else "0.0.0"


def _validate_fpk(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(4)
        if head[:2] == b'\x1f\x8b' or head == b'PK\x03\x04':
            return True, ""
        return False, "内容异常 (%r)" % (head,)
    except Exception as e:
        return False, str(e)


def _download_fpk(url, dest, status, max_size=FPK_MAX_SIZE):
    import urllib.request
    import urllib.error
    tmp = dest + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        return False, "HTTP %d %s" % (e.code, e.reason)
    except urllib.error.URLError as e:
        return False, "网络错误: %s" % (e.reason,)
    except Exception as e:
        return False, "连接失败: %s" % (e,)
    if resp.status != 200:
        resp.close()
        return False, "服务器返回 HTTP %d" % resp.status
    total = int(resp.headers.get("Content-Length", 0))
    if total > max_size:
        resp.close()
        return False, "文件过大 (%.1fMB > %.1fMB)" % (total / 1024 / 1024, max_size / 1024 / 1024)
    try:
        resp.fp.raw._sock.settimeout(30)
    except Exception:
        pass
    downloaded = 0
    try:
        with open(tmp, 'wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > max_size:
                    resp.close()
                    os.remove(tmp)
                    return False, "下载内容超过大小限制"
                if total > 0:
                    pct = 10 + int(downloaded / total * 50)
                    status["progress"] = pct
                    status["message"] = "正在下载... %.1fMB/%.1fMB" % (
                        downloaded / 1024 / 1024, total / 1024 / 1024)
    except Exception as e:
        resp.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, "下载中断: %s" % (e,)
    resp.close()
    if downloaded == 0:
        os.remove(tmp)
        return False, "下载文件为空"
    os.replace(tmp, dest)
    return True, ""


def _perform_update(fpk_url):
    global _update_status
    try:
        _update_status["message"] = "正在准备更新..."
        _update_status["progress"] = 5
        fpk_path = "/tmp/qbittorrent-update.fpk"
        urls = [UPDATE_PROXY + fpk_url, fpk_url]
        success = False
        last_error = ""
        for idx, download_url in enumerate(urls):
            _update_status["message"] = (
                "正在下载更新包..." if idx == 0 else "代理下载失败，尝试直连..."
            )
            _update_status["progress"] = 10
            ok, err = _download_fpk(download_url, fpk_path, _update_status)
            if ok:
                valid, reason = _validate_fpk(fpk_path)
                if valid:
                    success = True
                    break
                else:
                    last_error = "文件校验失败: %s" % reason
                    os.remove(fpk_path)
            else:
                last_error = err
        if not success:
            raise Exception(last_error or "下载失败")
        _update_status["message"] = "下载完成！请点击下方按钮下载 fpk，然后前往 应用中心 → 手动安装 上传"
        _update_status["progress"] = 100
        _update_status["updating"] = False
        _update_status["downloadUrl"] = PREFIX + "/api/update/download"
    except Exception as e:
        _update_status["message"] = "更新失败: %s" % (e,)
        _update_status["progress"] = 0
        _update_status["updating"] = False


_update_status = {"updating": False, "progress": 0, "message": ""}
_update_lock = threading.Lock()
_cached_version = {"expires": 0, "data": None}

# ---------------------------------------------------------------------------
# WebSocket 隧道（双向 TCP 透传）
# ---------------------------------------------------------------------------
def _tunnel_sock(client_sock, backend_sock):
    try:
        while True:
            r, _, _ = select.select([client_sock, backend_sock], [], [], 30)
            if not r:
                break
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                if s is client_sock:
                    backend_sock.sendall(data)
                else:
                    client_sock.sendall(data)
    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass
        try:
            backend_sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 代理请求处理器
# ---------------------------------------------------------------------------
def _is_security_header(key):
    kl = key.lower()
    return kl in (
        "x-frame-options",
        "content-security-policy",
        "cross-origin-opener-policy",
        "cross-origin-embedder-policy",
    )


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    # 共享连接池（类级别，所有实例共用）
    _conn_pool = None

    def _strip_prefix(self):
        path = self.path
        if path.startswith(PREFIX):
            path = path[len(PREFIX):] or "/"
        return path

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_api(self, path):
        if path == "/api/update/check":
            try:
                global _cached_version
                now = time.time()
                if _cached_version["data"] and _cached_version["expires"] > now:
                    result = _cached_version["data"]
                else:
                    info = _fetch_latest_version()
                    cur = _get_current_version()
                    has_update = _compare_version(cur, info["version"]) > 0
                    result = {
                        "success": True,
                        "currentVersion": cur,
                        "latestVersion": info["version"],
                        "hasUpdate": has_update,
                        "changelog": info["changelog"],
                        "publishedAt": info["publishedAt"],
                        "releaseUrl": info["releaseUrl"],
                        "fpkUrl": info["fpkUrl"],
                        "arch": CURRENT_ARCH,
                        "message": "发现新版本" if has_update else "已是最新版本",
                    }
                    _cached_version = {"expires": now + 300, "data": result}
                self._send_json(200, result)
            except Exception as e:
                logging.error("update/check failed: %s", traceback.format_exc())
                self._send_json(500, {"success": False, "error": str(e)})
            return True

        if path == "/api/update/install":
            if self.command != "POST":
                self._send_json(405, {"success": False, "error": "Method not allowed"})
                return True
            with _update_lock:
                if _update_status["updating"]:
                    self._send_json(409, {"success": False, "error": "正在更新中，请稍候"})
                    return True
                try:
                    info = _fetch_latest_version()
                    if not info["fpkUrl"]:
                        self._send_json(400, {"success": False, "error": "未找到更新包"})
                        return True
                    _update_status["updating"] = True
                    _update_status["progress"] = 0
                    _update_status["message"] = "准备更新..."
                    _update_status["latestVersion"] = info["version"]
                    _update_status["fpkFilename"] = (
                        info["fpkUrl"].rsplit('/', 1)[-1] if info["fpkUrl"] else ""
                    )
                except Exception as e:
                    # 网络请求失败时释放锁
                    self._send_json(500, {"success": False, "error": str(e)})
                    return True
            self._send_json(200, {"success": True, "message": "开始下载更新"})
            t = threading.Thread(target=_perform_update, args=(info["fpkUrl"],))
            t.daemon = True
            t.start()
            return True

        if path == "/api/update/status":
            self._send_json(200, {"success": True, **_update_status})
            return True

        if path == "/api/update/download":
            fpk_path = "/tmp/qbittorrent-update.fpk"
            if not os.path.exists(fpk_path):
                self._send_json(404, {"success": False, "error": "更新包不存在，请先点击一键更新"})
                return True
            try:
                filename = (
                    _update_status.get("fpkFilename", "")
                    or ("qbittorrent-vuetorrent-%s.fpk" % (
                        _update_status.get("latestVersion", "") or _get_current_version()
                    ))
                )
                sz = os.path.getsize(fpk_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", "attachment; filename=%s" % filename)
                self.send_header("Content-Length", str(sz))
                self.end_headers()
                with open(fpk_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception as e:
                logging.error("update/download failed: %s", traceback.format_exc())
                self._send_json(500, {"success": False, "error": str(e)})
            return True

        return False

    def do_request(self):
        # /prefix → /prefix/ 重定向
        if self.path == PREFIX:
            self.send_response(301)
            self.send_header("Location", PREFIX + "/")
            self.end_headers()
            return

        # WebSocket 升级
        upgrade = self.headers.get("Upgrade", "").lower()
        if upgrade == "websocket":
            self._handle_ws()
            return

        path = self._strip_prefix()

        # API 路由
        if path.startswith("/api/update/"):
            if self._handle_api(path):
                return

        # VueTorrent 健康检查
        if path == "/backend/ping":
            self._send_json(200, {"success": True, "version": "pong"})
            return

        is_head = self.command == "HEAD"
        port = get_target_port()
        pool = ProxyHandler._conn_pool

        # 从连接池获取连接
        if pool:
            conn = pool.acquire()
        else:
            conn = HTTPConnection(TARGET_HOST, port, timeout=30)

        # 构造转发请求头
        headers = {}
        skip_headers = frozenset({
            "host", "connection", "transfer-encoding",
            "accept-encoding", "origin", "referer",
        })
        for key, value in self.headers.items():
            if key.lower() not in skip_headers:
                headers[key] = value

        backend_url = "http://%s:%d" % (TARGET_HOST, port)
        headers["Host"] = "%s:%d" % (TARGET_HOST, port)
        headers["Origin"] = backend_url
        referer = self.headers.get("Referer", "")
        if referer:
            headers["Referer"] = _RE_REFERER.sub(backend_url, referer)
        headers["Accept-Encoding"] = "gzip, deflate"

        # Cookie 透传（LocalHostAuth=false 跳过认证）
        browser_cookie = self.headers.get("Cookie", "")
        if browser_cookie:
            headers["Cookie"] = browser_cookie

        # 读取请求 body
        content_length = self.headers.get("Content-Length")
        body = None
        if content_length:
            body = self.rfile.read(int(content_length))

        # 静态缓存命中检查
        cache_key = self.command + ":" + path
        cacheable = _is_static_cacheable(self.command, path)
        if cacheable:
            cached = _static_cache.get(cache_key)
            if cached:
                c_status, c_headers, c_body = cached
                self.send_response(c_status)
                for k, v in c_headers:
                    self.send_header(k, v)
                if not is_head:
                    self.send_header("Content-Length", str(len(c_body)))
                    self.end_headers()
                    self.wfile.write(c_body)
                else:
                    # HEAD: 不返回 body，但保留 Content-Length
                    self.send_header("Content-Length", str(len(c_body)))
                    self.end_headers()
                if pool:
                    pool.release(conn)
                else:
                    conn.close()
                return

        # 转发请求到后端
        try:
            conn.request(self.command, path, body, headers)
            resp = conn.getresponse()
        except ConnectionError as e:
            # 连接池可能返回了 half-close 的失效连接（RemoteDisconnected）
            # 用全新连接重试一次
            logging.warning("request failed, retry with fresh connection: %s %s -> %s",
                           self.command, path, e)
            conn.close()
            fresh = HTTPConnection(TARGET_HOST, port, timeout=30)
            try:
                fresh.request(self.command, path, body, headers)
                resp = fresh.getresponse()
                conn = fresh  # 后续 release 时 conn 指向新连接
            except Exception as e2:
                logging.error("request failed (after retry): %s %s -> %s",
                              self.command, path, e2)
                self.send_error(502, str(e2))
                fresh.close()
                return
        except Exception as e:
            logging.error("request failed: %s %s -> %s", self.command, path, e)
            self.send_error(502, str(e))
            if pool:
                conn.close()  # 出错的连接不归还池
            else:
                conn.close()
            return

        try:
            all_resp_headers = resp.getheaders()
            is_html = any(
                "text/html" in v for k, v in all_resp_headers
                if k.lower() == "content-type"
            )
            if resp.status >= 400:
                logging.warning("upstream HTTP %d for %s %s", resp.status, self.command, path)

            content_encoding = next(
                (v for k, v in all_resp_headers if k.lower() == "content-encoding"),
                None,
            )

            # 发送状态行
            self.send_response(resp.status)

            # 过滤并发送响应头
            for key, value in all_resp_headers:
                kl = key.lower()
                # 移除 iframe 阻止安全头
                if _is_security_header(kl):
                    continue
                # Cookie 剥离 SameSite
                if kl == "set-cookie":
                    self.send_header(key, _RE_SAME_COOKIE_ATTR.sub('', value))
                    continue
                # HTML 时自行处理 Content-Encoding
                if kl == "content-encoding" and is_html:
                    continue
                # 跳过 hop-by-hop
                if kl in ("transfer-encoding", "connection", "content-length"):
                    continue
                self.send_header(key, value)

            # 读取并处理响应 body
            if is_html:
                data = resp.read()
                if content_encoding:
                    raw = decompress(data, content_encoding)
                    if raw is not None:
                        data = raw
                data = rewrite_html(data)
                if not is_head:
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    # HEAD: 告诉客户端如果 GET 会有多大
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
            else:
                data = resp.read()
                # 缓存静态资源
                if cacheable and 200 <= resp.status < 300:
                    ch = [
                        (k, v) for k, v in all_resp_headers
                        if k.lower() not in (
                            'transfer-encoding', 'connection',
                            'content-length', 'set-cookie',
                        )
                    ]
                    _static_cache.set(cache_key, resp.status, ch, data)
                if not is_head:
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
        except Exception:
            logging.error("unhandled in do_request %s %s:\n%s",
                          self.command, path, traceback.format_exc())
        finally:
            if pool:
                pool.release(conn)
            else:
                conn.close()

    def _handle_ws(self):
        path = self._strip_prefix()
        port = get_target_port()

        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend.settimeout(10)
        try:
            backend.connect((TARGET_HOST, port))
        except Exception as e:
            backend.close()
            self.send_error(502, str(e))
            return

        ws_key = self.headers.get("Sec-WebSocket-Key", "")
        ws_ver = self.headers.get("Sec-WebSocket-Version", "13")
        ws_proto = self.headers.get("Sec-WebSocket-Protocol", "")

        req_line = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "%s"
            "Sec-WebSocket-Version: %s\r\n"
            "%s"
            "Origin: http://%s:%d\r\n"
        ) % (
            path,
            TARGET_HOST, port,
            "Sec-WebSocket-Key: %s\r\n" % ws_key if ws_key else "",
            ws_ver,
            "Sec-WebSocket-Protocol: %s\r\n" % ws_proto if ws_proto else "",
            TARGET_HOST, port,
        )

        # 透传其他请求头
        skip_ws = frozenset({
            "host", "connection", "upgrade", "sec-websocket-key",
            "sec-websocket-version", "sec-websocket-protocol",
            "origin", "cookie",
        })
        for key, value in self.headers.items():
            if key.lower() not in skip_ws:
                req_line += "%s: %s\r\n" % (key, value)
        req_line += "\r\n"

        try:
            backend.sendall(req_line.encode())
        except Exception as e:
            backend.close()
            self.send_error(502, str(e))
            return

        # 读取后端响应
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = backend.recv(4096)
            if not chunk:
                backend.close()
                self.send_error(502, "backend closed")
                return
            resp += chunk

        hdr_end = resp.index(b"\r\n\r\n")
        hdr_raw = resp[:hdr_end].decode("utf-8", errors="replace")
        remaining = resp[hdr_end + 4:]

        status_line = hdr_raw.split("\r\n")[0]
        parts = status_line.split(" ", 2)
        status_code = int(parts[1]) if len(parts) >= 2 else 101

        self.send_response(status_code)
        for line in hdr_raw.split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                self.send_header(k.strip(), v.strip())
        self.end_headers()

        if remaining:
            self.wfile.write(remaining)
            self.wfile.flush()

        client_raw = self.connection
        backend.setblocking(True)
        client_raw.setblocking(True)

        t = threading.Thread(target=_tunnel_sock, args=(client_raw, backend))
        t.daemon = True
        t.start()

    def do_GET(self):
        self.do_request()

    def do_POST(self):
        self.do_request()

    def do_PUT(self):
        self.do_request()

    def do_DELETE(self):
        self.do_request()

    def do_HEAD(self):
        self.do_request()

    def do_PATCH(self):
        self.do_request()

    def do_OPTIONS(self):
        self.do_request()

    def log_message(self, format, *args):
        logging.info(format % args)


# ---------------------------------------------------------------------------
# Unix socket 服务器（线程池版）
# ---------------------------------------------------------------------------
class ThreadedUnixHTTPServer(http.server.HTTPServer):
    address_family = socket.AF_UNIX

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=20, thread_name_prefix="proxy"
        )

    def server_bind(self):
        self.socket.bind(self.server_address)
        os.chmod(self.server_address, 0o666)

    def process_request(self, request, client_address):
        self._executor.submit(self._handle, request, client_address)

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def server_close(self):
        self._executor.shutdown(wait=False)
        super().server_close()


# ---------------------------------------------------------------------------
# 信号处理
# ---------------------------------------------------------------------------
def cleanup(signum, frame):
    logging.info("received signal %d, shutting down", signum)
    if hasattr(server, '_executor'):
        server._executor.shutdown(wait=False)
    server.server_close()
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
    sys.exit(0)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not SOCK_PATH:
        logging.error("Usage: gateway-proxy.py <socket_path> <target_host> <initial_port> [config_path]")
        sys.exit(1)

    # 初始化连接池
    ProxyHandler._conn_pool = ConnectionPool(TARGET_HOST, INITIAL_PORT, maxsize=10, timeout=30)

    # 清理残留 socket
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)

    server = ThreadedUnixHTTPServer(SOCK_PATH, ProxyHandler)
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    logging.info("gateway-proxy started: %s -> %s:%d", SOCK_PATH, TARGET_HOST, INITIAL_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    server.server_close()
    if ProxyHandler._conn_pool:
        ProxyHandler._conn_pool.close_all()
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
