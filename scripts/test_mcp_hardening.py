#!/usr/bin/env python3
"""
本地回归测试：mcp-server.py 的口令面与请求面加固。

覆盖：
  A. 高危开关语义：savepath、torrents/setLocation、rss/setRule、hashes=all
  B. HTTP 层：请求体上限、非法 Content-Length、正常 initialize
  C. 并发上限：BoundedThreadingHTTPServer 在超限时返回 503（不发线程）

运行：python3 scripts/test_mcp_hardening.py
"""
import importlib.util
import json
import os
import socket
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP = os.path.join(REPO, "app", "bin", "mcp-server.py")
FAILURES = []


def check(name, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def load_mcp():
    spec = importlib.util.spec_from_file_location("mcp_under_test_hardening", MCP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_qbt(monkey_return=(200, "Ok.")):
    calls = []

    def _fake(method, path, body=None, headers=None):
        calls.append((method, path, body))
        return monkey_return

    return _fake, calls


def test_dangerous_gates(mcp):
    """关掉高危开关后，savepath / setLocation / RSS 规则 / hashes=all 都应被拒。"""
    mcp.ALLOW_DANGEROUS = False

    fake, calls = fake_qbt()
    mcp.qbt_api = fake

    text, is_err = mcp.tool_add_torrent({"urls": ["magnet:?xt=urn:btih:abc"], "savepath": "/tmp/x"})
    check("add_torrent 带 savepath 被拒", is_err and "高危" in text, text)
    check("被拒时没有真的调用 qBittorrent", not calls, calls)

    text, is_err = mcp.tool_add_torrent({"urls": ["magnet:?xt=urn:btih:abc"]})
    check("不带 savepath 仍可用", not is_err, text)

    text, is_err = mcp.tool_api_request({"path": "torrents/setLocation", "method": "POST", "params": {"hashes": "aa", "location": "/tmp"}})
    check("setLocation 需高危开关", is_err and "高危" in text, text)

    text, is_err = mcp.tool_api_request({"path": "rss/setRule", "method": "POST", "params": {"ruleName": "x"}})
    check("rss/setRule 需高危开关", is_err and "高危" in text, text)

    text, is_err = mcp.tool_api_request({"path": "torrents/reannounce", "method": "POST", "params": {"hashes": "all"}})
    check("hashes=all 需高危开关", is_err and "全部任务" in text, text)

    text, is_err = mcp.tool_api_request({"path": "torrents/reannounce", "method": "POST", "params": {"hashes": "aa"}})
    check("具体 hashes 仍可用", not is_err, text)

    # 打开开关后放行
    mcp.ALLOW_DANGEROUS = True
    fake2, calls2 = fake_qbt()
    mcp.qbt_api = fake2
    text, is_err = mcp.tool_api_request({"path": "torrents/setLocation", "method": "POST", "params": {"hashes": "aa", "location": "/tmp"}})
    check("开启后 setLocation 放行", not is_err, text)
    mcp.ALLOW_DANGEROUS = False


def http_request(port, raw):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        s.sendall(raw)
        chunks = []
        while True:
            b = s.recv(4096)
            if not b:
                break
            chunks.append(b)
        return b"".join(chunks)
    finally:
        s.close()


def test_http_limits(mcp):
    """请求体上限与 Content-Length 校验必须在解析前生效。"""
    mcp.CONFIG_PATH = None          # 无 Key：仅放行本机，测试用 127.0.0.1 正好通过
    server = mcp.BoundedThreadingHTTPServer(("127.0.0.1", 0), mcp.McpHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        body = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        raw = (b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
               b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(body)) + body
        resp = http_request(port, raw)
        check("正常 initialize 返回 200", b"200" in resp.split(b"\r\n")[0], resp[:120])

        over = (b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                b"Content-Length: %d\r\nConnection: close\r\n\r\n" % (mcp.McpHandler.MAX_BODY_BYTES + 1))
        resp = http_request(port, over)
        check("超大请求体返回 413", b"413" in resp.split(b"\r\n")[0], resp[:120])

        bad = (b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
               b"Content-Length: abc\r\nConnection: close\r\n\r\n")
        resp = http_request(port, bad)
        check("非法 Content-Length 返回 400", b"400" in resp.split(b"\r\n")[0], resp[:120])
    finally:
        server.shutdown()
        server.server_close()


def test_concurrency_cap(mcp):
    """并发达到上限后应直接 503，而不是无限开线程。"""
    class Tiny(mcp.BoundedThreadingHTTPServer):
        MAX_WORKERS = 1

    mcp.CONFIG_PATH = None
    server = Tiny(("127.0.0.1", 0), mcp.McpHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # 占满唯一的工作线程：发一半 header 让它停在读请求行/头上
        hold = [socket.create_connection(("127.0.0.1", port), timeout=5) for _ in range(1)]
        for s in hold:
            s.sendall(b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Length: 999\r\n\r\n{")
        import time
        time.sleep(0.3)
        resp = http_request(port, b"GET /mcp HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        check("超出并发上限返回 503", b"503" in resp.split(b"\r\n")[0], resp[:120])
        for s in hold:
            s.close()
    finally:
        server.shutdown()
        server.server_close()


def main():
    print("mcp-server 加固回归测试")
    print("=" * 60)
    mcp = load_mcp()
    for fn in (test_dangerous_gates, test_http_limits, test_concurrency_cap):
        print(fn.__name__ + "  " + (fn.__doc__ or "").strip().splitlines()[0])
        try:
            fn(mcp)
        except Exception as e:
            check(fn.__name__ + " 执行异常", False, repr(e))
    print("=" * 60)
    if FAILURES:
        print("失败 %d 项：%s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
