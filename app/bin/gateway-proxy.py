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
import logging
from http.client import HTTPConnection
from collections import OrderedDict

# 懒加载模块：仅在需要时才导入
_queue = None
def _get_queue():
    global _queue
    if _queue is None:
        import queue
        _queue = queue
    return _queue

_concurrent_futures = None
def _get_concurrent_futures():
    global _concurrent_futures
    if _concurrent_futures is None:
        import concurrent.futures
        _concurrent_futures = concurrent.futures
    return _concurrent_futures

# ---------------------------------------------------------------------------
# brotli 可选支持（懒加载）
# ---------------------------------------------------------------------------
_brotli = None
HAS_BROTLI = False
def _get_brotli():
    global _brotli, HAS_BROTLI
    if _brotli is None:
        try:
            import brotli as _br
            _brotli = _br
            HAS_BROTLI = True
        except ImportError:
            _brotli = False
    return _brotli if HAS_BROTLI else None

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
UPDATE_PROXY_MAIN = "https://gh-proxy.com/"
UPDATE_PROXY_BACKUP = "https://gh-proxy.org/"
STATIC_EXTENSIONS = frozenset({
    'js', 'css', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico',
    'woff', 'woff2', 'ttf', 'eot',
})
FPK_MAX_SIZE = 100 * 1024 * 1024  # 100 MB
DOWNLOAD_TIMEOUT = 120  # 总下载超时 2 分钟

# ---------------------------------------------------------------------------
# 架构检测
# ---------------------------------------------------------------------------
import platform as _platform
_RAW_ARCH = _platform.machine()
if _RAW_ARCH in ('aarch64', 'arm64', 'armv8l'):
    CURRENT_ARCH = 'arm64'
else:
    CURRENT_ARCH = 'amd64'

# 优先使用 fnOS 平台环境变量
_CURRENT_VERSION = os.environ.get("TRIM_APPVER", "0.0.0")

# ---------------------------------------------------------------------------
# 注入脚本（模块级构建模板，update-check.js 延迟加载）
# ---------------------------------------------------------------------------
_UPDATE_CHECK_JS_CACHED = None

# 浏览器兼容性检测脚本（纯 ES5，插入到所有 polyfill 之前）：
# VueTorrent 使用 <script type="module"> + 现代 JS 语法（?. / .at() / replaceAll 等），
# 旧内核浏览器会静默忽略 module 标签导致页面全白且无任何报错。
# 这里在内核过旧时显示明确提示，避免"一片空白"无从排查。
# 注意：本段独立于 _INJECT_SCRIPT_TEMPLATE（不参与 % 格式化），内部可放心使用 % 字符。
_COMPAT_SCRIPT = (
    '<script>'
    '(function(){'
    'function __qbModernOk(){'
    'try{'
    'return ("noModule" in document.createElement("script"))'
    '&& typeof Array.prototype.at === "function"'
    '&& typeof String.prototype.replaceAll === "function"'
    '&& typeof structuredClone === "function";'
    '}catch(e){return false;}'
    '}'
    'function __qbShowCompatWarn(){'
    'try{'
    'if(document.getElementById("__qbCompatWarn")){return;}'
    'var d=document.createElement("div");'
    'd.setAttribute("id","__qbCompatWarn");'
    'd.style.cssText="position:fixed;left:0;top:0;right:0;bottom:0;z-index:2147483647;'
    'background:#f1f5f9;color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,\\"Segoe UI\\",\\"Microsoft YaHei\\",sans-serif;'
    'display:flex;align-items:center;justify-content:center;padding:24px;";'
    'var i=document.createElement("div");'
    'i.style.cssText="max-width:560px;width:100%;background:#fff;border-radius:12px;'
    'box-shadow:0 8px 30px rgba(0,0,0,.12);padding:28px 32px;text-align:center;";'
    'var h=document.createElement("h2");'
    'h.style.cssText="margin:0 0 12px;font-size:19px;color:#dc2626;line-height:1.5;";'
    'h.textContent="当前浏览器内核过旧，无法加载 qBittorrent 界面";'
    'var p=document.createElement("p");'
    'p.style.cssText="margin:0;font-size:14px;line-height:1.9;color:#334155;";'
    'p.innerHTML="您的浏览器不支持界面所需的现代 Web 特性（ES Module 等）。<br>'
    '请使用最新版 <b>Chrome</b> 或 <b>Edge</b> 访问，或升级浏览器后再打开。<br><br>'
    '如需在旧内核下继续使用，可临时改为 qBittorrent 原生界面（兼容性更好）：<br>'
    '1. 编辑 <code>qBittorrent.conf</code>，把 <code>WebUI\\\\AlternativeUIEnabled</code> 改为 <code>false</code>；<br>'
    '2. 在应用中心停止并重新启动 qBittorrent。";'
    'i.appendChild(h);i.appendChild(p);'
    'd.appendChild(i);'
    '(document.body||document.documentElement).appendChild(d);'
    '}catch(e){}'
    '}'
    'if(!__qbModernOk()){'
    'if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",__qbShowCompatWarn);}'
    'else{__qbShowCompatWarn();}'
    '}'
    '})();'
    '</script>'
)

