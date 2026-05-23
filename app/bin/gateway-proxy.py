#!/usr/bin/env python3
import http.server, socket, sys, os, signal, re, time, threading, gzip, zlib, select, traceback, json
from http.client import HTTPConnection


from collections import OrderedDict

# 静态资源缓存（JS/CSS/图片等）
class _StaticCache:
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
_static_cache = _StaticCache()

def _is_static_cacheable(method, path):
    """GET请求、非API路径、有常见静态扩展名 → 可缓存"""
    if method != 'GET':
        return False
    if path.startswith('/api/'):
        return False
    ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    return ext in ('js','css','png','jpg','jpeg','gif','svg','ico','woff','woff2','ttf','eot')

SOCK_PATH = sys.argv[1]
TARGET_HOST = sys.argv[2]
INITIAL_PORT = int(sys.argv[3])
CONFIG_PATH = sys.argv[4] if len(sys.argv) > 4 else None
PREFIX = "/app/qbittorrent"

def log(msg):
    sys.stderr.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))

_current_port = INITIAL_PORT
_port_check_time = 0
_port_lock = threading.Lock()

INJECT_SCRIPT = b'''<script>
(function(){
var P="/app/qbittorrent";
var _f=window.fetch;
window.fetch=function(u,o){
if(typeof u==='string'&&u.charAt(0)==='/'&&!u.startsWith(P)){u=P+u;}
return _f.call(this,u,o);
};
var _o=XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open=function(m,u,s){
if(typeof u==='string'&&u.charAt(0)==='/'&&!u.startsWith(P)){arguments[1]=P+u;}
return _o.apply(this,arguments);
};
var _cw=window.WebSocket;
if(_cw){
window.WebSocket=function(u,p){
if(typeof u==='string'&&u.charAt(0)==='/'&&!u.startsWith(P)){
var _proto=location.protocol==='https:'?'wss:':'ws:';
u=_proto+'//'+location.host+P+u;
}
else if(typeof u==='string'&&u.startsWith('ws')){
var r=new RegExp('^(wss?)://([^/]+)(/.*)$');
var m=u.match(r);
if(m&&!m[3].startsWith(P)){u=m[1]+'://'+m[2]+P+m[3];}
}
return p?new _cw(u,p):new _cw(u);
};
window.WebSocket.prototype=_cw.prototype;
window.WebSocket.CONNECTING=_cw.CONNECTING;
window.WebSocket.OPEN=_cw.OPEN;
window.WebSocket.CLOSING=_cw.CLOSING;
window.WebSocket.CLOSED=_cw.CLOSED;
}
try{
var _td=Object.getOwnPropertyDescriptor(top,'location');
if(_td&&_td.set){
Object.defineProperty(top,'location',{
set:function(v){console.warn('[qB] Blocked top.location:',v);},
get:function(){return window.location;}
});
}
}catch(e){}
setInterval(function(){
try{
document.querySelectorAll('.overlay,.desktop-overlay,#overlay,.MuiDialog-root').forEach(function(el){el.style.display='none';});
}catch(ex){}
},500);
})();
</script>'''

def decompress(data, encoding):
    try:
        if encoding == 'gzip':
            return gzip.decompress(data)
        elif encoding == 'deflate':
            return zlib.decompress(data)
        elif encoding == 'br':
            import brotli
            return brotli.decompress(data)
    except Exception:
        pass
    return None

def rewrite_html(data, prefix):
    p = prefix.encode()
    # 注入统一修复脚本（fetch/XHR/WebSocket 前缀 + 反逃逸 + 覆盖层清除）
    data = data.replace(b'</head>', INJECT_SCRIPT + b'</head>', 1)
    # 重写 HTML 属性中的绝对路径（跳过已带前缀的路径防重复）
    data = re.sub(rb'(src|href|action)=([\'"])/(?!/?(?:app|cgi)/)', rb'\1=\2' + p + rb'/', data)
    return data

