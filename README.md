# qBittorrent for fnOS

**功能强大的BitTorrent下载工具**，飞牛NAS版，接入统一网关。

![qBittorrent](https://img.shields.io/badge/qBittorrent-5.2.3.2-blue?style=flat-square&logo=qbittorrent)
![VueTorrent](https://img.shields.io/badge/VueTorrent-2.35.0-purple?style=flat-square&logo=vue.js)
![Platform](https://img.shields.io/badge/Platform-fnOS_1.1.31+-green?style=flat-square&logo=nas)
![MCP](https://img.shields.io/badge/MCP-%E2%9C%93%20AI%E6%8E%A5%E5%85%A5-8A2BE2?style=flat-square)
![License](https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square)

---

## ✨ 特色功能

| 功能 | 说明 |
|------|------|
| 🌐 **统一网关** | 接入fnOS网关，通过系统地址直接访问，无需配置端口 |
| 🔓 **自动免登录** | 网关模式下跳过WebUI登录，统一网关已保证身份认证 |
| 🎨 **智能适配** | VueTorrent iframe打开，原生WebUI自动弹出新标签页并关闭app窗口 |
| 📡 **完整BT协议** | 支持BitTorrent v1/v2，DHT/PEX/LSD P2P网络 |
| 📰 **RSS订阅** | 支持RSS自动下载，订阅管理 |
| 🔍 **搜索引擎** | 内置多引擎搜索，聚合结果 |
| ⚡ **速度控制** | 灵活的速度限制和队列管理 |
| 📁 **文件管理** | 顺序下载、选择性下载、文件优先级 |
| 🛡️ **IP过滤** | 支持IP过滤列表和加密协议 |
| 🔔 **更新检测** | 自动检测GitHub最新版本，VueTorrent与原生WebUI均支持，按架构匹配 |
| 🔄 **动态端口** | WebUI改端口后代理自动跟随，无需重启 |
| 🤖 **MCP AI 接入** | 内置 MCP Server，CodeBuddy / Cherry Studio / Claude 等 AI 客户端可直接管理下载任务 |

---

## 🎨 界面说明

| 使用的WebUI | 行为 |
|------------|------|
| **VueTorrent** | 在fnOS iframe 中正常打开，窗口头部提供"新标签页打开"按钮 |
| **qBittorrent原生WebUI** | iframe 中自动弹出新标签页，原 app 窗口自动关闭 |

VueTorrent 为默认WebUI，如需切换至原生WebUI请在 qBittorrent 设置中关闭"使用备用WebUI"。

> ⚠️ **弹窗提醒**：原生WebUI自动打开新标签页依赖 `window.open()`。请在浏览器中**允许 fnOS 站点弹出窗口**，否则 `window.open()` 会被拦截。拦截后会在窗口头部显示"新标签页打开"按钮，需手动点击打开。

---

## 🏗️ 网关架构

```
用户浏览器 → fnOS网关(5666) → qbittorrent.sock → Python反向代理 → 127.0.0.1:8080 → qbittorrent-nox
```

代理功能：
- 自动剥离 `/app/qbittorrent` 路径前缀
- `LocalHostAuth=false` + 代理从127.0.0.1转发 → 自动跳过WebUI登录
- 拦截 `fetch`/`XMLHttpRequest`/`WebSocket` 中的绝对路径请求
- 重写HTML中的 `src`/`href`/`action` 绝对路径
- WebSocket Upgrade 透传（原始TCP双向tunnel）
- 非HTML响应保留gzip压缩透传，HTML响应解压重写
- 动态读取配置文件端口，WebUI改端口后自动生效
- 多线程并发处理
- 统一更新检测脚本注入（`update-check.js`），VueTorrent（构建注入）与原生WebUI（网关注入）共用

---

## 📦 安装与更新

> **系统要求**：fnOS v1.1.3104+（需要统一网关支持）

### 手动安装/更新

1. 打开 **应用中心** → 左下角 **手动安装**
2. 选择对应架构的fpk文件：
   - x86设备：`qbittorrent-5.2.3.2-amd64.fpk`
   - ARM设备：`qbittorrent-5.2.3.2-arm64.fpk`

或命令行：

```bash
appcenter-cli install-local qbittorrent-5.2.3.2-arm64.fpk
```

---

## 🏗️ 本地构建

统一使用跨平台 Python 构建脚本 `build.py`，**在 Windows / Linux / macOS 上命令完全一致**，仅需安装 Python 3.8+（项目本身即依赖 Python，无额外负担）。

```bash
# 基本用法（默认从 manifest 读取版本，默认架构 arm64）
python build.py

# 指定版本与架构
python build.py --version 5.2.3.2 --arch amd64
python build.py --version 5.2.3.2 --arch arm64

# 强制重新下载所有依赖
python build.py --force
```

**参数说明**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--version, -v` | 打包版本号（覆盖 manifest） | 读取 manifest |
| `--arch, -a` | 目标架构 `arm64` / `amd64` | `arm64` |
| `--force, -f` | 强制重新下载所有依赖 | 关闭 |

**构建特性**：
- **跨平台**：一份脚本在 Windows / Linux / macOS 通用，自动检测平台并选择对应的官方 `fnpack` 构建工具（`windows-amd64` / `linux-amd64` / `linux-arm` / `darwin-amd64` / `darwin-arm64`）
- **零外部依赖**：下载用内置 `urllib`，解压用内置 `zipfile`，无需安装 `curl` / `unzip` / `jq`
- 自动获取对应版本的qBittorrent-nox和VueTorrent
- 智能代理策略：gh-proxy.com → ghfast.top → 直连 自动切换
- 统一更新检测脚本（`app/ui/update-check.js`），同时服务于VueTorrent与原生WebUI
- 构建产物输出到项目根目录：`qbittorrent-<版本>-<架构>.fpk`

---

## 🔄 升级与数据保留

- **升级前**：自动将数据备份到共享目录
- **升级后**：自动从备份恢复数据
- **卸载时**：可选择保留或删除数据

---

## 💻 默认配置

| 项目 | 默认值 |
|------|--------|
| 系统版本 | fnOS v1.1.3104+ |
| 访问地址 | `http://<NAS_IP>:5666/app/qbittorrent/` |
| WebUI 监听地址 | `0.0.0.0`（所有接口） |
| WebUI 端口 | `8080` |
| LocalHostAuth | `false`（允许从非本机发起认证） |

> 🔓 网关模式下无需手动登录，统一网关已保证用户身份认证

### 🌐 WebUI / API 外部访问

qBittorrent WebUI 默认监听 `0.0.0.0`（所有接口），除 fnOS 网关入口外，也可通过局域网地址直接访问 WebUI 及 WebUI API：

```
http://<NAS_IP>:8080/               # WebUI
http://<NAS_IP>:8080/api/v2/...     # WebUI API（如 auth/login、torrents/info 等）
```

- 网关代理（`gateway-proxy.py`）从本机 `127.0.0.1:8080` 转发，改动监听地址不影响 fnOS 桌面 iframe 访问。
- WebUI/API 仍受 qBittorrent 用户名+密码保护（SSO 模式下为随机内部凭证），需先通过 `auth/login` 获取 cookie 才能调用 API。
- 如需脚本/自动化调用，可参考 [qBittorrent WebUI API 文档](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0))，例如：

```bash
# 登录获取 cookie
curl -s -c cookies.txt -d "username=<用户>&password=<密码>" \
  "http://<NAS_IP>:8080/api/v2/auth/login"

# 使用 cookie 调用 API
curl -s -b cookies.txt "http://<NAS_IP>:8080/api/v2/torrents/info"
```

> ⚠️ **安全提醒**：监听所有接口意味着 WebUI 会暴露到局域网，务必使用强密码。若仅需本机/网关访问，可手动把 `qBittorrent.conf` 中 `WebUI\Address` 改回 `127.0.0.1` 后重启应用。

---

## 🤖 MCP 服务（AI 客户端接入）

应用内置 **qBittorrent MCP Server**（Streamable HTTP 传输，零第三方依赖），让 AI 客户端（CodeBuddy / Cherry Studio / Claude 等）通过 MCP 协议直接管理下载任务：

```
AI 客户端 ──HTTP POST /mcp (JSON-RPC 2.0)──> MCP Server (:8081) ──> 127.0.0.1:8080 qBittorrent WebUI API
```

### 快速开始

1. 打开应用窗口，点击**标题栏 MCP 图标**进入「MCP 服务设置」
2. 勾选 **启用 MCP 服务**，点击 **保存并生效**
3. 复制面板中的 **MCP 连接地址** 与 **Web API Key**
4. 在 AI 客户端中按以下格式添加：

```json
{
  "mcpServers": {
    "qbittorrent": {
      "type": "http",
      "url": "http://<NAS_IP>:8081/mcp",
      "headers": {
        "Authorization": "Bearer <你的API Key>"
      }
    }
  }
}
```

### 设置面板

| 选项 | 说明 |
|------|------|
| **启用 MCP 服务** | 开启后由代理自动拉起/热重启 MCP 子进程 |
| **服务端口** | 默认 `WebUI端口 + 1`（即 `8081`），可自定义（1024–65535） |
| **Web API Key** | 客户端鉴权密钥，支持一键复制 / **重新生成**（旧 Key 立即失效） |
| **MCP 连接地址** | 客户端接入 URL，一键复制 |
| **允许高危操作** | 高危操作开关，详见下文 |

### 🛡️ 高危操作开关

为防止 AI 误操作，**删除 / 停止 / 开始** 任务默认**禁用**，关闭状态下 MCP 仅提供只读查询与添加任务能力：

| 开关状态 | 可用能力 |
|----------|----------|
| 关闭（默认） | 查看版本/状态/任务列表/详情、添加任务，以及通用 API 透传中的低风险写操作（改分类/标签/限速/RSS 等） |
| 开启 | 上述全部 + 停止 / 开始 / 删除任务，以及通用 API 透传的全部写操作 |

- 开关在「MCP 服务设置」面板中切换，**保存即热重启生效**，无需重启应用
- 禁用期间：高危工具不会出现在 `tools/list` 的正常列表描述中（带"已被管理员禁用"标注），直接调用也会收到明确的错误提示
- 持久化于 `mcp.conf`（与 `qBittorrent.conf` 同目录），重启后保持

### 工具清单

| 工具 | 说明 | 高危 |
|------|------|:----:|
| `qb_app_info` | qBittorrent 版本与 MCP 服务信息 | |
| `qb_global_status` | 全局传输状态（速度 / 总量 / 连接状态） | |
| `qb_list_torrents` | 列出下载任务（按状态 / 分类 / 标签过滤、排序、限量） | |
| `qb_torrent_detail` | 单任务详情（属性 + 文件列表） | |
| `qb_add_torrent` | 添加下载任务（磁力链接 / .torrent 地址，可指定目录与分类） | |
| `qb_start_torrents` | 开始（恢复）任务 | 🟠 |
| `qb_stop_torrents` | 停止（暂停）任务 | 🟠 |
| `qb_delete_torrents` | 删除任务（可选同时删除文件） | 🟠 |
| `qb_api_request` | **通用 API 透传**：调用任意 qBittorrent WebUI API 端点，完整覆盖官方 API（含搜索插件、RSS、日志、统计等无专属封装的能力） | 视端点 |

### 通用 API 透传（`qb_api_request`）

qBittorrent WebUI API 有 100+ 端点，除上述专属工具外，`qb_api_request` 可调用**任意** `/api/v2` 端点，实现完整接入：

```json
// tools/call 参数示例：查看所有分类
{ "name": "qb_api_request", "arguments": { "method": "GET", "path": "torrents/categories" } }

// 示例：通过搜索插件搜索资源
{ "name": "qb_api_request", "arguments": {
    "method": "POST", "path": "search/start",
    "params": { "pattern": "Ubuntu", "category": "all", "plugins": "enabled" } } }
```

安全约束：

| 规则 | 说明 |
|------|------|
| `GET` 查询 | 始终允许 |
| 低风险写操作 | 添加任务、分类/标签管理、限速、优先级、RSS 管理等，始终允许 |
| 其余写操作 | 需开启「允许高危操作」（与专属高危工具同一开关） |
| 敏感端点 | `auth/*`、`app/setPreferences`、`app/rotateAPIKey` 等一律禁止透传，防止 AI 破坏鉴权配置 |

### 鉴权说明

- 请求头支持 `Authorization: Bearer <key>` 或 `X-Api-Key: <key>` 两种方式
- Key 即 qBittorrent **Web API Key**（可在 VueTorrent：设置 → WebUI → Web API Key 查看），每次请求实时读取，**轮换后立即生效，无需重启**
- 未配置 API Key 时仅允许来自 `127.0.0.1` 的请求

> 💡 更多技术细节可查看服务端脚本 `app/bin/mcp-server.py` 头部注释。

---

## 📋 更新日志

详见 [GitHub Releases](https://github.com/sushazhi/fnos-qbittorrent/releases)

---

## 🤝 支持与反馈

- 🐛 [报告问题](https://github.com/sushazhi/fnos-qbittorrent/issues)
- 💬 [飞牛论坛](https://club.fnnas.com/)
- 📖 [fnOS开发文档](https://developer.fnnas.com/)

---

## 📁 项目结构

```
fnos-qbittorrent/
├── app/
│   ├── bin/
│   │   ├── qbittorrent-nox        # qBittorrent守护进程
│   │   ├── gateway-proxy.py       # Python反向代理（网关模式 + MCP服务托管）
│   │   ├── mcp-server.py          # qBittorrent MCP Server（AI客户端接入）
│   │   └── qbt_password.py        # PBKDF2密码哈希生成
│   └── ui/
│       ├── vuetorrent/            # VueTorrent WebUI
│       ├── config                 # 应用入口配置
│       ├── images/                # 应用图标
│       └── update-check.js        # 更新检测脚本
├── cmd/
│   ├── main                       # 启动/停止/重启/状态
│   ├── install_init               # 安装前验证
│   ├── install_callback           # 安装后配置
│   ├── config_init                # 读取当前配置
│   ├── config_callback            # 配置变更（用户名/密码/UI类型）
│   ├── upgrade_init               # 升级前备份
│   ├── upgrade_callback           # 升级后恢复
│   ├── uninstall_init             # 卸载初始化
│   └── uninstall_callback         # 卸载清理
├── config/
│   ├── privilege                  # 权限配置
│   └── resource                   # 资源映射
├── wizard/
│   ├── install                    # 安装向导
│   ├── config                     # 配置向导（含密码修改）
│   ├── uninstall                  # 卸载向导
│   └── upgrade                    # 升级向导
├── build.py                       # 跨平台构建脚本（Windows/Linux/macOS）
├── manifest                       # 应用清单
└── README.md
```

---

## 🙏 项目引用

本项目构建于以下优秀的开源项目之上：

| 项目 | 说明 | 许可证 |
|------|------|--------|
| [**qBittorrent**](https://github.com/qbittorrent/qBittorrent) | 核心 BT 下载引擎 (`qbittorrent-nox`) | [GPL-2.0](https://github.com/qbittorrent/qBittorrent/blob/master/COPYING) |
| [**VueTorrent**](https://github.com/VueTorrent/VueTorrent) | 现代 WebUI 界面 | [MIT](https://github.com/VueTorrent/VueTorrent/blob/master/LICENSE) |
| [**userdocs/qbittorrent-nox-static**](https://github.com/userdocs/qbittorrent-nox-static) | 静态编译的 qBittorrent-nox 二进制 | [GPL-2.0](https://github.com/userdocs/qbittorrent-nox-static/blob/main/LICENSE) |
| [**fnOS**](https://www.fnnas.com/) | 飞牛 NAS 操作系统（统一网关） | 专有 |
| [**fnpack**](https://static2.fnnas.com/fnpack/) | fnOS 应用打包工具 | 专有 |

### 致谢

- [@userdocs](https://github.com/userdocs) — 提供跨平台静态编译的 qBittorrent-nox
- [@VueTorrent](https://github.com/VueTorrent) — 优秀的现代化 qBittorrent WebUI
- 飞牛团队（fnOS）— 提供统一网关和应用平台

---

## 📄 许可证

本项目基于 [GPL-2.0](LICENSE) 许可证开源。

本项目包含 [qBittorrent](https://github.com/qbittorrent/qBittorrent)（GPL-2.0）及 [VueTorrent](https://github.com/VueTorrent/VueTorrent)（MIT）的分发版本。