def _get_update_check_js():
    global _UPDATE_CHECK_JS_CACHED
    if _UPDATE_CHECK_JS_CACHED is not None:
        return _UPDATE_CHECK_JS_CACHED
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ui', 'update-check.js'), 'r', encoding='utf-8') as _f:
            _UPDATE_CHECK_JS_CACHED = _f.read()
    except Exception:
        _UPDATE_CHECK_JS_CACHED = '/* update-check.js not found */'
    return _UPDATE_CHECK_JS_CACHED

_INJECT_SCRIPT_TEMPLATE = (
    '<script>window.QBITTORRENT_APP_ARCH="%s";window.QBITTORRENT_APP_VERSION="%s";</script><script>'
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
    '<script>'
    '(function(){'
    '/* __QB_CLIPBOARD_FALLBACK__：'
    ' * 1) http 非安全上下文下 navigator.clipboard 可能为 undefined；'
    ' * 2) iframe 内 clipboard-write 权限不足时 writeText 会 reject。'
    ' * 两种情况都会让 VueTorrent 复制 Web API Key 抛错 → toast.copy.error。'
    ' * 这里统一兜底到 document.execCommand("copy")（用户手势下可用）。 */'
    'function __qbLegacyCopy(text){'
      'var ok=false;'
      'try{'
        'var ta=document.createElement("textarea");'
        'ta.value=text;'
        'ta.style.position="fixed";'
        'ta.style.top="0";'
        'ta.style.left="0";'
        'ta.style.width="2em";'
        'ta.style.height="2em";'
        'ta.style.padding="0";'
        'ta.style.border="none";'
        'ta.style.outline="none";'
        'ta.style.boxShadow="none";'
        'ta.style.background="transparent";'
        'ta.setAttribute("readonly","");'
        'document.body.appendChild(ta);'
        'ta.focus();'
        'ta.select();'
        'ta.setSelectionRange(0,ta.value.length);'
        'ok=document.execCommand("copy");'
        'document.body.removeChild(ta);'
      '}catch(e){}'
      'return ok;'
    '}'
    '/* 兜底复制入口：优先原生 writeText，失败再回退 execCommand */'
    'function __qbCopyWithFallback(text){'
      'var np=null;'
      'try{np=navigator.clipboard;}catch(e){}'
      'if(np&&typeof np.writeText==="function"){'
        'try{'
          'return np.writeText(text).then(function(){return true;},function(){'
            'return __qbLegacyCopy(text);'
          '});'
        '}catch(e){'
          'return Promise.resolve(__qbLegacyCopy(text));'
        '}'
      '}'
      'return Promise.resolve(__qbLegacyCopy(text));'
    '}'
    'window.__qbCopyText=function(text){return __qbCopyWithFallback(text);};'
    '/* 让 navigator.clipboard 始终存在且 writeText 始终可用（覆盖非安全上下文 & iframe 权限不足） */'
    'try{'
      'if(typeof navigator==="undefined"){navigator={};}'
      'if(!navigator.clipboard){navigator.clipboard={};}'
      'var _clip=navigator.clipboard;'
      'var _origWrite=_clip.writeText;'
      '_clip.writeText=function(text){'
        'if(_origWrite&&typeof _origWrite==="function"){'
          'try{'
            'return _origWrite.call(_clip,text).then(function(){return true;},function(){'
              'return __qbLegacyCopy(text);'
            '});'
          '}catch(e){'
            'return Promise.resolve(__qbLegacyCopy(text));'
          '}'
        '}'
        'return Promise.resolve(__qbLegacyCopy(text));'
      '};'
    '}catch(e){}'
    '})();'
    '</script>'
    '<script>'
    '(function(){'
    '/* __QB_UPDATE_CHECK__ */'
    'if(window.self!==window.top){'
    'try{'
    'var fe=window.frameElement;'
    'if(!fe){return;}'
    'var P="' + PREFIX + '";'
    'var _dlPath="";'
    'var _dlPathDisplay="";'
    'var _titleBase="qBittorrent";'
    ''
    '/* ===== 0. 最小化 Penpal 桥接：连接 fnOS 宿主 ===== */'
    'var __qbSdk=(function(){'
      'var connected=false;'
      'var methods={};'
      'var pending={};'
      'var msgId=1;'
      'var listeners={};'
      'var _cbId=1;'
      ''
      'function connect(){'
        'window.parent.postMessage({penpal:"syn"},"*");'
        'setTimeout(function(){'
          'if(!connected){'
            'window.__QB_SDK_READY=true;'
            'window.dispatchEvent(new Event("qb-sdk-ready"));'
          '}'
        '},1500);'
      '}'
      ''
      'window.addEventListener("message",function(ev){'
        'var d=ev.data;'
        'if(!d||!d.penpal)return;'
        'if(d.penpal==="synAck"){'
          'methods=d.methodNames||[];'
          'window.parent.postMessage({penpal:"ack",methodNames:[],config:{}},"*");'
          'connected=true;'
          'window.__QB_SDK_READY=true;'
          'window.dispatchEvent(new Event("qb-sdk-ready"));'
        '}else if(d.penpal==="reply"){'
          'var cb=pending[d.id];'
          'if(cb){'
            'delete pending[d.id];'
            'if(d.resolution==="fulfilled"){cb.resolve(d.returnValue);}'
            'else{cb.reject(new Error((d.returnValue&&d.returnValue.message)||"call failed"));}'
          '}'
        '}'
      '});'
      ''
      'function call(methodName,args){'
        'return new Promise(function(resolve,reject){'
          'var id=msgId++;'
          'pending[id]={resolve:resolve,reject:reject};'
          'var payload={penpal:"call",id:id,methodName:methodName,args:args||[]};'
          'if(!connected){setTimeout(function(){connect();},0);}'
          'window.parent.postMessage(payload,"*");'
        '});'
      '}'
      ''
      'function has(m){return connected&&methods.indexOf(m)>-1;}'
      'function $on(evt,cb){listeners[evt]=listeners[evt]||[];listeners[evt].push(cb);'
        'return function(){};}'
      'function $off(evt,cb){var l=listeners[evt];if(l){var i=l.indexOf(cb);if(i>-1)l.splice(i,1);}}'
      'return {'
        'get ready(){return connected;},'
        'connect:connect,'
        'isWeb:true,'
        'has:has,'
        'call:call,'
        '$on:$on,'
        '$off:$off,'
        '$notify:function(opts){return call("$notify",[opts||{}]);},'
        'getPlatformConfig:function(){return call("getPlatformConfig",[]);},'
        'setTitle:function(t){return call("setTitle",[t]);},'
        'openFileManager:function(p){return call("openFileManager",[p]);},'
        'convertPath:function(p,l){return call("convertPath",[p,l]);},'
        'pickUserFile:function(opts){return call("pickUserFile",[opts||{}]);},'
        'pickSharedFile:function(opts){return call("pickSharedFile",[opts||{}]);}'
      '};'
    '})();'
    'var sdk=__qbSdk;'
    'setTimeout(function(){sdk.connect();},0);'
    ''
    '/* ===== 1. 主题/语言监听 ===== */'
    'sdk.$on("os/theme",function(t){document.documentElement.setAttribute("data-theme",t);});'
    'sdk.$on("os/language",function(l){document.documentElement.setAttribute("lang",l);});'
    'try{'
      'sdk.getPlatformConfig().then(function(c){'
        'if(c&&c.theme)document.documentElement.setAttribute("data-theme",c.theme);'
        'if(c&&c.language)document.documentElement.setAttribute("lang",c.language);'
      '}).catch(function(){});'
    '}catch(e){}'
    ''
    '/* ===== 2. 获取下载路径 ===== */'
    'fetch(P+"/api/download-path").then(function(r){return r.json();}).then(function(d){'
      'if(d.success&&d.path){'
        '_dlPath=d.path;'
        '_dlPathDisplay=d.displayPath||d.path;'
        'if(!d.hasACL){console.warn("[qB] 下载目录权限不足:",d.path);}'
        'var fb=document.getElementById("qb-openfolder-btn");'
        'if(fb)fb.title="打开下载目录: "+_dlPathDisplay;'
      '}'
    '}).catch(function(){});'
    ''
    '/* ===== 3. 窗口标题显示下载进度 ===== */'
    'function _qBUpdateTitle(){'
      'try{'
        'fetch(P+"/api/v2/torrents/info?filter=downloading").then(function(r){return r.json();}).then(function(d){'
          'var n=Array.isArray(d)?d.length:0;'
          'var t=_titleBase;'
          'if(n>0)t+=" ("+n+"个下载中)";'
          'if(sdk.ready&&sdk.has("setTitle")){sdk.setTitle(t);}'
          'else if(window.setTitle){window.setTitle(t);}'
          'else{document.title=t;}'
        '}).catch(function(){});'
      '}catch(e){}'
    '}'
    'setTimeout(_qBUpdateTitle,3000);'
    'setInterval(_qBUpdateTitle,10000);'
      'function _qBDetect(){'
     'var addBtn=function(){'
     'var h=fe.closest(".trim-ui__app-layout--window");'
     'if(h){h=h.querySelector(".trim-ui__app-layout--header");'
     'if(h){var r=h.querySelector(":scope > div:last-child");'
     'if(r&&!r.querySelector("#qb-newwindow-btn")){'
     'var c=document.createElement("div");'
     'c.id="qb-pickfolder-btn";'
     'c.title="选择下载目录";'
     'c.className="flex h-full w-base shrink-0 cursor-pointer items-center justify-center px-[15px] text-[var(--semi-color-text-0)] hover:bg-[var(--semi-color-fill-0)]";'
     'c.innerHTML=\'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg>\';'
     'c.onclick=function(e){e.stopPropagation();'
       'var P="' + PREFIX + '";'
       'var opts={multiple:false,directory:true,title:"选择下载目录",okText:"确认选择",sidebarGroup:["myFiles","otherShare","favorites"]};'
       'var doPick=function(){'
       'var sel=sdk&&sdk.pickUserFile?sdk.pickUserFile.bind(sdk):null;'
       'var notify=function(t,m){'
        'var colors={success:"#22c55e",error:"#ef4444",warning:"#f59e0b",info:"#3b82f6"};'
        'var icons={success:"✓",error:"✕",warning:"!",info:"ℹ"};'
        'var c=colors[t]||"#3b82f6";'
        'var el=document.createElement("div");'
        'el.style.position="fixed";'
        'el.style.top="16px";'
        'el.style.right="16px";'
        'el.style.zIndex="2147483647";'
        'el.style.display="flex";'
        'el.style.alignItems="center";'
        'el.style.gap="10px";'
        'el.style.maxWidth="360px";'
        'el.style.padding="12px 16px";'
        'el.style.background="rgba(30,32,38,0.95)";'
        'el.style.borderLeft="4px solid "+c;'
        'el.style.borderRadius="8px";'
        'el.style.color="#fff";'
        'el.style.fontSize="13px";'
        'el.style.boxShadow="0 8px 24px rgba(0,0,0,0.35)";'
        'var icon=document.createElement("span");'
        'icon.style.width="18px";icon.style.height="18px";icon.style.flexShrink="0";'
        'icon.style.borderRadius="50%%";icon.style.background=c;icon.style.color="#fff";'
        'icon.style.display="flex";icon.style.alignItems="center";icon.style.justifyContent="center";'
        'icon.style.fontSize="12px";icon.style.fontWeight="bold";'
        'icon.textContent=icons[t]||"ℹ";'
        'var txt=document.createElement("span");'
        'txt.style.flex="1";txt.style.wordBreak="break-all";'
        'txt.textContent=m;'
        'el.appendChild(icon);el.appendChild(txt);'
        'document.body.appendChild(el);'
        'setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},3500);'
       '};'
       'if(!sel){notify("error","文件选择器不可用");return;}'
       'sel(opts).then(function(res){'
        'var p=null;'
        'if(Array.isArray(res)){p=res[0];}'
        'else if(res&&res.data){p=Array.isArray(res.data)?res.data[0]:res.data;}'
        'else if(res&&res.paths&&res.paths.length){p=res.paths[0];}'
        'if(!p){notify("warning","未选择目录");return;}'
        'fetch(P+"/api/set-save-path",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:p})}).then(function(r){return r.json();}).then(function(r2){'
          'if(r2.success){'
            'notify("success",r2.applied?("下载目录已设置为: "+p):("配置已保存，请重启应用后生效"));'
          '}'
          'else{notify("error","设置失败: "+(r2.error||"未知错误"));}'
        '}).catch(function(){notify("error","设置失败，网络错误");});'
       '}).catch(function(err){'
        'var m=(err&&err.message)||"无法打开文件选择器";'
        'if(m.indexOf("cancel")>-1||m.indexOf("canceled")>-1){return;}'
        'notify("error","选择目录失败: "+m);'
       '});'
       '};'
       'if(!sdk.ready){setTimeout(doPick,800);}else{doPick();}'
     '};'
     'r.insertBefore(c,r.firstChild);'
     'var f=document.createElement("div");'
     'f.id="qb-openfolder-btn";'
     'f.title="打开下载目录";'
     'f.className="flex h-full w-base shrink-0 cursor-pointer items-center justify-center px-[15px] text-[var(--semi-color-text-0)] hover:bg-[var(--semi-color-fill-0)]";'
     'f.innerHTML=\'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/></svg>\';'
     'f.onclick=function(e){e.stopPropagation();'
       'var P="' + PREFIX + '";'
       'fetch(P+"/api/download-path").then(function(r){return r.json();}).then(function(d){'
         'if(d.success&&d.path){'
           '/* 通过 Penpal 桥接调用 fnOS 宿主 openFileManager，传真实内部路径 */'
           'sdk.openFileManager(d.path).catch(function(){'
             'var inp=document.createElement("textarea");'
             'inp.value=d.path;inp.style.position="fixed";inp.style.opacity="0";'
             'document.body.appendChild(inp);inp.select();'
             'document.execCommand("copy");document.body.removeChild(inp);'
             'alert("打开失败，下载目录路径已复制: "+d.path);'
           '});'
         '}else{'
           'alert("无法获取下载目录路径");'
         '}'
       '}).catch(function(){alert("获取下载目录失败");});'
     '};'
     'r.insertBefore(f,r.firstChild);'
     'var b=document.createElement("div");'
     'b.id="qb-newwindow-btn";'
     'b.title="新标签页打开";'
     'b.className="flex h-full w-base shrink-0 cursor-pointer items-center justify-center px-[15px] text-[var(--semi-color-text-0)] hover:bg-[var(--semi-color-fill-0)]";'
     'b.innerHTML=\'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4m-8-2l8-8m0 0v5m0-5h-5"/></svg>\';'
     'b.onclick=function(e){e.stopPropagation();window.open(window.location.href,"_blank","noopener");};'
     'r.insertBefore(b, f);'
     'var u=document.createElement("div");'
     'u.id="qb-updatecheck-btn";'
     'u.title="检测更新";'
     'u.className="flex h-full w-base shrink-0 cursor-pointer items-center justify-center px-[15px] text-[var(--semi-color-text-0)] hover:bg-[var(--semi-color-fill-0)]";'
     'u.innerHTML=\'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12a8 8 0 1 1-8-8m-4.5 4.5L12 4l4.5 4.5"/></svg>\';'
     'u.onclick=function(e){e.stopPropagation();if(typeof __qbCheckUpdate==="function"){__qbCheckUpdate();}};'
     'r.insertBefore(u, b);'
     '}}}};'
     'if(document.getElementById("app")){'
     'addBtn();'
     'setTimeout(addBtn,1000);'
      '}else{'
       'var _w=window.open(window.location.href,"_blank");'
       'if(_w){'
       'try{'
       'var _qc=fe.closest(".trim-ui__app-layout--window");'
       'if(_qc){'
       'var _x=_qc.querySelector("[class*=\'close\']")||_qc.querySelector("[class*=\'Close\']");'
       'if(_x&&typeof _x.click==="function"){_x.click();}'
       '}'
       '}catch(e){}'
       '}else{'
       'addBtn();'
       'setTimeout(addBtn,1000);'
       '}'
     '}'
     '}'
    'if(document.readyState==="loading"){'
    'document.addEventListener("DOMContentLoaded",_qBDetect);'
    '}else{'
    '_qBDetect();'
    '}'
    '}catch(e){console.warn("[qB]:",e.message);}'
    '}'
    '})();'
    '</script>'
)