def get_target_port():
    global _current_port, _port_check_time
    with _port_lock:
        now = time.time()
        if CONFIG_PATH and (now - _port_check_time) > 5:
            _port_check_time = now
            try:
                with open(CONFIG_PATH, 'r') as f:
                    for line in f:
                        m = re.match(r'^WebUI\\Port=(\d+)', line.strip())
                        if m:
                            _current_port = int(m.group(1))
                            break
            except Exception:
                pass
        return _current_port

if os.path.exists(SOCK_PATH):
    os.unlink(SOCK_PATH)

# 检测当前架构（用于更新包匹配）
import platform as _platform
_RAW_ARCH = _platform.machine()
if _RAW_ARCH in ('aarch64', 'arm64', 'armv8l'):
    CURRENT_ARCH = 'arm64'
else:
    CURRENT_ARCH = 'amd64'

# === Update Check API ===
UPDATE_REPO = "sushazhi/fnos-qbittorrent"
UPDATE_API = "https://api.github.com"
UPDATE_PROXY = "https://ghfast.top/"
_update_status = {"updating": False, "progress": 0, "message": ""}
_update_lock = threading.Lock()
_cached_version = {"expires": 0, "data": None}

def _compare_version(v1, v2):
    p1 = [int(x) for x in v1.split('.')]
    p2 = [int(x) for x in v2.split('.')]
    for i in range(max(len(p1), len(p2))):
        n1 = p1[i] if i < len(p1) else 0
        n2 = p2[i] if i < len(p2) else 0
        if n2 > n1: return 1
        if n2 < n1: return -1
    return 0

def _fetch_latest_version():
    import urllib.request
    url = f"{UPDATE_API}/repos/{UPDATE_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "fnos-qbittorrent-updater", "Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    version = data.get("tag_name", "").lstrip("v")
    # 按当前架构匹配更新包（避免 arm 机器下载到 amd64 的包）
    arch_suffix = "-" + CURRENT_ARCH + ".fpk"
    fpk_asset = None
    for a in data.get("assets", []):
        name = a.get("name", "")
        if name.endswith(arch_suffix) and "qbittorrent" in name:
            fpk_asset = a
            break
    # fallback：未找到架构匹配时取第一个 .fpk
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
        "fpkSize": fpk_asset.get("size", 0) if fpk_asset else 0
    }

def _get_current_version():
    possible_paths = []
    appdest = os.environ.get("TRIM_APPDEST", "")
    if appdest:
        possible_paths.append(os.path.join(appdest, "manifest"))
    if CONFIG_PATH:
        parent = os.path.dirname(CONFIG_PATH)
        possible_paths.append(os.path.join(parent, "..", "manifest"))
    possible_paths.append("/var/apps/qbittorrent/manifest")
    for p in possible_paths:
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
            return False, f"内容异常 ({repr(head)})"
    except Exception as e:
        return False, str(e)

def _download_fpk(url, dest, status, max_size=100*1024*1024):
    import urllib.request, urllib.error
    tmp = dest + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"网络错误: {e.reason}"
    except Exception as e:
        return False, f"连接失败: {e}"
    if resp.status != 200:
        resp.close()
        return False, f"服务器返回 HTTP {resp.status}"
    total = int(resp.headers.get("Content-Length", 0))
    if total > max_size:
        resp.close()
        return False, f"文件过大 ({total/1024/1024:.1f}MB > {max_size/1024/1024:.1f}MB)"
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
                    status["message"] = f"正在下载... {downloaded/1024/1024:.1f}MB/{total/1024/1024:.1f}MB"
    except Exception as e:
        resp.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, f"下载中断: {e}"
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
        update_dir = "/tmp"
        fpk_path = os.path.join(update_dir, "qbittorrent-update.fpk")
        urls = [UPDATE_PROXY + fpk_url, fpk_url]
        success = False
        last_error = ""
        for idx, download_url in enumerate(urls):
            _update_status["message"] = "正在下载更新包..." if idx == 0 else "代理下载失败，尝试直连..."
            _update_status["progress"] = 10 if idx == 0 else 10
            ok, err = _download_fpk(download_url, fpk_path, _update_status)
            if ok:
                valid, reason = _validate_fpk(fpk_path)
                if valid:
                    success = True
                    break
                else:
                    last_error = f"文件校验失败: {reason}"
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
        _update_status["message"] = f"更新失败: {e}"
        _update_status["progress"] = 0
        _update_status["updating"] = False


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


