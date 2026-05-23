# qBittorrent for fnOS

**功能强大的BitTorrent下载工具**，飞牛NAS版，接入统一网关。

![qBittorrent](https://img.shields.io/badge/qBittorrent-5.2.0.1-blue?style=flat-square&logo=qbittorrent)
![VueTorrent](https://img.shields.io/badge/VueTorrent-2.33.0-purple?style=flat-square&logo=vue.js)
![Platform](https://img.shields.io/badge/Platform-fnOS_1.1.31+-green?style=flat-square&logo=nas)
![License](https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square)

---

## ✨ 特色功能

| 功能 | 说明 |
|------|------|
| 🌐 **统一网关** | 接入fnOS网关，通过系统地址直接访问，无需配置端口 |
| 🎨 **双WebUI** | VueTorrent在fnOS内iframe打开，原生UI新标签页打开 |
| 📡 **完整BT协议** | 支持BitTorrent v1/v2，DHT/PEX/LSD P2P网络 |
| 📰 **RSS订阅** | 支持RSS自动下载，订阅管理 |
| 🔍 **搜索引擎** | 内置多引擎搜索，聚合结果 |
| ⚡ **速度控制** | 灵活的速度限制和队列管理 |
| 📁 **文件管理** | 顺序下载、选择性下载、文件优先级 |
| 🛡️ **IP过滤** | 支持IP过滤列表和加密协议 |
| 🔔 **更新检测** | VueTorrent界面自动检测GitHub最新版本 |
| 🔄 **动态端口** | WebUI改端口后代理自动跟随，无需重启 |

---

## 🎨 双WebUI设计

安装后桌面显示**两个图标**，分别对应不同界面：

| 桌面图标 | 打开方式 | 说明 |
|----------|----------|------|
| **qBittorrent** | fnOS iframe（网关模式） | VueTorrent现代界面（推荐） |
| **原生界面** | 浏览器新标签页（网关模式） | qBittorrent原生WebUI |

### 切换方法

两个图标可独立使用，无需切换。如需修改默认UI类型：

1. **应用设置**：系统设置 → 应用设置 → qBittorrent → 界面类型
2. **安装向导**：安装时选择界面类型（仅影响默认UI配置）

---

## 🏗️ 网关架构

```
用户浏览器 → fnOS网关(5666) → qbittorrent.sock → Python反向代理 → 127.0.0.1:8080 → qbittorrent-nox
```

代理功能：
- 自动剥离 `/app/qbittorrent` 路径前缀
- 拦截 `fetch`/`XMLHttpRequest`/`WebSocket` 中的绝对路径请求
- 重写HTML中的 `src`/`href`/`action` 绝对路径
- 动态读取配置文件端口，WebUI改端口后自动生效

---

## 📦 安装与更新

> **系统要求**：fnOS v1.1.31+（需要统一网关支持）

### 手动安装/更新

1. 打开 **应用中心** → 左下角 **手动安装**
2. 选择 `qbittorrent-vuetorrent-5.2.0.1-amd64.fpk` 文件

或命令行：

```bash
appcenter-cli install-local qbittorrent-vuetorrent-5.2.0.1-amd64.fpk
```

---

## 🏗️ 本地构建

### Windows (PowerShell)

```powershell
.\build.ps1 -Version 5.2.0.1 -Arch amd64
```

### Linux (Bash)

```bash
chmod +x build.sh
./build.sh --version 5.2.0.1 --arch amd64
```

**构建特性**：
- 自动获取对应版本的qBittorrent-nox和VueTorrent
- 智能代理策略：gh-proxy.org → ghfast.top 自动切换
- 自动注入更新检测脚本到VueTorrent

---

## 🔄 升级与数据保留

- **升级前**：自动将数据备份到共享目录
- **升级后**：自动从备份恢复数据
- **卸载时**：可选择保留或删除数据

---

## 💻 默认配置

| 项目 | 默认值 |
|------|--------|
| 系统版本 | fnOS v1.1.31+ |
| 访问地址(VueTorrent) | `http://<NAS_IP>:5666/app/qbittorrent/` |
| 访问地址(原生UI) | `http://<NAS_IP>:5666/app/qbittorrent/` (新标签页) |
| 默认用户名 | `admin` |
| 默认密码 | `adminadmin` |

> ⚠️ **安全提示**：首次登录后请立即修改默认密码！

---

## 📋 更新日志

| 版本 | 更新内容 |
|------|----------|
| v5.2.0.2 | 接入fnOS统一网关；VueTorrent iframe / 原生UI新标签页；Python反向代理；动态端口跟随；@appshare目录自动创建 |
| v5.2.0.0 | 升级至qBittorrent 5.2.0 |
| v5.1.4.3 | 修复与系统下载进程冲突；安装时需配置下载目录 |

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
│   │   └── gateway-proxy.py       # Python反向代理（网关模式）
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
│   ├── config_callback            # 配置变更
│   ├── upgrade_init               # 升级前备份
│   ├── upgrade_callback           # 升级后恢复
│   ├── uninstall_init             # 卸载初始化
│   └── uninstall_callback         # 卸载清理
├── config/
│   ├── privilege                  # 权限配置
│   └── resource                   # 资源映射
├── wizard/
│   ├── install                    # 安装向导
│   ├── config                     # 配置向导
│   ├── uninstall                  # 卸载向导
│   └── upgrade                    # 升级向导
├── build.ps1                      # Windows构建脚本
├── build.sh                       # Linux构建脚本
├── manifest                       # 应用清单
└── README.md
```

## 📄 许可证

本项目基于 [GPL-2.0](LICENSE) 许可证开源。