# 构建模板（不含 update-check.js 内容，运行时注入）
_INJECT_SCRIPT_TEMPLATE = _INJECT_SCRIPT_TEMPLATE % (CURRENT_ARCH, _CURRENT_VERSION, PREFIX)

def _build_inject_script():
    """构建最终注入脚本（兼容性检测 + polyfill + update-check.js 内容）"""
    return _COMPAT_SCRIPT + _INJECT_SCRIPT_TEMPLATE.replace('/* __QB_UPDATE_CHECK__ */', _get_update_check_js())

# 延迟构建：仅在首次需要时编码
_INJECT_SCRIPT_B_CACHED = None

def _get_inject_script_bytes():
    global _INJECT_SCRIPT_B_CACHED
    if _INJECT_SCRIPT_B_CACHED is None:
        _INJECT_SCRIPT_B_CACHED = _build_inject_script().encode()
    return _INJECT_SCRIPT_B_CACHED

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
        _q = _get_queue()
        self._pool = _q.Queue(maxsize)

    def acquire(self):
        """从池中取一个连接，没有则新建。"""
        _q = _get_queue()
        try:
            conn = self._pool.get_nowait()
            if conn.sock is not None:
                try:
                    conn.sock.getpeername()
                    return conn
                except (OSError, AttributeError):
                    pass
            conn.close()
        except _q.Empty:
            pass
        return HTTPConnection(self._host, self._port, timeout=self._timeout)

    def release(self, conn):
        """归还连接，池满则关闭。"""
        _q = _get_queue()
        try:
            self._pool.put_nowait(conn)
        except _q.Full:
            conn.close()

    def close_all(self):
        _q = _get_queue()
        while True:
            try:
                self._pool.get_nowait().close()
            except _q.Empty:
                break


