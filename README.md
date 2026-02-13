# qBittorrent for fnOS 🚀

🌐 **语言/Language** 
 - [简体中文]( README.md ) | [English]( README_EN.md )

一款功能强大、美观易用的BitTorrent下载工具，飞牛NAS版。

![qBittorrent](https://img.shields.io/badge/qBittorrent-5.1.4.2-blue?style=flat-square&logo=qbittorrent)
![VueTorrent](https://img.shields.io/badge/VueTorrent-2.31.3-purple?style=flat-square&logo=vue.js)
![Platform](https://img.shields.io/badge/Platform-fnOS-green?style=flat-square&logo=nas)
![License](https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square)

---

## ✨ 特色功能

| 功能 | 说明 |
|------|------|
| 🎯 **双WebUI** | 默认启用VueTorrent现代界面，可切换原生界面 |
| 📡 **完整BT协议** | 支持BitTorrent v1/v2，DHT/PEX/LSD P2P网络 |
| 📰 **RSS订阅** | 支持RSS自动下载，订阅管理 |
| 🔍 **搜索引擎** | 内置多引擎搜索，聚合结果 |
| ⚡ **速度控制** | 灵活的速度限制和队列管理 |
| 🌐 **远程访问** | 内置Web界面，随时随地管理 |
| 📁 **文件管理** | 顺序下载、选择性下载、文件优先级 |
| 🛡️ **IP过滤** | 支持IP过滤列表和加密协议 |
| 🔔 **更新检测** | VueTorrent 界面自动检测 GitHub 最新版本 |
| 🔧 **端口配置** | 安装或应用设置中自定义端口 |

---

## 🎨 双WebUI设计

本应用包含**两套精美界面**，默认使用VueTorrent：

| 界面 | 特点 |
|------|------|
| **VueTorrent** ✨ | 现代美观、响应式设计、Vue 3 + Vuetify 3、多语言支持（推荐） |
| **qBittorrent原生** | 功能完整、轻量快速、经典界面 |

### UI切换方法

本应用提供**三种方式**切换界面：

#### 方式一：安装向导（推荐）

在安装应用时，选择 **界面类型**：
- VueTorrent（推荐）- 现代美观的Vue 3界面
- qBittorrent原生 - 经典的原生界面

#### 方式二：应用设置

在飞牛NAS**应用设置**中修改：
1. 进入应用中心
2. 找到 qBittorrent
3. 点击 **设置**
4. 选择 **界面类型**：VueTorrent 或 原生界面
5. 保存后重启应用生效

#### 方式三：WebUI内切换

进入 qBittorrent → 设置 → Web UI → 取消勾选"使用备用Web UI"

> ⚠️ **注意**：使用原生UI时，必须**新标签页打开**进入设置页面，在飞牛的iframe窗口内无法访问设置。

---

## 📦 安装与更新

> 📌 **注意**：本应用目前**仅支持ARM64架构**，系统要求 **fnOS v1.1.19+**。

### 手动安装/更新

1. 打开 **应用中心**
2. 左下角点击 **手动安装**
3. 选择 `qbittorrent-vuetorrent-5.1.4.2-arm64.fpk` 文件

或使用命令行：

```bash
appcenter-cli install-local qbittorrent-vuetorrent-5.1.4.2-arm64.fpk
```

---

## 🏗️ 本地构建

### Windows 本地构建

在 Windows 上使用 PowerShell 构建：

```powershell
# 1. 打开 PowerShell（以管理员身份运行）
# 2. 进入项目目录
cd C:\Path\To\fnos-qbittorrent

# 3. 执行构建
.\build.ps1
```

### Linux 本地构建

在 Linux 上使用 Bash 构建：

```bash
# 1. 添加执行权限
chmod +x build.sh

# 2. 执行构建（默认 arm64）
./build.sh

# 3. 或指定架构
./build.sh --arch arm64   # ARM64
./build.sh --arch amd64   # AMD64
./build.sh --force        # 强制重新下载所有文件
```

### 构建说明

- 构建脚本会自动从 manifest 读取版本号
- 自动下载 VueTorrent WebUI 和 qBittorrent 源码
- 自动注入更新检测脚本到 VueTorrent
- 生成的 fpk 文件可直接安装

### 输出文件

| 架构 | 输出文件 |
|------|----------|
| ARM64 | `qbittorrent-vuetorrent-<版本>-arm64.fpk` |
| AMD64 | `qbittorrent-vuetorrent-<版本>-amd64.fpk` |

---

## 🔄 升级与数据保留

### 升级数据保护

升级时应用会自动保护您的数据：

1. **升级前**：自动将数据备份到共享目录
2. **升级后**：自动从备份恢复数据
3. **选择权**：升级时可选择"保留数据"或"删除数据"

> 📌 **注意**：fnOS 升级时会清理数据目录，应用通过备份机制保护您的种子、RSS订阅和配置。

### 卸载数据保留

卸载时同样提供数据保留选项：

- **保留数据**：卸载后重新安装可恢复所有数据
- **删除数据**：彻底清除所有数据

> 💡 **建议**：如非必要，卸载时选择"保留数据"，以便将来恢复。

---

## 💻 系统要求

| 项目 | 默认值 |
|------|--------|
| 系统版本 | fnOS v1.1.19+ |
| 访问地址 | `http://<你的NAS_IP>:<端口>` |
| 默认用户名 | `admin` |
| 默认密码 | `adminadmin` |
| 默认端口 | `8080` (可在安装或应用设置中修改) |

> ⚠️ **安全提示**：请首次登录后立即修改默认密码！
> 
> 📌 **端口修改**：安装或应用设置中可自定义端口，**请勿在WebUI中修改端口**，否则飞牛iframe窗口无法访问UI。

---

## 📋 更新日志

| 版本 | 更新内容 |
|------|----------|
| v5.1.4.2 | 支持安装和应用设置中选择界面类型(VueTorrent/原生)<br>端口/UI修改可在应用设置中操作，请勿在WebUI中修改端口 |
| v5.1.4.1 | 支持安装和应用设置中修改端口（请勿在WebUI中修改端口）<br>添加更新检测功能（VueTorrent界面自动检测GitHub最新版本）<br>默认以应用用户的身份运行 |

---

## 🤝 支持与反馈

- 🐛 [报告问题](https://github.com/sushazhi/fnos-qbittorrent/issues)
- 💬 [飞牛论坛](https://club.fnnas.com/)
- 📖 [fnOS开发文档](https://developer.fnnas.com/)

---

## 📁 项目结构

### 核心目录结构

```
fnos-qbittorrent/
├── app/                    # fnOS应用资源
│   ├── bin/                # 构建产生的可执行文件
│   │   └── qbittorrent-nox  # qBittorrent守护进程
│   └── ui/                  # WebUI资源
│       ├── vuetorrent/      # VueTorrent WebUI
│       └── www/            # qBittorrent原生WebUI
├── cmd/                    # fnOS 生命周期脚本
│   ├── config_callback     # 配置后置
│   ├── config_init         # 配置初始化
│   ├── install_init        # 安装前初始化
│   ├── install_callback    # 安装后回调
│   ├── main               # 主服务控制脚本
│   ├── uninstall_init      # 卸载前清理
│   ├── uninstall_callback  # 卸载后清理
│   ├── upgrade_init        # 升级前备份
│   └── upgrade_callback    # 升级后恢复
├── config/                 # 配置文件
│   ├── privilege           # 权限配置（端口、挂载点）
│   └── resource            # 资源映射配置
├── wizard/                 # 向导UI定义
│   ├── install             # 安装向导
│   ├── uninstall           # 卸载向导
│   └── upgrade             # 升级向导
├── manifest                # 应用清单文件
├── ICON.PNG                # 应用图标（64x64）
├── ICON_256.PNG            # 应用图标（256x256）
└── LICENSE                 # 许可证文件
```

## 📄 许可证

本项目基于 [GPL-2.0](LICENSE) 许可证开源。

**感谢**：
- [qBittorrent](https://www.qbittorrent.org/) - 强大的BitTorrent客户端
- [VueTorrent](https://github.com/VueTorrent/VueTorrent) - 精美的qBittorrent WebUI
- [qbittorrent-nox-static](https://userdocs.github.io/qbittorrent-nox-static/) - qBittorrent静态编译指南
- [fnOS](https://www.fnnas.com/) - 优秀的国产NAS系统