class ProxyHandler(http.server.BaseHTTPRequestHandler):
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
                        "message": "发现新版本" if has_update else "已是最新版本"
                    }
                    _cached_version = {"expires": now + 300, "data": result}
                self._send_json(200, result)
            except Exception as e:
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
                    _update_status["fpkFilename"] = info["fpkUrl"].rsplit('/', 1)[-1] if info["fpkUrl"] else ""
                except Exception as e:
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
                filename = _update_status.get("fpkFilename", "") or (f"qbittorrent-vuetorrent-{_update_status.get('latestVersion', '') or _get_current_version()}.fpk")
                sz = os.path.getsize(fpk_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename={filename}")
                self.send_header("Content-Length", str(sz))
                self.end_headers()
                with open(fpk_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return True

        return False

    def do_request(self):
        if self.path == PREFIX:
            self.send_response(301)
            self.send_header("Location", PREFIX + "/")
            self.end_headers()
            return

        upgrade = self.headers.get("Upgrade", "").lower()
        if upgrade == "websocket":
            self._handle_ws()
            return

        path = self._strip_prefix()

        if path.startswith("/api/update/"):
            if self._handle_api(path):
                return

        # VueTorrent 健康检查端点，qBittorrent 无此路径
        if path == "/backend/ping":
            self._send_json(200, {"success": True, "version": "pong"})
            return

        port = get_target_port()

        conn = HTTPConnection(TARGET_HOST, port, timeout=30)

        headers = {}
        for key, value in self.headers.items():
            kl = key.lower()
            if kl in ("host", "connection", "transfer-encoding", "accept-encoding", "origin", "referer"):
                continue
            headers[key] = value
        headers["Host"] = "{}:{}".format(TARGET_HOST, port)
        backend_origin = "http://{}:{}".format(TARGET_HOST, port)
        headers["Origin"] = backend_origin
        referer = self.headers.get("Referer", "")
        if referer:
            headers["Referer"] = re.sub(r'^https?://[^/]+', backend_origin, referer)
        headers["Accept-Encoding"] = "gzip, deflate"

        # 直接透传浏览器原有 Cookie，proxy 不做任何 SID 管理
        # qBittorrent 的 LocalHostAuth=true 会自动处理本地请求的认证
        browser_cookie = self.headers.get("Cookie", "")
        if browser_cookie:
            headers["Cookie"] = browser_cookie

        content_length = self.headers.get("Content-Length")
        body = None
        if content_length:
            body = self.rfile.read(int(content_length))

        # 静态资源缓存命中检查
        cache_key = self.command + ":" + path
        cacheable = _is_static_cacheable(self.command, path)
        if cacheable:
            cached = _static_cache.get(cache_key)
            if cached:
                c_status, c_headers, c_body = cached
                self.send_response(c_status)
                for k, v in c_headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(c_body)))
                self.end_headers()
                self.wfile.write(c_body)
                conn.close()
                return

        try:
            conn.request(self.command, path, body, headers)
            resp = conn.getresponse()
        except Exception as e:
            log("conn.request/getresponse failed: %s %s -> %s" % (self.command, path, e))
            self.send_error(502, str(e))
            conn.close()
            return

        try:
            all_resp_headers = resp.getheaders()
            is_html = any("text/html" in v for k, v in all_resp_headers if k.lower() == "content-type")
            if resp.status >= 400:
                log("upstream returned HTTP %d for %s %s" % (resp.status, self.command, path))
            content_encoding = next((v for k, v in all_resp_headers if k.lower() == "content-encoding"), None)

            self.send_response(resp.status)

            for key, value in all_resp_headers:
                kl = key.lower()
                # 移除阻止 iframe 嵌入的安全头
                if kl in ("x-frame-options", "content-security-policy", "cross-origin-opener-policy", "cross-origin-embedder-policy"):
                    continue
                # 处理 Cookie：剥离 SameSite 属性以兼容 iframe
                if kl == "set-cookie":
                    new_value = re.sub(r';\s*SameSite\s*=\s*[^;\s]+', '', value, flags=re.IGNORECASE)
                    self.send_header(key, new_value)
                    continue
                # 内容编码由我们自行处理（解压 HTML 后不重新编码）
                if kl == "content-encoding" and is_html:
                    continue
                if kl in ("transfer-encoding", "connection", "content-length"):
                    continue
                self.send_header(key, value)

            if is_html:
                data = resp.read()
                if content_encoding:
                    raw = decompress(data, content_encoding)
                    if raw is not None:
                        data = raw
                data = rewrite_html(data, PREFIX)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                # 读取完整响应体（用于缓存 + 流式回写）
                data = resp.read()
                # 缓存静态资源
                if cacheable and 200 <= resp.status < 300:
                    ch = [(k, v) for k, v in all_resp_headers
                          if k.lower() not in ('transfer-encoding','connection','content-length','set-cookie')]
                    _static_cache.set(cache_key, resp.status, ch, data)
                # 发送
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception:
            log("unhandled exception in do_request %s %s:\n%s" % (self.command, path, traceback.format_exc()))
        finally:
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

        req_line = "GET {} HTTP/1.1\r\n".format(path)
        req_line += "Host: {}:{}\r\n".format(TARGET_HOST, port)
        req_line += "Upgrade: websocket\r\n"
        req_line += "Connection: Upgrade\r\n"
        if ws_key:
            req_line += "Sec-WebSocket-Key: {}\r\n".format(ws_key)
        req_line += "Sec-WebSocket-Version: {}\r\n".format(ws_ver)
        if ws_proto:
            req_line += "Sec-WebSocket-Protocol: {}\r\n".format(ws_proto)
        req_line += "Origin: http://{}:{}\r\n".format(TARGET_HOST, port)
        for key, value in self.headers.items():
            kl = key.lower()
            if kl in ("host", "connection", "upgrade", "sec-websocket-key",
                      "sec-websocket-version", "sec-websocket-protocol", "origin", "cookie"):
                continue
            req_line += "{}: {}\r\n".format(key, value)
        req_line += "\r\n"

        try:
            backend.sendall(req_line.encode())
        except Exception as e:
            backend.close()
            self.send_error(502, str(e))
            return

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

        resp_hdrs = []
        for line in hdr_raw.split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                resp_hdrs.append((k.strip(), v.strip()))

        self.send_response(status_code)
        for k, v in resp_hdrs:
            self.send_header(k, v)
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

    def do_GET(self): self.do_request()
    def do_POST(self): self.do_request()
    def do_PUT(self): self.do_request()
    def do_DELETE(self): self.do_request()
    def do_HEAD(self): self.do_request()
    def do_PATCH(self): self.do_request()
    def do_OPTIONS(self): self.do_request()

    def log_message(self, format, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


class ThreadedUnixHTTPServer(http.server.HTTPServer):
    address_family = socket.AF_UNIX

    def server_bind(self):
        self.socket.bind(self.server_address)
        os.chmod(self.server_address, 0o666)

    def process_request(self, request, client_address):
        t = threading.Thread(target=self._handle, args=(request, client_address))
        t.daemon = True
        t.start()

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def cleanup(signum, frame):
    server.server_close()
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
    sys.exit(0)


server = ThreadedUnixHTTPServer(SOCK_PATH, ProxyHandler)
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

log("gateway-proxy started: %s -> %s:%d" % (SOCK_PATH, TARGET_HOST, _current_port))
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass

server.server_close()
if os.path.exists(SOCK_PATH):
    os.unlink(SOCK_PATH)