# ---------------------------------------------------------------------------
# 静态资源缓存（LRU，按总字节数控制，避免大文件撑爆内存）
# ---------------------------------------------------------------------------
# 单个资源超过该字节数则不入缓存（VueTorrent 大 JS/CSS 无需缓存）
_MAX_SINGLE_CACHE_BYTES = 512 * 1024  # 512 KB
# 缓存总字节上限
_MAX_CACHE_TOTAL_BYTES = 16 * 1024 * 1024  # 16 MB


class StaticCache:
    def __init__(self, max_bytes=_MAX_CACHE_TOTAL_BYTES):
        self._cache = OrderedDict()
        self._max_bytes = max_bytes
        self._used_bytes = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key, status, headers, body):
        if body is None or len(body) > _MAX_SINGLE_CACHE_BYTES:
            # 空响应或超大资源不入缓存（按需直转，不占用内存）
            return
        size = len(body)
        with self._lock:
            existing = self._cache.get(key)
            if existing is not None:
                # 覆盖已有条目，先回收其占用的字节数
                self._used_bytes -= len(existing[2])
            self._used_bytes += size
            # 逐出最旧条目，直到满足总字节上限（至少保留当前条目）
            while self._used_bytes > self._max_bytes and len(self._cache) > 0:
                _, (_, _, old_body) = self._cache.popitem(last=False)
                self._used_bytes -= len(old_body)
            self._cache[key] = (status, headers, body)


