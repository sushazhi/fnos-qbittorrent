# fnOS 应用开发指南

> 本文档整合飞牛官方开发文档，以 qBittorrent 项目作为参考示例。
> 
> **官方文档**: https://developer.fnnas.com/
> **参考项目**: qBittorrent for fnOS（本目录）

**文档版本**: 2.0
**最后更新**: 2025-02-14

---

## 目录

- [一、快速开始](#一快速开始)
- [二、应用架构](#二应用架构)
- [三、生命周期管理](#三生命周期管理)
- [四、Manifest 清单](#四manifest-清单)
- [五、环境变量](#五环境变量)
- [六、权限配置](#六权限配置)
- [七、资源配置](#七资源配置)
- [八、用户向导](#八用户向导)
- [九、应用入口](#九应用入口)
- [十、依赖管理](#十依赖管理)
- [十一、运行时环境](#十一运行时环境)
- [十二、中间件服务](#十二中间件服务)
- [十三、CLI 工具](#十三cli-工具)
- [十四、图标规范](#十四图标规范)
- [十五、Docker 应用](#十五docker-应用)
- [十六、Native 应用](#十六native-应用)
- [附录A：代码模板](#附录a代码模板)
- [附录B：检查清单](#附录b检查清单)

---

## 一、快速开始

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| 系统版本 | fnOS 0.9.27 及以上 |
| 存储空间 | 至少创建一个存储空间 |
| 权限 | 管理员权限 |
| 内核版本 | 6.12.18 |
| 系统架构 | x86_64 (AMD64) |

### 1.2 应用技术栈

fnOS 基于 Linux 内核（Debian 发行版）深度开发，支持多种技术栈：

**服务开发语言**：
- Node.js、Python、Java、Go
- 以及 Linux 运行时支持的其他语言

**前端开发语言**：
- HTML/JavaScript/CSS
- 以及现代浏览器支持的其他语言和框架

### 1.3 CLI 工具

| 工具 | 说明 |
|------|------|
| `fnpack` | 应用打包工具（需下载） |
| `appcenter-cli` | 应用中心命令行工具（fnOS 预装） |

### 1.4 开发流程

```
1. 创建项目 → fnpack create myapp
2. 编写代码 → manifest、cmd、wizard、config
3. 本地测试 → appcenter-cli install-local
4. 打包发布 → fnpack build
```

### 1.5 快速命令

```bash
# 创建项目
fnpack create myapp                    # 普通应用
fnpack create myapp --template docker  # Docker 应用
fnpack create myapp --without-ui true  # 无 UI 服务

# 打包
fnpack build

# 安装测试
appcenter-cli install-local           # 本地目录安装
appcenter-cli install-fpk myapp.fpk   # fpk 文件安装
```

### 1.6 查看日志

应用日志位置：
```bash
/var/apps/[appname]/var/info.log
```

---

## 二、应用架构

### 2.1 目录结构

```
myapp/
├── manifest                    # 应用清单（必需）
├── ICON.PNG                    # 图标 64x64（必需）
├── ICON_256.PNG                # 图标 256x256（必需）
├── LICENSE                     # 许可证（可选）
│
├── cmd/                        # 生命周期脚本（必需）
│   ├── main                    # start|stop|restart|status
│   ├── install_init            # 安装前
│   ├── install_callback        # 安装后
│   ├── config_init             # 配置初始化
│   ├── config_callback         # 配置变更
│   ├── upgrade_init            # 升级前
│   ├── upgrade_callback        # 升级后
│   ├── uninstall_init          # 卸载前
│   └── uninstall_callback      # 卸载后
│
├── config/
│   ├── privilege               # 权限配置（JSON）
│   └── resource                # 资源配置（JSON）
│
├── wizard/
│   ├── install                 # 安装向导
│   ├── config                  # 配置向导
│   ├── upgrade                 # 升级向导
│   └── uninstall               # 卸载向导
│
└── app/
    ├── bin/                    # 可执行文件
    ├── ui/                     # WebUI
    │   ├── images/
    │   └── config
    └── docker/                 # Docker 配置（可选）
```

> 📁 **参考示例**：本目录 `cmd/`、`config/`、`wizard/` 文件夹

### 2.2 安装后目录映射

| 符号链接 | 实际路径 | 说明 | 卸载时 |
|----------|----------|------|--------|
| `target` | `/vol[x]/@appcenter/[appname]` | 可执行文件 | 删除 |
| `etc` | `/vol[x]/@appconf/[appname]` | 静态配置 | 删除 |
| `tmp` | `/vol[x]/@apptemp/[appname]` | 临时文件 | 删除 |
| `home` | `/vol[x]/@apphome/[appname]` | 用户数据 | 删除 |
| `var` | `/vol[x]/@appdata/[appname]` | 动态数据 | **保留** |
| `shares` | `/vol[x]/@appshare/[sharename]` | 共享目录 | **保留** |

---

## 三、生命周期管理

### 3.1 安装流程

```
┌─────────────────┐
│  install_init   │  ← 环境检查、依赖验证
└────────┬────────┘
         ↓
┌─────────────────┐
│  文件解压       │  ← 系统自动处理
└────────┬────────┘
         ↓
┌─────────────────┐
│install_callback │  ← 创建配置、设置权限
└─────────────────┘
```

> 📁 **参考示例**：`cmd/install_init`、`cmd/install_callback`

### 3.2 卸载流程

```
┌─────────────────┐
│  检查运行状态   │
└────────┬────────┘
         ↓ 运行中
┌─────────────────┐
│   main stop     │
└────────┬────────┘
         ↓
┌─────────────────┐
│ uninstall_init  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  删除目录       │  ← target/tmp/home/etc（var/shares 保留）
└────────┬────────┘
         ↓
┌─────────────────┐
│uninstall_callback│
└─────────────────┘
```

> 📁 **参考示例**：`cmd/uninstall_init`、`cmd/uninstall_callback`

### 3.3 更新流程

```
┌─────────────────┐
│   main stop     │
└────────┬────────┘
         ↓
┌─────────────────┐
│  upgrade_init   │  ← 备份数据到 @appshare
└────────┬────────┘
         ↓
┌─────────────────┐
│  文件更新       │  ← 系统自动处理
└────────┬────────┘
         ↓
┌─────────────────┐
│upgrade_callback │  ← 恢复数据、设置权限
└────────┬────────┘
         ↓
┌─────────────────┐
│   main start    │
└─────────────────┘
```

> 📁 **参考示例**：`cmd/upgrade_init`、`cmd/upgrade_callback`

### 3.4 配置流程

```
┌─────────────────┐
│  用户修改配置   │  ← 系统设置 → 应用设置
└────────┬────────┘
         ↓
┌─────────────────┐
│  更新环境变量   │  ← 系统自动处理
└────────┬────────┘
         ↓
┌─────────────────┐
│   config_init   │
└────────┬────────┘
         ↓
┌─────────────────┐
│ config_callback │  ← 更新配置文件、重启服务
└─────────────────┘
```

> 📁 **参考示例**：`cmd/config_init`、`cmd/config_callback`

### 3.5 main 脚本

**基本结构**：

```bash
#!/bin/bash
case $1 in
start)
    # 启动逻辑，成功返回 0，失败返回 1
    exit 0
    ;;
stop)
    # 停止逻辑，成功返回 0，失败返回 1
    exit 0
    ;;
status)
    # 运行中返回 0，未运行返回 3
    exit 0
    ;;
*)
    exit 1
    ;;
esac
```

**状态码说明**：

| 命令 | exit 0 | exit 1 | exit 3 |
|------|--------|--------|--------|
| start | 启动成功 | 启动失败 | - |
| stop | 停止成功 | 停止失败 | - |
| status | 运行中 | - | 未运行 |

> 📁 **参考示例**：`cmd/main`

---

## 四、Manifest 清单

### 4.1 基本信息（必需）

| 字段 | 说明 | 示例 |
|------|------|------|
| `appname` | 唯一标识（小写无空格） | `myapp` |
| `version` | 版本号，格式 x[.y[.z]][-build] | `1.0.0` |
| `display_name` | 显示名称 | `我的应用` |
| `desc` | 应用介绍（支持 HTML） | `<b>功能...</b>` |
| `source` | 固定值 | `thirdparty` |

### 4.2 系统要求

| 字段 | 说明 | 示例 |
|------|------|------|
| `arch` | 架构类型（已废弃，使用 platform） | `x86_64` |
| `platform` | 架构：x86/arm/loongarch/risc-v/all | `all` |
| `os_min_version` | 最低系统版本 | `0.9.27` |
| `os_max_version` | 最高系统版本 | `1.1.100` |

**platform 说明**：
- `x86` - 仅支持 x86 架构
- `arm` - 仅支持 arm 架构
- `loongarch` - 仅支持 loongarch 架构（暂未支持）
- `risc-v` - 仅支持 risc-v 架构（暂未支持）
- `all` - 支持所有架构（如 Docker 应用）

### 4.3 开发者信息

| 字段 | 说明 |
|------|------|
| `maintainer` | 开发者名称 |
| `maintainer_url` | 开发者网站 |
| `distributor` | 发布者名称 |
| `distributor_url` | 发布者网站 |

### 4.4 安装和运行控制

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `ctl_stop` | 是否显示启动/停止功能 | `true` |
| `install_type` | 安装类型，`root` 安装到系统分区 | 空 |

**install_type 说明**：
- 为空时，用户可在安装向导中选择存储位置 `/vol${x}/@appcenter/`
- 设置为 `root` 时，应用安装到系统分区 `/usr/local/apps/@appcenter/`

### 4.5 界面配置

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `desktop_uidir` | UI 目录 | `ui` |
| `desktop_applaunchname` | 入口 ID | - |
| `service_port` | 服务端口（可引用向导变量） | - |
| `checkport` | 端口检查 | `true` |

### 4.6 权限控制

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `disable_authorization_path` | 是否禁用授权目录功能 | `false` |

### 4.7 依赖声明

| 字段 | 说明 | 示例 |
|------|------|------|
| `install_dep_apps` | 依赖应用列表 | `redis:nodejs_v22` |

**格式**：`app1>version:app2:app3`
**顺序**：从后往前安装

### 4.8 更新日志

| 字段 | 说明 |
|------|------|
| `changelog` | 应用更新日志（升级时展示） |

> 📁 **参考示例**：`manifest`

---

## 五、环境变量

### 5.1 路径变量

| 变量 | 说明 | 对应目录 |
|------|------|----------|
| `TRIM_APPDEST` | 可执行文件目录 | target |
| `TRIM_PKGETC` | 配置文件目录 | etc |
| `TRIM_PKGVAR` | 动态数据目录 | var |
| `TRIM_PKGTMP` | 临时文件目录 | tmp |
| `TRIM_PKGHOME` | 用户数据目录 | home |
| `TRIM_PKGMETA` | 元数据目录 | meta |
| `TRIM_APPDEST_VOL` | 应用安装的存储空间路径 | - |

### 5.2 应用变量

| 变量 | 说明 |
|------|------|
| `TRIM_APPNAME` | 应用名称 |
| `TRIM_APPVER` | 应用版本 |
| `TRIM_OLD_APPVER` | 升级前版本（仅升级时） |
| `TRIM_SERVICE_PORT` | 服务端口 |
| `TRIM_USERNAME` | 应用专用用户名 |
| `TRIM_GROUPNAME` | 应用专用用户组名 |
| `TRIM_UID` | 应用用户 ID |
| `TRIM_GID` | 应用用户组 ID |
| `TRIM_RUN_USERNAME` | 当前执行脚本的用户名 |
| `TRIM_RUN_GROUPNAME` | 当前执行脚本的用户组名 |
| `TRIM_RUN_UID` | 当前执行脚本的用户 ID |
| `TRIM_RUN_GID` | 当前执行脚本的用户组 ID |

### 5.3 系统变量

| 变量 | 说明 |
|------|------|
| `TRIM_SYS_VERSION` | 完整系统版本 |
| `TRIM_SYS_VERSION_MAJOR` | 系统主版本号 |
| `TRIM_SYS_VERSION_MINOR` | 系统次版本号 |
| `TRIM_SYS_VERSION_BUILD` | 系统构建版本号 |
| `TRIM_SYS_ARCH` | 系统架构（如 x86_64） |
| `TRIM_KERNEL_VERSION` | 系统内核版本号 |
| `TRIM_SYS_MACHINE_ID` | 设备唯一标识符 |
| `TRIM_SYS_LANGUAGE` | 系统语言 |

### 5.4 日志变量

| 变量 | 说明 |
|------|------|
| `TRIM_TEMP_LOGFILE` | 错误日志路径（用户可见） |

**使用方式**：写入错误信息后 `exit 1`，系统会弹窗显示。

```bash
if [ ! -f "$CONFIG" ]; then
    echo "配置文件不存在，启动失败！" > "$TRIM_TEMP_LOGFILE"
    exit 1
fi
```

**注意**：`TRIM_TEMP_LOGFILE` 在 `cmd/main`、`cmd/install_*`、`cmd/upgrade_*` 中有效，`cmd/config_*`、`cmd/uninstall_*` 暂不支持。

### 5.5 数据共享变量

| 变量 | 说明 |
|------|------|
| `TRIM_DATA_SHARE_PATHS` | 数据共享路径列表（冒号分隔） |
| `TRIM_DATA_ACCESSIBLE_PATHS` | 可访问路径列表（冒号分隔，V1.1.8+） |

### 5.6 临时目录变量

| 变量 | 说明 |
|------|------|
| `TRIM_TEMP_UPGRADE_FOLDER` | 升级过程临时目录 |
| `TRIM_PKGINST_TEMP_DIR` | 安装包解压临时目录 |
| `TRIM_TEMP_TPKFILE` | fpk 包解压目录 |

### 5.7 CMD 脚本变量

| 变量 | 说明 |
|------|------|
| `TRIM_APP_STATUS` | 当前状态（INSTALL/START/UPGRADE/UNINSTALL/STOP/CONFIG） |

### 5.8 向导变量

向导中的 `field` 直接成为环境变量：

```bash
# 向导定义：{"field": "wizard_port", "initValue": "8080"}
# 脚本使用：
PORT="${wizard_port:-8080}"
```

---

## 六、权限配置

### 6.1 默认模式（推荐）

```json
{
    "defaults": {
        "run-as": "package"
    }
}
```

特点：
- 系统创建专用用户和用户组
- 所有进程以专用用户身份运行
- 只能访问自己的目录

### 6.2 自定义用户

```json
{
    "defaults": {
        "run-as": "package"
    },
    "username": "myapp_user",
    "groupname": "myapp_group"
}
```

### 6.3 Root 模式

> 仅限官方合作开发者

```json
{
    "defaults": {
        "run-as": "root"
    }
}
```

### 6.4 外部文件访问权限

默认情况下，应用无法访问用户的个人文件。用户需要在应用设置中明确授权：

**授权方式**：
1. 用户在应用设置页面选择要授权的目录
2. 设置访问权限类型：
   - **读写权限**：应用可以读取和修改文件
   - **只读权限**：应用只能读取文件
   - **禁止访问**：应用无法访问该路径

**权限检查脚本**：
```bash
#!/bin/bash
echo "当前运行用户: $TRIM_RUN_USERNAME"
echo "应用专用用户: $TRIM_USERNAME"

if [ "$TRIM_RUN_USERNAME" = "root" ]; then
    echo "应用以 root 权限运行"
else
    echo "应用以应用用户权限运行"
fi
```

> 📁 **参考示例**：`config/privilege`

---

## 七、资源配置

### 7.1 数据共享 (data-share)

```json
{
    "data-share": {
        "shares": [
            {
                "name": "data",
                "permission": {
                    "rw": ["myapp"]
                }
            }
        ]
    }
}
```

**权限**：`rw`（读写）/ `ro`（只读）
**路径**：`/vol[x]/@appshare/[name]`

### 7.2 系统集成 (usr-local-linker)

```json
{
    "usr-local-linker": {
        "bin": ["bin/myapp-cli"],
        "lib": ["lib/mylib.so"],
        "etc": ["etc/myapp.conf"]
    }
}
```

**链接目标**：
- `bin` → `/usr/local/bin/`
- `lib` → `/usr/local/lib/`
- `etc` → `/usr/local/etc/`

### 7.3 Docker 项目 (docker-project)

```json
{
    "docker-project": {
        "projects": [
            {
                "name": "myapp",
                "path": "docker"
            }
        ]
    }
}
```

> 📁 **参考示例**：`config/resource`

---

## 八、用户向导

### 8.1 向导类型

| 文件 | 用途 |
|------|------|
| `wizard/install` | 安装向导 |
| `wizard/config` | 配置向导 |
| `wizard/upgrade` | 升级向导 |
| `wizard/uninstall` | 卸载向导 |

### 8.2 控件类型

| type | 说明 | 必需字段 |
|------|------|----------|
| `text` | 文本输入 | field, label, initValue |
| `password` | 密码输入 | field, label |
| `radio` | 单选 | field, label, options |
| `checkbox` | 多选 | field, label, options |
| `select` | 下拉选择 | field, label, options |
| `switch` | 开关 | field, label |
| `tips` | 提示文本 | helpText |

### 8.3 验证规则

```json
"rules": [
    {"required": true, "message": "必填"},
    {"min": 3, "max": 20, "message": "长度3-20"},
    {"pattern": "^[a-z]+$", "message": "只能小写字母"}
]
```

### 8.4 完整示例

```json
[
    {
        "stepTitle": "基本配置",
        "items": [
            {
                "type": "tips",
                "helpText": "请配置应用参数"
            },
            {
                "type": "text",
                "field": "wizard_port",
                "label": "端口",
                "initValue": "8080",
                "rules": [
                    {"required": true, "message": "请输入端口"}
                ]
            },
            {
                "type": "radio",
                "field": "wizard_mode",
                "label": "运行模式",
                "initValue": "standard",
                "options": [
                    {"label": "标准模式", "value": "standard"},
                    {"label": "高级模式", "value": "advanced"}
                ]
            }
        ]
    }
]
```

> 📁 **参考示例**：`wizard/install`、`wizard/config`、`wizard/upgrade`、`wizard/uninstall`

---

## 九、应用入口

### 9.1 配置文件

位置：`app/ui/config`

### 9.2 桌面图标入口

```json
{
    ".url": {
        "myapp.Application": {
            "title": "我的应用",
            "icon": "images/icon-{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "8080",
            "url": "/",
            "allUsers": true
        }
    }
}
```

**注意**：入口 ID 必须以 `appname` 为前缀，如 `myapp.Application`。

### 9.3 字段说明

| 字段 | 说明 |
|------|------|
| `title` | 显示标题 |
| `icon` | 图标路径，`{0}` 替换为尺寸（64 或 256） |
| `type` | `url`（新标签页）/ `iframe`（嵌入窗口） |
| `protocol` | `http` / `https` / `""`（自适应） |
| `port` | 端口，支持 `${wizard_port}` 环境变量（V1.1.8+） |
| `url` | 路径，支持 `${wizard_path}` 环境变量（V1.1.8+） |
| `allUsers` | `true` 所有人 / `false` 仅管理员 |

**protocol 说明**：
- `http` - 使用 HTTP 协议
- `https` - 使用 HTTPS 协议
- `""` - 自适应协议（注意：不声明 protocol 字段时默认为 `http`，而非自适应）

### 9.4 文件右键入口

```json
{
    ".url": {
        "myapp.Editor": {
            "title": "编辑器",
            "icon": "images/icon-{0}.png",
            "type": "url",
            "port": "8080",
            "url": "/edit",
            "fileTypes": ["txt", "md", "json"],
            "noDisplay": true
        }
    }
}
```

| 字段 | 说明 |
|------|------|
| `fileTypes` | 关联文件类型数组 |
| `noDisplay` | `true` 不在桌面显示，只在右键菜单显示 |

**URL 参数**：打开文件时自动添加 `?path=/path/to/file`

### 9.5 控制字段

```json
{
    "myapp.advanced": {
        "title": "高级功能",
        "icon": "images/advanced-{0}.png",
        "type": "iframe",
        "port": "8080",
        "url": "/advanced",
        "allUsers": false,
        "control": {
            "accessPerm": "readonly"
        }
    }
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `accessPerm` | 桌面访问权限：`editable`/`readonly`/`hidden` | `readonly` |

> 📁 **参考示例**：`app/ui/config`

---

## 十、依赖管理

### 10.1 声明依赖

```ini
install_dep_apps = redis:nodejs_v22:mariaDB>10.5
```

**格式**：`app1>version:app2:app3`
- `>` 表示最低版本要求
- `:` 分隔多个依赖

### 10.2 依赖顺序

**从后往前**安装：
```ini
# 正确：先安装 dep1，后安装 dep2
install_dep_apps = dep2:dep1

# 错误：如果 dep2 依赖 dep1，可能导致问题
install_dep_apps = dep1:dep2
```

### 10.3 嵌套依赖

应用中心仅检查一层依赖，不做递归检查。如果应用 A 依赖应用 B，应用 B 又依赖应用 C，则需要在应用 A 中同时声明 B 和 C：

```ini
# 嵌套依赖的平铺定义
install_dep_apps = depB:depC
```

### 10.4 依赖检查逻辑

应用中心在以下流程中自动检查依赖关系：

| 操作 | 检查逻辑 |
|------|----------|
| **安装/启用** | 检查依赖是否已安装启用，未安装则自动安装，未启用则自动启用 |
| **停用/卸载** | 检查是否有其他应用依赖当前应用，有则提示自动停用 |
| **更新** | 检查是否有其他应用依赖当前应用，有则提示更新期间自动停用 |

---

## 十一、运行时环境

### 11.1 Python

```ini
install_dep_apps = python312
```

**可用版本**：`python312`, `python311`, `python310`, `python39`, `python38`

```bash
export PATH=/var/apps/python312/target/bin:$PATH
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 11.2 Node.js

```ini
install_dep_apps = nodejs_v22
```

**可用版本**：`nodejs_v22`, `nodejs_v20`, `nodejs_v18`, `nodejs_v16`, `nodejs_v14`

```bash
export PATH=/var/apps/nodejs_v22/target/bin:$PATH
node -v
npm -v
```

### 11.3 Java

```ini
install_dep_apps = java-21-openjdk
```

**可用版本**：`java-21-openjdk`, `java-17-openjdk`, `java-11-openjdk`

```bash
export PATH=/var/apps/java-21-openjdk/target/bin:$PATH
java --version
```

---

## 十二、中间件服务

### 12.1 Redis

```ini
install_dep_apps = redis
```

**连接信息**：
- Host: `127.0.0.1`
- Port: `6379`

**Python 使用示例**：
```python
import redis

# 创建连接池，指定逻辑数据库（如 db=1），防止冲突
pool = redis.ConnectionPool(
    host='127.0.0.1',
    port=6379,
    db=1,  # 指定逻辑数据库，防止与其他应用冲突
    decode_responses=True,
    max_connections=10
)

# 从连接池获取连接
client = redis.Redis(connection_pool=pool)

# 使用连接
client.lpush('my_list', 'item1', 'item2')
items = client.lrange('my_list', 0, -1)
print(items)  # 输出: ['item2', 'item1']

# 不需要手动关闭连接，连接池会管理
```

### 12.2 MinIO

MinIO 是高性能、云原生的开源对象存储系统，完全兼容 Amazon S3 API。

```ini
install_dep_apps = minio
```

**连接信息**：
- Host: `127.0.0.1`
- Port: `9000`

**Python 使用示例**：
```python
from minio import Minio
from minio.error import S3Error

# 初始化客户端
client = Minio(
    endpoint="127.0.0.1:9000",
    access_key="your_access_key",   # MinIO 管理员用户名或 Access Key
    secret_key="your_secret_key",   # MinIO 管理员密码或 Secret Key
    secure=False                    # 本地测试通常为 False
)

# 定义桶名
bucket_name = "my-bucket"

# 创建 Bucket
try:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' 已创建")
    else:
        print(f"Bucket '{bucket_name}' 已存在")
except S3Error as err:
    print("创建 Bucket 时发生错误:", err)
```

### 12.3 RabbitMQ

```ini
install_dep_apps = rabbitmq
```

**连接信息**：
- Host: `127.0.0.1`
- Port: `5672`
- Virtual Host: `/`
- Username: `guest`
- Password: `guest`

**Python 使用示例**：
```python
import pika

# 创建连接
credentials = pika.PlainCredentials("guest", "guest")
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="127.0.0.1",
        port=5672,
        virtual_host="/",
        credentials=credentials
    )
)

channel = connection.channel()

# 声明队列
channel.queue_declare(queue="my_queue")

# 发送消息
channel.basic_publish(
    exchange="",
    routing_key="my_queue",
    body="Hello, RabbitMQ!"
)

print("消息已发送")

# 关闭连接
connection.close()
```

### 12.4 MariaDB

> 即将上线...

---

## 十三、CLI 工具

### 13.1 fnpack

fnpack 是飞牛 fnOS 应用打包工具，已预置到 fnOS 系统中，也支持本地使用。

**工具下载**：

| 平台 | 下载地址 |
|------|----------|
| Windows x86 | fnpack-1.2.1-windows-amd64 |
| Linux x86 | fnpack-1.2.1-linux-amd64 |
| Linux ARM | fnpack-1.2.1-linux-arm64 |
| Mac Intel | fnpack-1.2.1-darwin-amd64 |
| Mac M系列 | fnpack-1.2.1-darwin-arm64 |

**创建项目**：
```bash
# 创建独立项目
fnpack create myapp

# 无 UI 纯服务项目
fnpack create myapp --without-ui true

# Docker 应用项目
fnpack create myapp --template docker

# 无 UI Docker 应用
fnpack create myapp --template docker --without-ui true
```

**打包应用**：
```bash
# 在应用目录中执行
fnpack build

# 指定打包目录
fnpack build --directory /path/to/app
```

**打包校验规则**：

| 路径 | 校验规则 |
|------|----------|
| `manifest` | 必须存在，且必选字段存在 |
| `config/privilege` | 必须存在，符合 JSON 格式 |
| `config/resource` | 必须存在，符合 JSON 格式 |
| `ICON.PNG` | 必须存在 |
| `ICON_256.PNG` | 必须存在 |
| `app/` | 必须存在 |
| `cmd/` | 必须存在 |
| `wizard/` | 必须存在 |
| `app/{desktop_uidir}/` | 若定义则必须存在 |

### 13.2 appcenter-cli

appcenter-cli 是 fnOS 系统预装的应用中心管理工具。

**安装应用**：
```bash
# 通过 fpk 文件安装
appcenter-cli install-fpk myapp.fpk

# 静默安装（使用环境变量文件）
appcenter-cli install-fpk myapp.fpk --env config.env

# 从本地目录安装（开发测试）
appcenter-cli install-local
```

**环境变量文件格式**：
```env
# config.env
wizard_admin_username=admin
wizard_admin_password=mypassword123
wizard_database_type=sqlite
wizard_app_port=8080
wizard_agree_terms=true
```

**系统管理**：
```bash
# 查看默认存储空间
appcenter-cli default-volume

# 设置默认安装位置
appcenter-cli default-volume 1

# 手动安装功能
appcenter-cli manual-install          # 查看状态
appcenter-cli manual-install enable   # 开启
appcenter-cli manual-install disable  # 关闭
```

**应用管理**：
```bash
# 查看已安装应用
appcenter-cli list

# 启动/停止应用
appcenter-cli start myapp
appcenter-cli stop myapp
```

---

## 十四、图标规范

| 项目 | 要求 |
|------|------|
| 尺寸 | 64×64、256×256 像素 |
| 格式 | PNG、JPG |
| 颜色 | sRGB |
| 大小 | ≤ 1024 KB |
| 形状 | 正方形直角 |

**文件命名**：
- `ICON.PNG` - 64×64
- `ICON_256.PNG` - 256×256

---

## 十五、Docker 应用

### 15.1 创建项目

```bash
fnpack create myapp --template docker
```

### 15.2 项目结构

```
myapp/
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml    # Docker Compose 编排文件
│   └── ui/
│       ├── images/
│       └── config
├── manifest
├── cmd/
│   ├── main
│   ├── install_init
│   ├── install_callback
│   └── ...
├── config/
│   ├── privilege
│   └── resource
├── wizard/
├── ICON.PNG
└── ICON_256.PNG
```

### 15.3 docker-compose.yaml

系统根据此文件创建和启动容器编排，支持环境变量替换：

```yaml
version: '3.8'
services:
  web:
    image: nginx:latest
    container_name: myapp_web
    ports:
      - "${TRIM_SERVICE_PORT}:80"
    volumes:
      - ${TRIM_PKGVAR}/data:/data
```

**注意**：docker-compose.yaml 中可使用环境变量，执行前会自动替换。

### 15.4 main 脚本

Docker 应用的启停由应用中心管理，main 脚本只需检查状态：

```bash
#!/bin/bash
FILE_PATH="${TRIM_APPDEST}/docker/docker-compose.yaml"

is_docker_running() {
    DOCKER_NAME=""
    if [ -f "$FILE_PATH" ]; then
        DOCKER_NAME=$(cat $FILE_PATH | grep "container_name" | awk -F ':' '{print $2}' | xargs)
    fi
    if [ -n "$DOCKER_NAME" ]; then
        docker inspect $DOCKER_NAME | grep -q "\"Status\": \"running\"," || exit 1
        return
    fi
}

case $1 in
start)
    # Docker 应用由应用中心管理，无需处理
    exit 0
    ;;
stop)
    # Docker 应用由应用中心管理，无需处理
    exit 0
    ;;
status)
    # 默认选择第一个容器状态作为应用状态
    if is_docker_running; then
        exit 0
    else
        exit 3
    fi
    ;;
*)
    exit 1
    ;;
esac
```

### 15.5 开发流程

1. **编辑 manifest** - 定义应用基本信息
2. **编辑 docker-compose.yaml** - 定义容器编排
3. **检查启停状态** - 修改 main 脚本中的状态检查逻辑（如需要）
4. **定义用户入口** - 配置 app/ui/config
5. **打包测试** - `fnpack build` 后使用 `appcenter-cli install-local` 测试

---

## 十六、Native 应用

### 16.1 CGI 入口配置

```json
{
    ".url": {
        "myapp.Application": {
            "title": "我的应用",
            "icon": "images/icon-{0}.png",
            "type": "iframe",
            "url": "/cgi/ThirdParty/myapp/index.cgi/"
        }
    }
}
```

**CGI 服务映射路径**：`/cgi/ThirdParty/[appname]/**.cgi`

### 16.2 CGI 脚本模板

在 `app/ui/` 目录下创建 `index.cgi`：

```bash
#!/bin/bash
# 静态文件根目录
BASE_PATH="${TRIM_APPDEST}/www"

# 从 REQUEST_URI 获取路径
URI_NO_QUERY="${REQUEST_URI%%\?*}"
REL_PATH="/"

case "$URI_NO_QUERY" in
    *index.cgi*)
        REL_PATH="${URI_NO_QUERY#*index.cgi}"
        ;;
esac

if [ -z "$REL_PATH" ] || [ "$REL_PATH" = "/" ]; then
    REL_PATH="/index.html"
fi

TARGET_FILE="${BASE_PATH}${REL_PATH}"

# 禁止 .. 越级访问
if echo "$TARGET_FILE" | grep -q '\.\.'; then
    echo "Status: 400 Bad Request"
    echo "Content-Type: text/plain; charset=utf-8"
    echo ""
    echo "Bad Request"
    exit 0
fi

# 判断文件是否存在
if [ ! -f "$TARGET_FILE" ]; then
    echo "Status: 404 Not Found"
    echo "Content-Type: text/plain; charset=utf-8"
    echo ""
    echo "404 Not Found: ${REL_PATH}"
    exit 0
fi

# 根据 MIME 类型返回
ext="${TARGET_FILE##*.}"
case "$ext" in
    html|htm) mime="text/html; charset=utf-8" ;;
    css) mime="text/css; charset=utf-8" ;;
    js) mime="application/javascript; charset=utf-8" ;;
    png) mime="image/png" ;;
    jpg|jpeg) mime="image/jpeg" ;;
    gif) mime="image/gif" ;;
    svg) mime="image/svg+xml" ;;
    json) mime="application/json; charset=utf-8" ;;
    *) mime="application/octet-stream" ;;
esac

echo "Content-Type: $mime"
echo ""
cat "$TARGET_FILE"
```

### 16.3 项目结构

```
myapp/
├── app/
│   ├── ui/
│   │   ├── index.cgi           # CGI 脚本
│   │   ├── images/
│   │   └── config
│   └── www/                    # 静态文件目录
│       ├── index.html
│       ├── css/
│       └── js/
├── manifest
├── cmd/
└── ...
```

### 16.4 开发流程

1. **制作 Web 页面** - HTML/CSS/JS
2. **创建应用项目** - `fnpack create myapp`
3. **迁移 Web 文件** - 复制到 `app/www/`
4. **配置应用入口** - 编辑 `app/ui/config`
5. **创建 CGI 脚本** - 放置在 `app/ui/index.cgi`
6. **编写生命周期脚本** - `cmd/main` 等
7. **打包测试** - `fnpack build`

---

## 附录A：代码模板

### A.1 main 脚本模板

```bash
#!/bin/bash
APP_NAME="myapp"
BIN_DIR="${TRIM_APPDEST}/bin"
DATA_DIR="${TRIM_PKGVAR}"
PID_FILE="${TRIM_PKGTMP}/${APP_NAME}.pid"
LOG_FILE="${TRIM_PKGVAR}/${APP_NAME}.log"
PORT="${wizard_port:-${TRIM_SERVICE_PORT:-8080}}"

start_app() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "$APP_NAME already running"
        return 0
    fi
    
    mkdir -p "$(dirname "$PID_FILE")" "$DATA_DIR"
    
    # 启动应用
    "$BIN_DIR/myapp" --port "$PORT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    ps -p $(cat "$PID_FILE") > /dev/null 2>&1
}

stop_app() {
    [ -f "$PID_FILE" ] || return 0
    PID=$(cat "$PID_FILE")
    
    kill "$PID" 2>/dev/null || true
    for i in {1..10}; do
        ps -p "$PID" > /dev/null 2>&1 || break
        sleep 1
    done
    
    ps -p "$PID" > /dev/null 2>&1 && kill -9 "$PID"
    rm -f "$PID_FILE"
}

check_status() {
    [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1
}

case "$1" in
start)
    start_app && exit 0 || exit 1
    ;;
stop)
    stop_app && exit 0 || exit 1
    ;;
status)
    check_status && exit 0 || exit 3
    ;;
*)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
```

### A.2 install_callback 模板

```bash
#!/bin/bash
set -e

# 设置权限
chmod +x "${TRIM_APPDEST}/bin/"*

# 创建配置
mkdir -p "${TRIM_PKGVAR}/config"
cat > "${TRIM_PKGVAR}/config/app.conf" << EOF
port=${wizard_port:-8080}
mode=${wizard_mode:-standard}
EOF

echo "Installation complete"
exit 0
```

### A.3 config_callback 模板

```bash
#!/bin/bash
set -e

MAIN_SCRIPT="/var/apps/${TRIM_APPNAME}/cmd/main"
CONFIG_FILE="${TRIM_PKGVAR}/config/app.conf"
PID_FILE="${TRIM_PKGTMP}/${TRIM_APPNAME}.pid"

# 检查运行状态
WAS_RUNNING=false
if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    WAS_RUNNING=true
    "$MAIN_SCRIPT" stop
fi

# 更新配置
sed -i "s/^port=.*/port=${wizard_port}/" "$CONFIG_FILE"

# 重启（如果之前在运行）
[ "$WAS_RUNNING" = true ] && "$MAIN_SCRIPT" start

exit 0
```

### A.4 upgrade_init 模板

```bash
#!/bin/bash
set -e

MAIN_SCRIPT="/var/apps/${TRIM_APPNAME}/cmd/main"
BACKUP_DIR="/vol1/@appshare/${TRIM_APPNAME}/.backup"

# 停止服务
"$MAIN_SCRIPT" stop || true

# 备份数据（如果用户选择保留）
if [ "${wizard_data_action:-keep}" = "keep" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -a "${TRIM_PKGVAR}"/* "$BACKUP_DIR/"
fi

exit 0
```

### A.5 upgrade_callback 模板

```bash
#!/bin/bash
set -e

MAIN_SCRIPT="/var/apps/${TRIM_APPNAME}/cmd/main"
BACKUP_DIR="/vol1/@appshare/${TRIM_APPNAME}/.backup"

# 设置权限
chmod +x "${TRIM_APPDEST}/bin/"*

# 恢复数据
if [ -d "$BACKUP_DIR" ]; then
    cp -a "$BACKUP_DIR"/* "${TRIM_PKGVAR}/"
    rm -rf "$BACKUP_DIR"
fi

# 启动服务
"$MAIN_SCRIPT" start

exit 0
```

---

## 附录B：检查清单

### B.1 必需文件

- [ ] `manifest` - 应用清单
- [ ] `ICON.PNG` - 64×64 图标
- [ ] `ICON_256.PNG` - 256×256 图标
- [ ] `config/privilege` - 权限配置
- [ ] `config/resource` - 资源配置
- [ ] `cmd/main` - 主脚本
- [ ] `wizard/` - 向导目录

### B.2 manifest 必需字段

- [ ] `appname`
- [ ] `version`
- [ ] `display_name`
- [ ] `desc`
- [ ] `source`

### B.3 脚本检查

- [ ] 使用环境变量，无硬编码路径
- [ ] 错误写入 `$TRIM_TEMP_LOGFILE`
- [ ] 正确的 exit 状态码
- [ ] 有执行权限

### B.4 打包前检查

```bash
# 检查文件结构
ls -la manifest ICON.PNG ICON_256.PNG config/ cmd/ wizard/ app/

# 检查 JSON 格式
jq . config/privilege
jq . config/resource

# 检查脚本语法
bash -n cmd/main
```

---

## 附录C：参考项目文件索引

本目录 qBittorrent 项目可作为开发参考：

| 文件 | 说明 |
|------|------|
| `manifest` | 应用清单示例 |
| `config/privilege` | 权限配置示例 |
| `config/resource` | 资源配置示例 |
| `cmd/main` | 生命周期管理脚本示例 |
| `cmd/install_init` | 安装前脚本示例 |
| `cmd/install_callback` | 安装后脚本示例 |
| `cmd/config_init` | 配置初始化脚本示例 |
| `cmd/config_callback` | 配置变更脚本示例 |
| `cmd/upgrade_init` | 升级前备份脚本示例 |
| `cmd/upgrade_callback` | 升级后恢复脚本示例 |
| `cmd/uninstall_init` | 卸载前脚本示例 |
| `cmd/uninstall_callback` | 卸载后脚本示例 |
| `wizard/install` | 安装向导示例 |
| `wizard/config` | 配置向导示例 |
| `wizard/upgrade` | 升级向导示例 |
| `wizard/uninstall` | 卸载向导示例 |
| `app/ui/config` | 应用入口配置示例 |

---

**官方文档**: https://developer.fnnas.com/
**文档版本**: 2.0
**最后更新**: 2025-02-14
