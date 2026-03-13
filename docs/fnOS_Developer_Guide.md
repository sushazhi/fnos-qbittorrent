# fnOS 应用开发完整指南

> 本文档整理自 fnOS 官方开发文档 (https://developer.fnnas.com/docs/guide)，适用于 AI 辅助开发

## 目录

1. [概述](#概述)
2. [快速开始](#快速开始)
3. [应用结构](#应用结构)
4. [生命周期脚本](#生命周期脚本)
5. [配置文件](#配置文件)
6. [向导界面](#向导界面)
7. [环境变量](#环境变量)
8. [开发工具](#开发工具)
9. [最佳实践](#最佳实践)
10. [常见问题](#常见问题)

---

## 概述

### 关于 fnOS

飞牛 fnOS 是一款年轻而强大的 NAS 操作系统。自2024年8月开放公测以来，截止2025年8月公测一周年之际，系统装机量已经超过 **90万**，APP设备数也已突破 **120万**。

我们的目标很简单：把飞牛 fnOS 打造成 **"存储系统界的 Windows"**。

**系统架构:**
- **Linux 内核版本**: 当前飞牛 fnOS 最新内核版本为 6.12.18
- **系统架构支持**: 当前飞牛 fnOS 仅支持 x86_64 (AMD64) 设备安装
- **GLIBC 版本**: 飞牛 NAS 的 GLIBC 版本为 2.36

### 为什么在 fnOS 上开发应用?

#### 1. 数据安全与隐私
- 数据在本地自主管理，避免不必要的外部依赖
- 可控的访问与授权，满足个人与企业的隐私诉求

#### 2. 私有本地服务器，场景丰富
- **家庭娱乐中心**: 支持在不同设备里播放 NAS 中的照片、视频与音乐
- **本地 AI 与算力**: 部署智能相册等本地应用，享受 AI 的便利，同时数据不外流
- **备份与同步枢纽**: 手机与电脑自动/定时备份，并提供版本快照功能

#### 3. 企业级能力与扩展
- **文件共享与协作**: 支持多人文件共享和权限精细化管理
- **数字化办公**: 可将 NAS 作为数字化办公的存储容器
- **定制工作台**: 通过应用中心和Docker快速部署各种应用服务

### 什么是 fnOS 应用?

fnOS 应用是一个独立的 `.fpk` 包，包含应用的所有资源、配置和生命周期管理脚本。每个应用都运行在隔离的环境中，确保系统的稳定性和安全性。

### 核心概念

- **应用包 (.fpk)**: fnOS 应用标准格式，类似 Docker 镜像
- **生命周期脚本**: 控制应用安装、启动、停止、升级、卸载的脚本
- **向导界面**: 用户交互界面，用于配置应用参数
- **环境变量**: fnOS 提供的标准变量，用于定位路径和配置
- **fnpack**: 官方提供的应用打包工具
- **appcenter-cli**: 应用中心命令行工具

---

## 快速开始

### 开发环境要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+) 或 Windows (WSL2)
- **系统版本**: 飞牛 fnOS 0.9.27 及以上版本
- **存储空间**: 至少创建一个存储空间，可用于安装应用
- **管理员权限**: 拥有该设备的管理权限
- **必需工具**:
  - `bash` (4.0+)
  - `curl` 或 `wget`
  - `fnpack` (官方打包工具)
  - `appcenter-cli` (已在飞牛 fnOS 环境中预装)

### 安装开发工具

#### 下载 fnpack

`fnpack` 已预置到飞牛 fnOS 中，同时也支持在本地使用，可根据操作系统进行下载：

```bash
# Windows x86
curl -fsSL -o fnpack.exe https://static2.fnnas.com/fnpack/fnpack-1.2.1-windows-amd64

# Linux x86
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-amd64

# Linux ARM
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-arm64

# Mac Intel
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-darwin-amd64

# Mac M系列
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-darwin-arm64

# 添加执行权限 (Linux/macOS)
chmod +x fnpack

# 移动到系统路径
sudo mv fnpack /usr/local/bin/
```

#### 安装 appcenter-cli

`appcenter-cli` 已在飞牛 fnOS 环境中预装，无需额外安装。

如果您需要在开发环境中安装，可以从官方下载:

```bash
# 下载二进制文件
curl -fsSL -o appcenter-cli https://static2.fnnas.com/cli/appcenter-cli-latest-linux-amd64

# 添加执行权限
chmod +x appcenter-cli

# 移动到系统路径
sudo mv appcenter-cli /usr/local/bin/
```

### 创建第一个应用

#### 1. 创建项目目录

```bash
mkdir my-first-app
cd my-first-app
```

#### 2. 创建必需文件

```bash
# 创建目录结构
mkdir -p cmd config wizard app/bin app/ui

# 创建 manifest
cat > manifest << EOF
appname = myapp
version = 1.0.0
display_name = My First App
desc = 我的第一个 fnOS 应用
platform = all
os_min_version = 1.1.19
source = thirdparty
maintainer = Your Name
maintainer_url = https://github.com/yourname
EOF

# 创建权限配置
cat > config/privilege << EOF
{
    "defaults": {
        "run-as": "package"
    }
}
EOF

# 创建资源配置
cat > config/resource << EOF
{
    "data-share": {
        "shares": [
            {
                "name": "myapp",
                "permission": {
                    "rw": ["myapp"]
                }
            }
        ]
    }
}
EOF

# 创建主脚本
cat > cmd/main << 'EOF'
#!/bin/bash
APP_NAME="myapp"
PID_FILE="${TRIM_PKGTMP}/${APP_NAME}.pid"

case "$1" in
    start)
        echo "Starting $APP_NAME..."
        # 启动逻辑
        echo $! > "$PID_FILE"
        echo "$APP_NAME started"
        ;;
    stop)
        echo "Stopping $APP_NAME..."
        rm -f "$PID_FILE"
        echo "$APP_NAME stopped"
        ;;
    restart)
        "$0" stop
        sleep 1
        "$0" start
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            echo "$APP_NAME is running"
            exit 0
        else
            echo "$APP_NAME is not running"
            exit 3
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
EOF

chmod +x cmd/main

# 创建图标 (需要实际图片文件)
# 这里使用占位符，实际开发需要提供真实图标
touch ICON.PNG ICON_256.PNG
```

#### 3. 打包应用

```bash
# 使用 fnpack 打包
fnpack build .

# 生成的 .fpk 文件
ls -lh *.fpk
```

#### 4. 测试应用

```bash
# 安装到本地 fnOS 系统
appcenter-cli install-local myapp-1.0.0.fpk

# 或通过 Web 界面安装
# 访问 http://your-nas-ip 应用中心 -> 手动安装
```

---

## 应用结构

### 标准目录结构

**开发时目录结构：**

```
my-app/
├── manifest              # 应用清单文件 (必需)
├── ICON.PNG              # 应用图标 64x64 (必需)
├── ICON_256.PNG          # 应用图标 256x256 (必需)
├── LICENSE               # 许可证文件 (推荐)
├── README.md             # 说明文档 (推荐)
│
├── cmd/                  # 生命周期脚本目录 (必需)
│   ├── main              # 主控制脚本 (必需)
│   ├── install_init      # 安装前脚本
│   ├── install_callback  # 安装后脚本
│   ├── config_init       # 配置前脚本
│   ├── config_callback   # 配置后脚本
│   ├── upgrade_init      # 升级前脚本
│   ├── upgrade_callback  # 升级后脚本
│   ├── uninstall_init    # 卸载前脚本
│   └── uninstall_callback # 卸载后脚本
│
├── config/               # 配置文件目录 (必需)
│   ├── privilege         # 权限配置 (必需)
│   └── resource          # 资源配置 (必需)
│
├── wizard/               # 向导界面目录 (必需)
│   ├── install           # 安装向导
│   ├── config            # 配置向导
│   ├── upgrade           # 升级向导
│   └── uninstall         # 卸载向导
│
├── app/                  # 应用资源目录
│   ├── bin/              # 可执行文件
│   ├── ui/               # WebUI 资源
│   └── ...               # 其他应用资源
│
└── docs/                 # 文档目录 (可选)
    ├── README.md
    └── ...
```

**安装后目录结构：**

```
/var/apps/[appname]/
├── cmd/                  # 生命周期脚本
│   ├── main
│   ├── install_init
│   ├── install_callback
│   └── ...
├── config/
│   ├── privilege
│   └── resource
├── ICON.PNG
├── ICON_256.PNG
├── LICENSE
├── manifest
├── etc -> /vol[volume_number]/@appconf/[appname]      # 静态配置文件
├── home -> /vol[volume_number]/@apphome/[appname]     # 用户数据文件
├── target -> /vol[volume_number]/@appcenter/[appname] # 应用可执行文件
├── tmp -> /vol[volume_number]/@apptemp/[appname]      # 临时文件
├── var -> /vol[volume_number]/@appdata/[appname]      # 运行时动态数据
├── shares/                                             # 数据共享目录
│   ├── datashare1 -> /vol[volume_number]/@appshare/datashare1
│   └── datashare2 -> /vol[volume_number]/@appshare/datashare2
└── wizard/
    ├── install
    ├── uninstall
    ├── upgrade
    └── config
```

### 目录功能说明

**开发者定义目录：**

| 目录 | 说明 |
|------|------|
| `cmd` | 存放应用生命周期管理的脚本文件 |
| `wizard` | 存放用户交互向导的配置文件 |

**系统自动创建目录：**

| 目录 | 说明 |
|------|------|
| `target` | 应用可执行文件的存放位置 |
| `etc` | 静态配置文件存放位置 |
| `var` | 运行时动态数据存放位置 |
| `tmp` | 临时文件存放位置 |
| `home` | 用户数据文件存放位置 |
| `meta` | 应用元数据存放位置 |
| `shares` | 数据共享目录（根据 resource 配置自动创建）|

### 重要规则

1. **必需文件**: `manifest`, `ICON.PNG`, `ICON_256.PNG`, `cmd/main`, `config/privilege`, `config/resource`
2. **脚本权限**: 所有 `cmd/` 下的脚本必须可执行 (`chmod +x`)
3. **Shebang**: 所有脚本必须以 `#!/bin/bash` 开头
4. **编码**: 所有文本文件使用 UTF-8 编码
5. **行尾**: 使用 Unix 风格 (LF)，不要使用 Windows 风格 (CRLF)

---

## 生命周期脚本

### 脚本执行顺序

#### 安装流程
```
用户点击安装
    ↓
install_init (安装前)
    ↓
复制应用文件到系统
    ↓
install_callback (安装后)
    ↓
安装完成
```

#### 配置流程
```
用户修改配置
    ↓
config_init (配置前)
    ↓
应用配置变更
    ↓
config_callback (配置后)
    ↓
配置完成
```

#### 升级流程
```
用户点击升级
    ↓
upgrade_init (升级前)
    ↓
停止服务，备份数据
    ↓
替换应用文件
    ↓
upgrade_callback (升级后)
    ↓
恢复数据，启动服务
    ↓
升级完成
```

#### 卸载流程
```
用户点击卸载
    ↓
uninstall_init (卸载前)
    ↓
删除应用文件
    ↓
uninstall_callback (卸载后)
    ↓
卸载完成
```

### main 脚本 (必需)

**功能**: 应用生命周期主控制脚本

**参数**: `{start|stop|restart|status}`

**示例**:

```bash
#!/bin/bash
# cmd/main - 应用生命周期管理脚本

APP_NAME="myapp"
BIN_DIR="${TRIM_APPDEST}/bin"
DATA_DIR="${TRIM_PKGVAR}"
CONFIG_FILE="${DATA_DIR}/config.conf"
PID_FILE="${TRIM_PKGTMP}/${APP_NAME}.pid"
LOG_FILE="${TRIM_PKGVAR}/${APP_NAME}.log"

case "$1" in
    start)
        # 检查是否已运行
        if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
            echo "$APP_NAME is already running"
            exit 0
        fi
        
        # 创建必要目录
        mkdir -p "$DATA_DIR"
        
        # 启动应用
        "$BIN_DIR/myapp" --config="$CONFIG_FILE" >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        
        # 验证启动
        sleep 2
        if ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
            echo "$APP_NAME started successfully"
            exit 0
        else
            echo "Failed to start $APP_NAME" >&2
            exit 1
        fi
        ;;
    
    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo "$APP_NAME is not running"
            exit 0
        fi
        
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null || true
        
        # 等待进程结束
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done
        
        # 强制终止
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null || true
        fi
        
        rm -f "$PID_FILE"
        echo "$APP_NAME stopped"
        exit 0
        ;;
    
    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;
    
    status)
        if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
            echo "$APP_NAME is running (PID: $(cat $PID_FILE))"
            exit 0
        else
            echo "$APP_NAME is not running"
            exit 3
        fi
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
```

### install_init 脚本

**功能**: 安装前准备工作

**执行时机**: 复制应用文件之前

**典型用途**:
- 检查系统依赖
- 预创建目录
- 检查端口占用

**示例**:

```bash
#!/bin/bash
# cmd/install_init

echo "Preparing installation..."

# 检查依赖
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is required" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi

# 检查端口
PORT="${wizard_app_port:-8080}"
if netstat -tuln | grep -q ":$PORT "; then
    echo "Error: Port $PORT is already in use" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi

echo "Installation preparation completed"
exit 0
```

### install_callback 脚本

**功能**: 安装后配置工作

**执行时机**: 复制应用文件之后

**典型用途**:
- 创建配置文件
- 设置权限
- 初始化数据库

**示例**:

```bash
#!/bin/bash
# cmd/install_callback

APP_NAME="myapp"
BIN_DIR="${TRIM_APPDEST}/bin"
CONFIG_DIR="${TRIM_PKGVAR}/config"
CONFIG_FILE="${CONFIG_DIR}/config.conf"

echo "Configuring $APP_NAME..."

# 设置可执行权限
chmod +x "$BIN_DIR/myapp"

# 创建配置目录
mkdir -p "$CONFIG_DIR"

# 创建默认配置
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
[settings]
port = ${wizard_app_port:-8080}
data_dir = ${TRIM_PKGVAR}/data
log_level = info
EOF
    echo "Default configuration created"
fi

echo "Installation completed"
exit 0
```

### config_init 脚本

**功能**: 配置变更前准备工作

**执行时机**: 应用配置变更之前

**典型用途**:
- 验证配置参数
- 备份当前配置

**示例**:

```bash
#!/bin/bash
# cmd/config_init

echo "Preparing configuration change..."

# 验证端口
PORT="${wizard_app_port:-8080}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Invalid port number" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi

echo "Configuration validation passed"
exit 0
```

### config_callback 脚本

**功能**: 配置变更后处理

**执行时机**: 应用配置变更之后

**典型用途**:
- 更新配置文件
- 重启服务
- 应用新配置

**示例**:

```bash
#!/bin/bash
# cmd/config_callback

APP_NAME="myapp"
CONFIG_FILE="${TRIM_PKGVAR}/config/config.conf"
MAIN_SCRIPT="/var/apps/$APP_NAME/cmd/main"

echo "Applying configuration changes..."

# 停止服务
"$MAIN_SCRIPT" stop
sleep 2

# 更新配置文件
sed -i "s/^port = .*/port = ${wizard_app_port:-8080}/" "$CONFIG_FILE"

# 启动服务
"$MAIN_SCRIPT" start

echo "Configuration applied successfully"
exit 0
```

### upgrade_init 脚本

**功能**: 升级前准备工作

**执行时机**: 替换应用文件之前

**典型用途**:
- 停止服务
- 备份数据
- 备份配置

**示例**:

```bash
#!/bin/bash
# cmd/upgrade_init

APP_NAME="myapp"
DATA_DIR="${TRIM_PKGVAR}"
BACKUP_DIR="/vol1/@appshare/$APP_NAME/.backup"
MAIN_SCRIPT="/var/apps/$APP_NAME/cmd/main"

echo "Preparing upgrade..."

# 停止服务
"$MAIN_SCRIPT" stop

# 备份数据
if [ -d "$DATA_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -a "$DATA_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
    echo "Data backed up to $BACKUP_DIR"
fi

echo "Upgrade preparation completed"
exit 0
```

### upgrade_callback 脚本

**功能**: 升级后处理工作

**执行时机**: 替换应用文件之后

**典型用途**:
- 恢复数据
- 迁移配置
- 启动服务

**示例**:

```bash
#!/bin/bash
# cmd/upgrade_callback

APP_NAME="myapp"
DATA_DIR="${TRIM_PKGVAR}"
BACKUP_DIR="/vol1/@appshare/$APP_NAME/.backup"
MAIN_SCRIPT="/var/apps/$APP_NAME/cmd/main"

echo "Completing upgrade..."

# 恢复数据
if [ -d "$BACKUP_DIR" ]; then
    cp -a "$BACKUP_DIR"/* "$DATA_DIR/" 2>/dev/null || true
    rm -rf "$BACKUP_DIR"
    echo "Data restored from backup"
fi

# 设置权限
chmod +x "${TRIM_APPDEST}/bin/myapp"

# 启动服务
"$MAIN_SCRIPT" start

echo "Upgrade completed successfully"
exit 0
```

### uninstall_init 脚本

**功能**: 卸载前准备工作

**执行时机**: 删除应用文件之前

**典型用途**:
- 停止服务
- 询问用户是否保留数据

**示例**:

```bash
#!/bin/bash
# cmd/uninstall_init

APP_NAME="myapp"
MAIN_SCRIPT="/var/apps/$APP_NAME/cmd/main"

echo "Preparing uninstallation..."

# 停止服务
"$MAIN_SCRIPT" stop

# 用户选择是否保留数据
DATA_ACTION="${wizard_data_action:-keep}"
if [ "$DATA_ACTION" = "delete" ]; then
    echo "User chose to delete all data"
else
    echo "User chose to keep data"
fi

echo "Uninstallation preparation completed"
exit 0
```

### uninstall_callback 脚本

**功能**: 卸载后清理工作

**执行时机**: 删除应用文件之后

**典型用途**:
- 清理临时文件
- 保留或删除数据

**示例**:

```bash
#!/bin/bash
# cmd/uninstall_callback

APP_NAME="myapp"
DATA_DIR="${TRIM_PKGVAR}"

echo "Completing uninstallation..."

# 根据用户选择处理数据
DATA_ACTION="${wizard_data_action:-keep}"
if [ "$DATA_ACTION" = "delete" ]; then
    rm -rf "$DATA_DIR"
    echo "All data deleted"
else
    echo "Data preserved at $DATA_DIR"
fi

echo "Uninstallation completed"
exit 0
```

---

## 配置文件

### manifest 文件 (必需)

**功能**: 应用清单，定义应用基本信息。就像应用的"身份证"，告诉系统应用是谁、需要什么、怎么运行。

**格式**: INI 格式

**必需字段**:

```ini
# 应用基本信息
appname = myapp                    # 应用名称 (只能包含小写字母、数字、下划线)
version = 1.0.0                    # 版本号 (语义化版本，格式: x[.y[.z]][-build])
display_name = My Application      # 显示名称
desc = 应用描述                    # 应用描述 (支持HTML)

# 系统要求
platform = all                     # 支持平台: x86, arm, loongarch, risc-v, all
os_min_version = 0.9.0            # 最低系统版本 (官方要求)
source = thirdparty               # 来源: thirdparty, official

# 开发者信息
maintainer = Developer Name       # 维护者
maintainer_url = https://...      # 维护者网址
distributor = Distributor Name    # 分发者
distributor_url = https://...     # 分发者网址

# 安装控制
ctl_stop = true                   # 是否显示启动/停止功能

# 端口配置 (可选)
service_port = ${wizard_app_port} # 服务端口 (支持向导变量)
checkport = true                  # 是否检查端口占用

# 桌面图标配置 (可选)
desktop_uidir = ui                # UI目录
desktop_applaunchname = myapp.Application  # 应用启动名

# 依赖管理 (可选)
install_dep_apps = mariaDB:redis  # 依赖应用列表，格式: app1>2.2.2:app2:app3

# 权限控制 (可选)
disable_authorization_path = false # 是否禁用授权目录功能

# 更新日志 (可选)
changelog = v1.0.0<br>首次发布
```

**字段详细说明**:

| 字段 | 说明 | 是否必需 |
|------|------|----------|
| `appname` | 应用唯一标识符，只能包含小写字母、数字、下划线 | 必需 |
| `version` | 版本号，格式: x[.y[.z]][-build] | 必需 |
| `display_name` | 应用中心显示的名称 | 必需 |
| `desc` | 应用介绍，支持 HTML 格式 | 必需 |
| `platform` | 架构类型: x86, arm, loongarch, risc-v, all | 必需 |
| `source` | 应用来源，固定为 thirdparty | 必需 |
| `os_min_version` | 支持的最低系统版本 | 推荐 |
| `os_max_version` | 支持的最高系统版本 | 可选 |
| `maintainer` | 开发者或开发团队名称 | 推荐 |
| `maintainer_url` | 开发者网站或联系方式 | 可选 |
| `distributor` | 应用发布者 | 可选 |
| `distributor_url` | 发布者网站 | 可选 |
| `ctl_stop` | 是否显示启动/停止功能，默认 true | 可选 |
| `install_type` | 安装类型，设为 root 时安装到系统分区 | 可选 |
| `install_dep_apps` | 依赖应用列表，格式: app1>2.2.2:app2:app3 | 可选 |
| `service_port` | 应用监听的端口号 | 可选 |
| `checkport` | 是否启用端口检查，默认 true | 可选 |
| `desktop_uidir` | UI 组件目录路径，默认 ui | 可选 |
| `desktop_applaunchname` | 应用启动入口 ID | 可选 |
| `disable_authorization_path` | 是否禁用授权目录功能，默认 false | 可选 |
| `changelog` | 应用更新日志 | 可选 |

**完整示例**:

```ini
appname = qbittorrent
version = 5.1.4.3
display_name = qBittorrent
desc = <b>功能强大的BitTorrent下载工具</b>，支持RSS订阅、搜索引擎、速度控制、WebUI远程访问。

# 系统要求
platform = all
os_min_version = 1.1.19
source = thirdparty

# 开发者信息
maintainer = qBittorrent
maintainer_url = https://github.com/qbittorrent/qBittorrent
distributor = yukihana
distributor_url = https://github.com/sushazhi/fnos-qbittorrent

# 安装控制
ctl_stop = true

# 端口配置
service_port = ${wizard_app_port}
checkport = true

# 桌面图标配置
desktop_uidir = ui
desktop_applaunchname = qbittorrent.Application

# 更新日志
changelog = v5.1.4.3<br>1. 修复了与系统下载进程冲突的问题
```

### privilege 文件 (必需)

**功能**: 定义应用权限

**格式**: JSON

**字段说明**:
- `run-as`: 运行身份 (`root` 或 `package`)

**示例**:

```json
{
    "defaults": {
        "run-as": "package"
    }
}
```

**权限说明**:
- `package`: 以应用用户身份运行 (推荐，更安全)
- `root`: 以root身份运行 (需要特殊权限)

### resource 文件 (必需)

**功能**: 定义应用需要的系统资源。就像应用的"能力清单"，告诉系统应用需要哪些额外的功能和权限。

**格式**: JSON

#### data-share - 数据共享

数据共享功能允许应用与用户共享特定的数据目录，让用户可以直接在文件管理器中访问和管理这些数据。

**特点**:
- 共享目录仅在系统管理员的文件管理 - 应用文件中可见
- 可以设置不同的访问权限：只读、读写
- 支持多级目录结构

**示例**:

```json
{
    "data-share": {
        "shares": [
            {
                "name": "documents",
                "permission": {
                    "rw": ["myapp_user"]
                }
            },
            {
                "name": "documents/backups",
                "permission": {
                    "ro": ["myapp_user"]
                }
            }
        ]
    }
}
```

**权限类型**:
- `rw` - 读写权限：应用可以读取和修改文件
- `ro` - 只读权限：应用只能读取文件，不能修改

#### usr-local-linker - 系统集成

系统集成功能允许应用在启动时创建软链接到系统目录，让其他应用或系统工具能够直接访问应用提供的功能。

**特点**:
- 应用启动时自动创建软链接
- 应用停止时自动移除软链接
- 支持 bin、lib、etc 三个系统目录

**示例**:

```json
{
    "usr-local-linker": {
        "bin": [
            "bin/myapp-cli",
            "bin/myapp-server"
        ],
        "lib": [
            "lib/mylib.so",
            "lib/mylib.a"
        ],
        "etc": [
            "etc/myapp.conf",
            "etc/myapp.d/default.conf"
        ]
    }
}
```

**链接说明**:
- `bin` - 可执行文件链接到 `/usr/local/bin/`
- `lib` - 库文件链接到 `/usr/local/lib/`
- `etc` - 配置文件链接到 `/usr/local/etc/`

#### docker-project - Docker 项目支持

Docker 项目支持让应用可以基于 Docker Compose 运行，支持复杂的容器编排和多服务架构。

**项目结构**:

```
myapp/
├── app/
│   └── docker/
│       └── docker-compose.yaml
├── manifest
├── cmd/
├── config/
└── ...
```

**Docker Compose 示例**:

```yaml
# app/docker/docker-compose.yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:80"
    volumes:
      - ./data:/app/data
    environment:
      - DB_HOST=db
      - DB_PORT=3306
    depends_on:
      - db
  db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=password
      - MYSQL_DATABASE=myapp
    volumes:
      - db_data:/var/lib/mysql
volumes:
  db_data:
```

**资源配置**:

```json
{
    "docker-project": {
        "projects": [
            {
                "name": "myapp-stack",
                "path": "docker"
            }
        ]
    }
}
```

**配置说明**:
- `name` - Docker Compose 项目的名称，用于标识和管理
- `path` - 相对于 app 目录的路径，指向包含 docker-compose.yaml 的文件夹

**完整示例**:

```json
{
    "data-share": {
        "shares": [
            {
                "name": "qbittorrent",
                "permission": {
                    "rw": ["qbittorrent"]
                }
            }
        ]
    }
}
```

---

## 向导界面

### 向导文件格式

**格式**: JSON 数组

**结构**:

```json
[
    {
        "stepTitle": "步骤标题",
        "items": [
            {
                "type": "组件类型",
                "field": "变量名",
                "label": "标签文本",
                "initValue": "初始值",
                "options": [...],
                "rules": [...]
            }
        ]
    }
]
```

### 支持的组件类型

#### 1. tips - 提示文本

```json
{
    "type": "tips",
    "helpText": "这是提示文本，支持 <b>HTML</b> 标签"
}
```

#### 2. text - 文本输入框

```json
{
    "type": "text",
    "field": "wizard_app_port",
    "label": "应用端口",
    "initValue": "8080",
    "rules": [
        {
            "required": true,
            "message": "请输入端口号"
        },
        {
            "pattern": "^[0-9]+$",
            "message": "端口号必须是数字"
        }
    ]
}
```

#### 3. radio - 单选框

```json
{
    "type": "radio",
    "field": "wizard_ui_type",
    "label": "界面类型",
    "initValue": "vuetorrent",
    "options": [
        {
            "label": "VueTorrent - 现代界面",
            "value": "vuetorrent"
        },
        {
            "label": "原生 WebUI - 经典界面",
            "value": "native"
        }
    ],
    "rules": [
        {
            "required": true,
            "message": "请选择界面类型"
        }
    ]
}
```

#### 4. select - 下拉选择框

```json
{
    "type": "select",
    "field": "wizard_theme",
    "label": "主题",
    "initValue": "light",
    "options": [
        {"label": "浅色主题", "value": "light"},
        {"label": "深色主题", "value": "dark"}
    ]
}
```

#### 5. checkbox - 复选框

```json
{
    "type": "checkbox",
    "field": "wizard_auto_start",
    "label": "开机自动启动",
    "initValue": true
}
```

#### 6. password - 密码输入框

```json
{
    "type": "password",
    "field": "wizard_password",
    "label": "管理员密码",
    "rules": [
        {
            "required": true,
            "message": "请输入密码"
        },
        {
            "min": 8,
            "message": "密码至少8个字符"
        }
    ]
}
```

### 验证规则

```json
{
    "required": true,           // 是否必填
    "message": "错误提示",      // 错误消息
    "pattern": "^[0-9]+$",     // 正则表达式
    "min": 1,                  // 最小值/最小长度
    "max": 65535               // 最大值/最大长度
}
```

### install 向导示例

```json
[
    {
        "stepTitle": "🚀 欢迎安装 My Application",
        "items": [
            {
                "type": "tips",
                "helpText": "✨ <b>功能强大的应用</b>"
            },
            {
                "type": "text",
                "field": "wizard_app_port",
                "label": "应用端口",
                "initValue": "8080",
                "rules": [
                    {
                        "required": true,
                        "message": "请输入端口号"
                    },
                    {
                        "pattern": "^[0-9]+$",
                        "message": "端口号必须是数字"
                    }
                ]
            },
            {
                "type": "radio",
                "field": "wizard_ui_type",
                "label": "界面类型",
                "initValue": "modern",
                "options": [
                    {"label": "现代界面", "value": "modern"},
                    {"label": "经典界面", "value": "classic"}
                ]
            }
        ]
    }
]
```

### config 向导示例

```json
[
    {
        "stepTitle": "⚙️ 应用设置",
        "items": [
            {
                "type": "tips",
                "helpText": "修改应用配置参数"
            },
            {
                "type": "text",
                "field": "wizard_app_port",
                "label": "应用端口",
                "initValue": "8080",
                "rules": [
                    {
                        "required": true,
                        "message": "请输入端口号"
                    }
                ]
            }
        ]
    }
]
```

### upgrade 向导示例

```json
[
    {
        "stepTitle": "🔄 升级应用",
        "items": [
            {
                "type": "tips",
                "helpText": "即将升级到新版本"
            },
            {
                "type": "radio",
                "field": "wizard_data_action",
                "label": "数据处理",
                "initValue": "keep",
                "options": [
                    {"label": "保留数据", "value": "keep"},
                    {"label": "删除数据", "value": "delete"}
                ]
            }
        ]
    }
]
```

### uninstall 向导示例

```json
[
    {
        "stepTitle": "🗑️ 卸载应用",
        "items": [
            {
                "type": "tips",
                "helpText": "确定要卸载此应用吗？"
            },
            {
                "type": "radio",
                "field": "wizard_data_action",
                "label": "数据处理",
                "initValue": "keep",
                "options": [
                    {"label": "保留数据", "value": "keep"},
                    {"label": "删除数据", "value": "delete"}
                ]
            }
        ]
    }
]
```

---

## 环境变量

### 标准环境变量

fnOS 为应用提供以下标准环境变量:

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `TRIM_APPNAME` | 应用名称（来自 manifest 中的 appname） | `myapp` |
| `TRIM_APPVER` | 应用版本号 | `1.0.0` |
| `TRIM_OLD_APPVER` | 升级前的版本号（仅在升级时可用） | `0.9.0` |
| `TRIM_APPDEST` | 应用安装目录 | `/var/apps/myapp` |
| `TRIM_PKGVAR` | 应用数据目录 | `/vol1/@appdata/myapp` |
| `TRIM_PKGTMP` | 应用临时目录 | `/vol1/@apptmp/myapp` |
| `TRIM_PKGETC` | 配置文件目录路径（etc 文件夹） | `/vol1/@appconf/myapp` |
| `TRIM_PKGHOME` | 用户数据目录路径（home 文件夹） | `/vol1/@apphome/myapp` |
| `TRIM_PKGMETA` | 元数据目录路径（meta 文件夹） | `/vol1/@appmeta/myapp` |
| `TRIM_APPDEST_VOL` | 应用安装的存储空间路径 | `/vol1` |
| `TRIM_SERVICE_PORT` | 服务端口 | `8080` |
| `TRIM_TEMP_LOGFILE` | 临时日志文件 | `/tmp/myapp.log` |
| `TRIM_TEMP_UPGRADE_FOLDER` | 升级过程的临时目录 | `/tmp/upgrade_myapp` |
| `TRIM_PKGINST_TEMP_DIR` | 安装包解压的临时目录 | `/tmp/install_myapp` |
| `TRIM_TEMP_TPKFILE` | fpk 包解压目录 | `/tmp/tpk_myapp` |
| `TRIM_USERNAME` | 应用用户名 | `myapp` |
| `TRIM_GROUPNAME` | 应用用户组 | `myapp` |
| `TRIM_UID` | 应用用户 ID | `1000` |
| `TRIM_GID` | 应用用户组 ID | `1000` |
| `TRIM_RUN_USERNAME` | 当前执行脚本的用户名 | `root` |
| `TRIM_RUN_GROUPNAME` | 当前执行脚本的用户组名 | `root` |
| `TRIM_RUN_UID` | 当前执行脚本的用户 ID | `0` |
| `TRIM_RUN_GID` | 当前执行脚本的用户组 ID | `0` |
| `TRIM_DATA_SHARE_PATHS` | 数据共享路径列表，多个路径用冒号分隔 | `/vol1/@appshare/myapp:/vol1/1000/downloads` |
| `TRIM_DATA_ACCESSIBLE_PATHS` | 可访问路径列表 | `/vol1/@appshare/myapp` |
| `TRIM_APP_STATUS` | 当前状态 (INSTALL/START/UPGRADE/UNINSTALL/STOP/CONFIG) | `START` |

### 系统相关环境变量

fnOS 还提供以下系统相关的环境变量:

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `TRIM_SYS_VERSION` | 完整的系统版本号 | `0.9.27` |
| `TRIM_SYS_VERSION_MAJOR` | 系统主版本号 | `0` |
| `TRIM_SYS_VERSION_MINOR` | 系统次版本号 | `9` |
| `TRIM_SYS_VERSION_BUILD` | 系统构建号 | `27` |
| `TRIM_SYS_ARCH` | 系统 CPU 架构（如 x86_64） | `x86_64` |
| `TRIM_KERNEL_VERSION` | 系统内核版本号 | `6.12.18` |
| `TRIM_SYS_MACHINE_ID` | 设备的唯一标识符 | `a1b2c3d4e5f6...` |
| `TRIM_SYS_LANGUAGE` | 系统语言设置 | `zh_CN` |

### 向导变量

向导中定义的变量会以 `wizard_` 前缀传递给脚本:

```bash
# 向导中定义: "field": "wizard_app_port"
# 脚本中使用:
PORT="${wizard_app_port:-8080}"
```

### 使用示例

```bash
#!/bin/bash

# 应用目录
APP_DIR="${TRIM_APPDEST}"
BIN_DIR="${APP_DIR}/bin"

# 数据目录
DATA_DIR="${TRIM_PKGVAR}"
CONFIG_DIR="${DATA_DIR}/config"

# 临时目录
TMP_DIR="${TRIM_PKGTMP}"
PID_FILE="${TMP_DIR}/myapp.pid"

# 端口配置
PORT="${wizard_app_port:-${TRIM_SERVICE_PORT:-8080}}"

# 日志文件
LOG_FILE="${DATA_DIR}/myapp.log"
ERROR_LOG="${TRIM_TEMP_LOGFILE}"

# 数据共享路径（取第一个路径）
if [ -n "$TRIM_DATA_SHARE_PATHS" ]; then
    SHARE_DIR="${TRIM_DATA_SHARE_PATHS%%:*}"
else
    SHARE_DIR="/vol1/@appshare/${APP_NAME}"
fi
```

---

## 开发工具

### fnpack - 应用打包工具

`fnpack` 是 fnOS 官方提供的应用打包工具,用于将应用目录打包成 `.fpk` 格式。

#### 安装 fnpack

```bash
# Linux AMD64
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-amd64

# Linux ARM64
curl -fsSL -o fnpack https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-arm64

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://static2.fnnas.com/fnpack/fnpack-1.2.1-windows-amd64.exe" -OutFile "fnpack.exe"

# 添加执行权限 (Linux/macOS)
chmod +x fnpack
sudo mv fnpack /usr/local/bin/
```

#### 使用 fnpack

```bash
# 基本用法
fnpack build <应用目录>

# 示例
fnpack build .

# 输出
# qbittorrent-5.1.4.3-arm64.fpk
```

#### fnpack 命令选项

```bash
fnpack [command] [options]

Commands:
  build <dir>    构建应用包
  version        显示版本信息
  help           显示帮助信息

Options:
  -o, --output   指定输出文件名
  -v, --verbose  详细输出模式
```

### appcenter-cli - 应用中心命令行工具

`appcenter-cli` 是用于管理 fnOS 应用的命令行工具。

#### 安装 appcenter-cli

```bash
# 下载二进制文件
curl -fsSL -o appcenter-cli https://static2.fnnas.com/cli/appcenter-cli-latest-linux-amd64

# 添加执行权限
chmod +x appcenter-cli

# 移动到系统路径
sudo mv appcenter-cli /usr/local/bin/
```

#### 常用命令

```bash
# 安装本地应用包
appcenter-cli install-fpk <app.fpk>

# 开启手动安装功能
appcenter-cli manual-install enable

# 查看已安装应用
appcenter-cli list

# 启动应用
appcenter-cli start <appname>

# 停止应用
appcenter-cli stop <appname>

# 重启应用
appcenter-cli restart <appname>

# 查看应用状态
appcenter-cli status <appname>

# 卸载应用
appcenter-cli uninstall <appname>

# 查看应用日志
appcenter-cli logs <appname>
```

### 调试技巧

#### 1. 本地测试脚本

```bash
# 设置环境变量进行本地测试
export TRIM_APPDEST="/tmp/test-app"
export TRIM_PKGVAR="/tmp/test-data"
export TRIM_PKGTMP="/tmp/test-tmp"
export TRIM_TEMP_LOGFILE="/tmp/test.log"

# 运行脚本
./cmd/main start
./cmd/main status
./cmd/main stop
```

#### 2. 查看应用日志

```bash
# 应用日志位置
tail -f ${TRIM_PKGVAR}/myapp.log

# 系统日志
journalctl -u myapp -f

# 或使用 appcenter-cli
appcenter-cli logs myapp
```

#### 3. 验证应用包

```bash
# 解压 .fpk 文件查看内容
fnpack extract myapp.fpk -d extracted/

# 检查文件结构
tree extracted/

# 验证 manifest
cat extracted/manifest
```

#### 4. 常见调试命令

```bash
# 检查进程
ps aux | grep myapp

# 检查端口
netstat -tuln | grep 8080
ss -tuln | grep 8080

# 检查文件权限
ls -la ${TRIM_APPDEST}/bin/
ls -la ${TRIM_PKGVAR}/

# 检查磁盘空间
df -h ${TRIM_PKGVAR}
```

---

## 最佳实践

### 1. 脚本编写规范

#### 使用 set 选项

```bash
#!/bin/bash
set -o pipefail  # 管道命令任一失败即返回失败
```

#### 错误处理

**版本要求**: V1.1.8+

`TRIM_TEMP_LOGFILE` 是系统日志文件路径（用户可见的日志），用于向前端展示错误信息。

**支持的脚本**:

| 脚本 | 说明 |
|------|------|
| `cmd/main` | 运行状态管理脚本 |
| `cmd/install_init` | 安装前准备 |
| `cmd/install_callback` | 安装后配置 |
| `cmd/upgrade_init` | 升级前准备 |
| `cmd/upgrade_callback` | 升级后处理 |

**不支持的脚本**: `cmd/config_*`、`cmd/uninstall_*`

**工作机制**:

```
脚本执行遇到错误
       ↓
写入错误日志到 $TRIM_TEMP_LOGFILE
       ↓
exit 1 返回错误码
       ↓
系统自动捕获
       ↓
前端 Dialog 对话框展示给用户
```

**使用示例**:

```bash
# 推荐方式
if ! mkdir -p "$DATA_DIR"; then
    echo "Error: Failed to create directory" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi

# 或使用 || 操作符
mkdir -p "$DATA_DIR" || {
    echo "Error: Failed to create directory" > "$TRIM_TEMP_LOGFILE"
    exit 1
}

# 检查依赖
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is required" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi

# 检查端口占用
if netstat -tuln | grep -q ":$PORT "; then
    echo "Error: Port $PORT is already in use" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi
```

**注意事项**:
- 必须配合 `exit 1` 才能触发前端展示
- 错误信息会直接展示给用户，建议使用清晰易懂的描述

#### 日志记录

```bash
# 定义日志函数
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
    [ -n "$TRIM_TEMP_LOGFILE" ] && echo "[ERROR] $1" >> "$TRIM_TEMP_LOGFILE"
}

# 使用
log_info "Starting application..."
log_error "Failed to start application"
```

### 2. 进程管理

#### 检查进程是否运行

```bash
# 方法1: 通过PID文件
if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
    echo "Application is running"
fi

# 方法2: 通过进程名和参数
PID=$(pgrep -f "myapp.*--config.*$CONFIG_FILE" | head -1)
if [ -n "$PID" ]; then
    echo "Application is running (PID: $PID)"
fi
```

#### 优雅停止进程

```bash
# 发送SIGTERM信号
kill "$PID" 2>/dev/null || true

# 等待进程结束
TIMEOUT=10
for i in $(seq 1 $((TIMEOUT * 2))); do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# 如果还在运行，强制终止
if ps -p "$PID" > /dev/null 2>&1; then
    kill -9 "$PID" 2>/dev/null || true
fi
```

### 3. 配置文件管理

#### 创建默认配置

```bash
create_default_config() {
    local port="$1"
    local config_file="$2"
    
    cat > "$config_file" << EOF
[settings]
port = ${port}
data_dir = ${TRIM_PKGVAR}/data
log_level = info
EOF
}
```

#### 更新配置文件

```bash
update_config() {
    local key="$1"
    local value="$2"
    local config_file="$3"
    
    # 使用 sed 更新
    sed -i "s/^${key} = .*/${key} = ${value}/" "$config_file"
    
    # 或使用 awk 更新
    awk -v key="$key" -v value="$value" '
        $1 == key { print key " = " value; next }
        { print }
    ' "$config_file" > "${config_file}.tmp" && mv "${config_file}.tmp" "$config_file"
}
```

### 4. 数据备份与恢复

#### 备份数据

```bash
backup_data() {
    local data_dir="$1"
    local backup_dir="$2"
    
    mkdir -p "$backup_dir"
    
    # 使用 tar 打包
    tar -czf "${backup_dir}/data_$(date +%Y%m%d_%H%M%S).tar.gz" \
        -C "$(dirname $data_dir)" "$(basename $data_dir)"
    
    # 或直接复制
    cp -a "$data_dir"/* "$backup_dir/"
}
```

#### 恢复数据

```bash
restore_data() {
    local backup_dir="$1"
    local data_dir="$2"
    
    # 从 tar 包恢复
    local latest_backup=$(ls -t "${backup_dir}"/data_*.tar.gz | head -1)
    if [ -n "$latest_backup" ]; then
        tar -xzf "$latest_backup" -C "$(dirname $data_dir)"
    fi
    
    # 或从目录恢复
    if [ -d "$backup_dir" ]; then
        cp -a "$backup_dir"/* "$data_dir/"
    fi
}
```

### 5. 端口检查

```bash
check_port_available() {
    local port="$1"
    
    # 使用 ss 命令
    if command -v ss > /dev/null 2>&1; then
        if ss -tuln | grep -q ":${port} "; then
            return 1  # 端口被占用
        fi
    # 使用 netstat 命令
    elif command -v netstat > /dev/null 2>&1; then
        if netstat -tuln | grep -q ":${port} "; then
            return 1  # 端口被占用
        fi
    fi
    
    return 0  # 端口可用
}

# 使用
if ! check_port_available "$PORT"; then
    echo "Error: Port $PORT is already in use" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi
```

### 6. 权限管理

```bash
# 设置文件所有者
chown -R "${TRIM_USERNAME}:${TRIM_GROUPNAME}" "$DATA_DIR"

# 设置可执行权限
chmod +x "${BIN_DIR}/myapp"

# 设置目录权限
chmod 755 "$DATA_DIR"
chmod 600 "$CONFIG_FILE"  # 配置文件仅所有者可读写
```

---

## 常见问题

### 1. 如何调试脚本?

```bash
# 添加调试输出
set -x  # 显示执行的每条命令
set -e  # 命令失败时立即退出

# 或在关键位置添加日志
echo "DEBUG: Variable value = $VAR" >&2
```

### 2. 如何处理多架构支持?

在 `manifest` 中设置:

```ini
platform = all  # 支持所有架构
# 或
platform = arm64  # 仅支持 ARM64
# 或
platform = amd64  # 仅支持 AMD64
```

在脚本中检测架构:

```bash
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        BINARY="myapp-x86_64"
        ;;
    aarch64)
        BINARY="myapp-arm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac
```

### 3. 如何处理配置文件版本兼容?

```bash
# 检查配置文件版本
CONFIG_VERSION=$(grep "^version" "$CONFIG_FILE" | cut -d'=' -f2 | tr -d ' ')

# 根据版本迁移配置
case "$CONFIG_VERSION" in
    1.0)
        migrate_from_1_0_to_1_1 "$CONFIG_FILE"
        ;&
    1.1)
        migrate_from_1_1_to_1_2 "$CONFIG_FILE"
        ;;
    1.2)
        # 当前版本，无需迁移
        ;;
    *)
        echo "Unknown config version: $CONFIG_VERSION" >&2
        exit 1
        ;;
esac
```

### 4. 如何处理服务依赖?

```bash
# 检查依赖服务
check_dependencies() {
    local deps=("docker" "nginx")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" > /dev/null 2>&1; then
            echo "Error: $dep is required but not installed" > "$TRIM_TEMP_LOGFILE"
            exit 1
        fi
    done
}

# 等待服务就绪
wait_for_service() {
    local service="$1"
    local timeout="${2:-30}"
    local count=0
    
    while [ $count -lt $timeout ]; do
        if systemctl is-active --quiet "$service"; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    
    return 1
}
```

### 5. 如何处理并发问题?

```bash
# 使用文件锁
LOCK_FILE="${TRIM_PKGTMP}/myapp.lock"

# 获取锁
exec 200>"$LOCK_FILE"
flock -w 10 200 || {
    echo "Error: Cannot acquire lock" >&2
    exit 1
}

# 执行关键操作
# ...

# 释放锁
flock -u 200
```

### 6. 如何优化脚本性能?

```bash
# 避免重复执行命令
# 不好的做法
if [ "$(cat $PID_FILE)" != "" ]; then
    PID=$(cat $PID_FILE)
    # ...
fi

# 好的做法
PID=$(cat "$PID_FILE" 2>/dev/null)
if [ -n "$PID" ]; then
    # ...
fi

# 使用内置命令代替外部命令
# 不好的做法
if [ "$(echo $VAR | grep 'pattern')" ]; then
    # ...
fi

# 好的做法
if [[ "$VAR" == *pattern* ]]; then
    # ...
fi

# 减少文件系统操作
# 批量操作
cat > "$CONFIG_FILE" << EOF
key1 = value1
key2 = value2
key3 = value3
EOF

# 而不是多次 echo
echo "key1 = value1" > "$CONFIG_FILE"
echo "key2 = value2" >> "$CONFIG_FILE"
echo "key3 = value3" >> "$CONFIG_FILE"
```

---

## 附录

### A. 完整应用示例

参考项目: [fnos-qbittorrent](https://github.com/sushazhi/fnos-qbittorrent)

### B. 相关资源

- [fnOS 官方网站](https://www.fnnas.com/)
- [fnOS 开发者文档](https://developer.fnnas.com/)
- [fnOS 论坛](https://club.fnnas.com/)

### C. 版本历史

- v1.0 - 初始版本
- v1.1 - 添加更多示例和最佳实践

---

**文档维护**: 本文档基于 fnOS 官方文档整理，适用于 AI 辅助开发。如有疑问，请参考官方文档或社区支持。