_static_cache = StaticCache()

# ---------------------------------------------------------------------------
# fnOS 后端 API 调用（通过 Unix Socket）
# ---------------------------------------------------------------------------
_TRIM_SOCK = "/var/run/trim_open_gateway_apiscope.socket"

def _call_trim_api(req_name, data=None):
    """调用 fnOS 后端开放 API，返回响应中的 data 或 None"""
    api_token = os.environ.get("TRIM_API_TOKEN", "")
    if not api_token:
        return None
    body = json.dumps({
        "req": req_name,
        "appName": "qbittorrent",
        "data": data or {},
    })
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(_TRIM_SOCK)
        req = (
            "POST /api/v1/trimapp HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Authorization: Bearer %s\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: %d\r\n"
            "Connection: close\r\n"
            "\r\n"
            "%s"
        ) % (api_token, len(body), body)
        sock.sendall(req.encode())
        resp = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk
        sock.close()
        header_end = resp.find(b"\r\n\r\n")
        if header_end < 0:
            return None
        resp_body = resp[header_end + 4:]
        result = json.loads(resp_body)
        if result.get("code") == 0:
            return result.get("data")
        return None
    except Exception:
        return None

def _set_conf_value(cfg, key, value):
    """更新 qBittorrent.conf 中某键值（覆盖或新增），返回新配置文本"""
    lines = cfg.splitlines()
    out = []
    section = ""
    found = False
    for line in lines:
        if line.startswith("["):
            section = line.strip().strip("[]")
            out.append(line)
            continue
        if section in ("BitTorrent", "Preferences") and line.startswith(key + "="):
            out.append("%s=%s" % (key, value))
            found = True
            continue
        out.append(line)
    if not found:
        # 追加到合适位置
        if cfg.strip().endswith("]") and "[BitTorrent]" in cfg:
            # 简单追加到文件末尾
            out.append("%s=%s" % (key, value))
        else:
            out.append("")
            out.append("[BitTorrent]")
            out.append("%s=%s" % (key, value))
    return "\n".join(out)

def _call_qbt_api(method, api_path, body=None):
    """调用 qBittorrent WebUI API（LocalHostAuth=false，无需 Cookie）。
    返回 (status, json_dict_or_text)。失败返回 (None, None)。"""
    host = TARGET_HOST
    port = INITIAL_PORT
    try:
        conn = HTTPConnection(host, port, timeout=15)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        conn.request(method, api_path, body=body, headers=headers)
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


def _set_qbt_save_path(new_path):
    """通过 qBittorrent WebUI API 实时设置默认下载目录"""
    from urllib.parse import urlencode
    prefs = {
        "save_path": new_path,
        "temp_path": os.path.join(new_path, "temp"),
    }
    body = urlencode({"json": json.dumps(prefs)})
    status, resp = _call_qbt_api("POST", "/api/v2/app/setPreferences", body=body)
    return status == 200

# HTML 首页缓存（单条目，缓存 / 和 /index.html 的注入后 HTML）
_html_cache = {}
_html_cache_lock = threading.Lock()

def get_cached_html(path):
    """获取缓存的注入后 HTML 页面"""
    with _html_cache_lock:
        return _html_cache.get(path)

def set_cached_html(path, data):
    """缓存注入后的 HTML 页面"""
    with _html_cache_lock:
        _html_cache[path] = data

_HOME_PATHS = frozenset({'/', '/index.html'})

# 记录 UI 签名（按配置文件 mtime 缓存，避免频繁读文件）
_ui_signature_cache = {"sig": None, "mtime": None}


def _get_ui_signature():
    """读取配置中 UI 相关键生成签名。

    用户在 qBittorrent WebUI 内直接切换备用 UI（AlternativeUIEnabled）
    或修改 RootFolder 时，代理进程不会重启，首页 HTML 缓存会命中旧页面。
    用签名区分缓存，签名变化即换用新的缓存条目。
    """
    if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
        return ""
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if _ui_signature_cache["mtime"] == mtime:
            return _ui_signature_cache["sig"]
        with open(CONFIG_PATH, 'r') as f:
            txt = f.read()
        alt = re.search(r'^WebUI\\AlternativeUIEnabled=(\w+)', txt, re.MULTILINE)
        root = re.search(r'^WebUI\\RootFolder=(.*)$', txt, re.MULTILINE)
        sig = "%s|%s" % (
            alt.group(1) if alt else "",
            root.group(1).strip() if root else "",
        )
        _ui_signature_cache = {"sig": sig, "mtime": mtime}
        return sig
    except Exception:
        return ""


def _is_static_cacheable(method, path):
    if method != 'GET':
        return False
    if path.startswith('/api/'):
        return False
    idx = path.rfind('.')
    if idx < 0:
        return False
    return path[idx + 1:].lower() in STATIC_EXTENSIONS


def _is_home_path(path):
    """判断是否为 HTML 首页入口"""
    return path in _HOME_PATHS


# ---------------------------------------------------------------------------
# 解压缩工具
# ---------------------------------------------------------------------------
def decompress(data, encoding):
    try:
        if encoding == 'gzip':
            return gzip.decompress(data)
        elif encoding == 'deflate':
            return zlib.decompress(data)
        elif encoding == 'br':
            br = _get_brotli()
            if br:
                return br.decompress(data)
    except Exception as e:
        logging.warning("decompress(%s) failed: %s", encoding, e)
    return None


# ---------------------------------------------------------------------------
# HTML 重写
# ---------------------------------------------------------------------------
def rewrite_html(data):
    """注入 JS polyfill + 重写 src/href/action 绝对路径。"""
    data = data.replace(b'</head>', _get_inject_script_bytes() + b'</head>', 1)
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
        resp = urllib.request.urlopen(req, timeout=30)
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
    start_time = time.time()
    try:
        with open(tmp, 'wb') as f:
            while True:
                elapsed = time.time() - start_time
                if elapsed > DOWNLOAD_TIMEOUT:
                    resp.close()
                    os.remove(tmp)
                    return False, "下载超时 (已耗时 %ds，超过限制 %ds)" % (
                        int(elapsed), DOWNLOAD_TIMEOUT)
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


def _perform_update(info):
    global _update_status
    try:
        fpk_url = info["fpkUrl"]
        expected_version = info["version"]
        expected_size = info.get("fpkSize", 0)
        # URL 版本一致性检查，从 URL 中提取版本与 API 返回的版本比对
        fpk_filename = fpk_url.rsplit('/', 1)[-1] if '/' in fpk_url else fpk_url
        m = re.search(r'qbittorrent-([\d.]+)-', fpk_filename)
        url_version = m.group(1) if m else ""
        if url_version and url_version != expected_version:
            raise Exception(
                "版本信息不一致: API 返回 %s, 更新包 URL 指向 %s" % (expected_version, url_version)
            )
        _update_status["message"] = "正在准备更新..."
        _update_status["progress"] = 5
        fpk_path = "/tmp/qbittorrent-update.fpk"
        urls = [UPDATE_PROXY_MAIN + fpk_url, UPDATE_PROXY_BACKUP + fpk_url, fpk_url]
        success = False
        last_error = ""
        messages = [
            "正在下载更新包...",
            "主代理下载失败，切换备用代理...",
            "备用代理下载失败，尝试直连..."
        ]
        for idx, download_url in enumerate(urls):
            _update_status["message"] = messages[idx]
            _update_status["progress"] = 10
            ok, err = _download_fpk(download_url, fpk_path, _update_status)
            if ok:
                valid, reason = _validate_fpk(fpk_path)
                if not valid:
                    last_error = "文件校验失败: %s" % reason
                    os.remove(fpk_path)
                    continue
                # 校验文件大小是否与 GitHub API 返回的一致
                actual_size = os.path.getsize(fpk_path)
                if expected_size > 0 and actual_size != expected_size:
                    last_error = (
                        "文件大小不匹配: 期望 %d 字节, 实际 %d 字节" %
                        (expected_size, actual_size)
                    )
                    os.remove(fpk_path)
                    continue
                success = True
                break
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


def _stream_copy(src, dst, chunk_size=65536):
    """分块拷贝响应 body，避免一次性读入内存。"""
    while True:
        chunk = src.read(chunk_size)
        if not chunk:
            break
        dst.write(chunk)
    try:
        dst.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 代理请求处理器
# ---------------------------------------------------------------------------
# 需要移除的安全头（仅移除会阻止 iframe 嵌入的头）
# X-Frame-Options: DENY 会阻止 iframe，必须移除
# CSP 不应移除（提供 XSS 防护），通过 frame-ancestors 允许 iframe
_REMOVE_HEADERS = frozenset({
    "x-frame-options",
})


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    # 使用 HTTP/1.1：HTTP/1.0 不支持 chunked 编码，
    # 而动态 API 响应（无 Content-Length 时）会走 chunked 转发
    protocol_version = "HTTP/1.1"
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
        if path == "/api/download-path":
            try:
                save_path = ""
                if CONFIG_PATH and os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, 'r') as f:
                        for line in f:
                            m = re.match(r'(?:Session\\DefaultSavePath|Downloads\\SavePath)=(.*)', line)
                            if m:
                                save_path = m.group(1).strip()
                                break
                result = {"success": True, "path": save_path, "displayPath": save_path, "hasACL": True}
                if save_path:
                    # 路径转换：需要 language 参数
                    try:
                        display = _call_trim_api("trim.file.convertPath", {
                            "path": [save_path],
                            "language": "zh-CN",
                        })
                        if display and display.get("status") == 0:
                            sem = display.get("result", [{}])[0].get("semanticPath", "")
                            if sem:
                                result["displayPath"] = sem
                    except Exception:
                        pass
                    # 权限检查：需要 uid 参数，从请求头获取
                    try:
                        uid = self.headers.get("X-Trim-Userid", "")
                        if uid:
                            acl = _call_trim_api("trim.file.checkUserACL", {
                                "uid": int(uid),
                                "path": save_path,
                            })
                            if acl and isinstance(acl, list) and len(acl) > 0:
                                item = acl[0]
                                result["hasACL"] = bool(item.get("readable") or item.get("writable"))
                    except Exception:
                        pass
                self._send_json(200, result)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return True

        if path == "/api/set-save-path":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0:
                    self._send_json(400, {"success": False, "error": "缺少请求体"})
                    return True
                req_body = self.rfile.read(length).decode("utf-8")
                data = json.loads(req_body)
                new_path = (data.get("path") or "").strip()
                if not new_path:
                    self._send_json(400, {"success": False, "error": "路径不能为空"})
                    return True
                if not os.path.isdir(new_path):
                    try:
                        os.makedirs(new_path, exist_ok=True)
                    except Exception:
                        self._send_json(400, {"success": False, "error": "目录不存在且无法创建: %s" % new_path})
                        return True
                if not os.path.isdir(new_path):
                    self._send_json(400, {"success": False, "error": "目录不存在: %s" % new_path})
                    return True
                # 更新配置文件（持久化，重启后仍生效）
                if CONFIG_PATH and os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, 'r') as f:
                        cfg = f.read()
                    cfg_new = _set_conf_value(cfg, "Session\\DefaultSavePath", new_path)
                    cfg_new = _set_conf_value(cfg_new, "Session\\TempPath", new_path + "/temp/")
                    with open(CONFIG_PATH, 'w') as f:
                        f.write(cfg_new)
                # 调用 qBittorrent API 实时生效（无需重启）
                qbt_ok = _set_qbt_save_path(new_path)
                self._send_json(200, {
                    "success": True,
                    "path": new_path,
                    "applied": qbt_ok,
                    "note": "" if qbt_ok else "配置已保存，但实时应用失败，可能需重启应用生效",
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return True

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
            t = threading.Thread(target=_perform_update, args=(info,))
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
                    or ("qbittorrent-%s.fpk" % (
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
            # HTTP/1.1 下必须显式声明 body 长度，否则网关（客户端）
            # 无法判定响应边界，会一直等待导致请求挂起（iframe 白屏/超时）。
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True
            return

        # WebSocket 升级
        upgrade = self.headers.get("Upgrade", "").lower()
        if upgrade == "websocket":
            self._handle_ws()
            return

        path = self._strip_prefix()

        # API 路由（代理自定义 API，不走后端转发）
        if path.startswith("/api/"):
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
                    self.send_header("Content-Length", str(len(c_body)))
                    self.end_headers()
                if pool:
                    pool.release(conn)
                else:
                    conn.close()
                return

        # HTML 首页缓存命中检查（注入后的完整 HTML）
        is_home = _is_home_path(path)
        if is_home:
            # 缓存 key 带上 UI 签名，UI 切换后不命中旧缓存
            html_key = path + "|" + _get_ui_signature()
            cached_html = get_cached_html(html_key)
            if cached_html is not None:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
                    "frame-ancestors *; "
                    "img-src 'self' data: blob:; "
                    "style-src 'self' 'unsafe-inline';"
                )
                self.send_header("Cache-Control", "no-cache")
                if not is_head:
                    self.send_header("Content-Length", str(len(cached_html)))
                    self.end_headers()
                    self.wfile.write(cached_html)
                else:
                    self.send_header("Content-Length", str(len(cached_html)))
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
                # 仅移除会阻止 iframe 嵌入的头（X-Frame-Options: DENY）
                if kl in _REMOVE_HEADERS:
                    continue
                # send_response 已发送 Server 头，跳过后端的避免重复
                if kl == "server":
                    continue
                # 保留 SameSite 属性（不再剥离），提升 CSRF 防护
                if kl == "set-cookie":
                    self.send_header(key, value)
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
                # 缓存首页 HTML（避免每次打开都重新从后端获取和重写）
                if is_home and 200 <= resp.status < 300:
                    set_cached_html(html_key, data)
                # 添加 CSP 允许 iframe 嵌入，同时提供 XSS 防护
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
                    "frame-ancestors *; "
                    "img-src 'self' data: blob:; "
                    "style-src 'self' 'unsafe-inline';"
                )
                if not is_head:
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    # HEAD: 告诉客户端如果 GET 会有多大
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
            else:
                if cacheable and 200 <= resp.status < 300:
                    # 静态资源：读全并缓存（缓存层会按字节上限/单文件上限自动淘汰或跳过）
                    data = resp.read()
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
                else:
                    # 动态 API 响应 / 下载等：流式分块转发，避免一次性读入内存造成峰值占用。
                    # 后端无 Content-Length 时使用 chunked 编码。
                    content_length = resp.getheader("Content-Length")
                    if not is_head:
                        if content_length:
                            self.send_header("Content-Length", content_length)
                            self.end_headers()
                            _stream_copy(resp, self.wfile)
                        else:
                            # 无长度信息：以 chunked 形式转发
                            self.send_header("Transfer-Encoding", "chunked")
                            self.end_headers()
                            while True:
                                chunk = resp.read(65536)
                                if not chunk:
                                    self.wfile.write(b"0\r\n\r\n")
                                    break
                                self.wfile.write(
                                    b"%x\r\n" % len(chunk) + chunk + b"\r\n"
                                )
                    else:
                        # HEAD：仅透传长度头（不读 body）
                        if content_length:
                            self.send_header("Content-Length", content_length)
                            self.end_headers()
                        else:
                            # 无长度信息时显式声明空 body，避免网关判定挂起
                            self.send_header("Content-Length", "0")
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
                # 跳过 Server 头避免与 send_response 生成的重复
                if k.strip().lower() == "server":
                    continue
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
        cf = _get_concurrent_futures()
        # 并发上限按实际 WebUI 使用量收敛（20 → 8），显著降低线程栈虚拟内存与调度开销
        self._executor = cf.ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="proxy"
        )

    def server_bind(self):
        self.socket.bind(self.server_address)
        os.chmod(self.server_address, 0o660)

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

    # 降低线程栈大小（默认 8MB → 256KB），8 个线程合计节省约 62MB 虚拟内存。
    # 需在创建 ThreadPoolExecutor 之前调用。请求处理为轻量 IO 转发，256KB 足够。
    try:
        threading.stack_size(256 * 1024)
    except (ValueError, RuntimeError):
        pass  # 平台不支持时忽略

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
