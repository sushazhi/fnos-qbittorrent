# FNNAS (飞牛 fnOS) 开发者指南

> 完整开发文档 - AI 友好格式  
> 文档来源: https://developer.fnnas.com  
> 生成时间: 2026-03-12

---

## 目录

1. [欢迎与概述](#1-欢迎与概述)
2. [快速开始](#2-快速开始)
3. [开发指南 - 基础](#3-开发指南---基础)
4. [开发指南 - 进阶](#4-开发指南---进阶)
5. [开发指南 - 实战](#5-开发指南---实战)
6. [开发指南 - 规范](#6-开发指南---规范)
7. [CLI 开发工具](#7-cli-开发工具)
8. [文档更新日志](#8-文档更新日志)

---

## 1. 欢迎与概述

### 1.1 飞牛 fnOS 简介

飞牛 fnOS 是一款年轻而强大的 NAS 操作系统。自2024年8月开放公测以来，截止2025年8月公测一周年之际，系统装机量已经超过 90万，APP设备数也已突破 120万。

**目标**: 把飞牛 fnOS 打造成 "存储系统界的 Windows"

### 1.2 为什么在飞牛 fnOS 上开发应用？

**1. 数据安全与隐私**
- 数据在本地自主管理，避免不必要的外部依赖
- 可控的访问与授权，满足个人与企业的隐私诉求

**2. 私有本地服务器，场景丰富**
- 家庭娱乐中心：支持在不同设备里播放 NAS 中的照片、视频与音乐
- 本地 AI 与算力：部署智能相册等本地应用，数据不外流
- 备份与同步枢纽：手机与电脑自动/定时备份，版本快照功能

**3. 企业级能力与扩展**
- 文件共享与协作：支持多人文件共享和权限精细化管理
- 数字化办公：NAS 作为数字化办公的存储容器
- 定制工作台：通过应用中心和Docker快速部署各种应用服务

### 1.3 系统要求

- **系统版本**: 飞牛 fnOS 0.9.27 及以上版本
- **系统架构**: 仅支持 x86_64 (AMD64)
- **Linux 内核版本**: 6.12.18
- **存储空间**: 至少创建一个存储空间

### 1.4 应用技术栈

- **服务开发语言**: Node.js、Python、Java、Go、Linux 运行时支持的其他语言
- **前端开发语言**: Html/Javascript/CSS 及现代浏览器引擎支持的其他语言和框架

---

## 2. 快速开始

### 2.1 准备工作

**硬件要求**
- 系统版本: 飞牛 fnOS 0.9.27 及以上版本
- 存储空间: 至少创建一个存储空间
- 管理员权限: 拥有设备管理权限

**CLI 工具**
- `fnpack`: 应用打包工具
- `appcenter-cli`: 应用中心命令行工具（已在飞牛 fnOS 环境中预装）

### 2.2 创建应用

**基本命令**
```bash
# 创建独立项目
fnpack create <appname>

# 不带应用访问入口，使用纯服务类型的项目
fnpack create <appname> --without-ui true

# 创建 Docker 应用项目
fnpack create <appname> --template docker

# 无应用访问入口Docker应用
fnpack create <appname> --template docker --without-ui true
```

**项目结构**
```
myapp/
├── app/                    # 应用可执行文件目录
│   ├── ui/                 # UI资源
│   │   └── images/
│   └── config
│   └── docker/             # Docker 配置（Docker 应用模板）
├── cmd/                    # 应用生命周期管理脚本
│   ├── main                # 启停脚本
│   ├── install_init        # 安装前
│   ├── install_callback    # 安装后
│   ├── uninstall_init      # 卸载前
│   ├── uninstall_callback  # 卸载后
│   ├── upgrade_init        # 升级前
│   ├── upgrade_callback    # 升级后
│   ├── config_init         # 配置前
│   └── config_callback     # 配置后
├── config/
│   ├── privilege           # 应用权限配置
│   └── resource            # 应用资源配置
├── wizard/
│   ├── install             # 安装向导配置
│   ├── uninstall           # 卸载向导配置
│   └── config              # 配置向导
├── manifest                # 应用基本信息
├── LICENSE                 # 许可证文件
├── ICON.PNG                # 应用图标（64x64）
└── ICON_256.PNG            # 应用图标（256x256）
```

### 2.3 打包应用

```bash
# 在应用目录中执行打包
cd myapp
fnpack build

# 指定打包的目录
fnpack build --directory <path>
```

### 2.4 测试应用

**方式一：使用 appcenter-cli**
```bash
appcenter-cli install-fpk App.Native.HelloFnosAppCenter.fpk
```

**方式二：手动安装**
```bash
# 开启手动安装功能
appcenter-cli manual-install enable

# 查看日志
# 日志位置: /var/apps/App.Native.HelloFnosAppCenter/var/info.log
```

### 2.5 上架应用

加入**应用中心开发者先锋交流群**，群内会有专员为您办理应用内测和应用上架。

---

## 3. 开发指南 - 基础

### 3.1 架构概述

#### 3.1.1 应用目录结构

应用安装到飞牛 fnOS 系统后的目录结构：

```
/var/apps/[appname]
├── cmd/
│   ├── install_callback
│   ├── install_init
│   ├── main
│   ├── uninstall_callback
│   ├── uninstall_init
│   ├── upgrade_init
│   ├── upgrade_callback
│   ├── config_init
│   └── config_callback
├── config/
│   ├── privilege
│   └── resource
├── ICON_256.PNG
├── ICON.PNG
├── LICENSE
├── manifest
├── etc->/vol[volume_number]/@appconf/[appname]
├── home->/vol[volume_number]/@apphome/[appname]
├── target->/vol[volume_number]/@appcenter/[appname]
├── tmp->/vol[volume_number]/@apptemp/[appname]
├── var->/vol[volume_number]/@appdata/[appname]
├── shares/
│   ├── datashare1->/vol[volume_number]/@appshare/datashare1
│   └── datashare2->/vol[volume_number]/@appshare/datashare2
└── wizard/
    ├── install
    ├── uninstall
    ├── upgrade
    └── config
```

#### 3.1.2 目录功能说明

| 目录 | 说明 |
|------|------|
| target | 应用可执行文件的存放位置 |
| etc | 静态配置文件存放位置 |
| var | 运行时动态数据存放位置 |
| tmp | 临时文件存放位置 |
| home | 用户数据文件存放位置 |
| meta | 应用元数据存放位置 |
| shares | 数据共享目录（根据 resource 配置自动创建） |
| cmd | 存放应用生命周期管理的脚本文件 |
| wizard | 存放用户交互向导的配置文件 |

#### 3.1.3 应用生命周期

飞牛 fnOS 系统通过调用 `cmd` 目录中的脚本来管理应用：

- **安装流程**: install_init → 文件解压 → install_callback
- **卸载流程**: 停止应用 → uninstall_init → uninstall_callback
- **更新流程**: upgrade_init → 文件解压 → upgrade_callback
- **配置流程**: config_init → config_callback

#### 3.1.4 应用运行状态管理

```bash
#!/bin/bash

case $1 in
    start)
        # 启动应用的命令，成功返回 0，失败返回 1
        exit 0
        ;;
    stop)
        # 停止应用的命令，成功返回 0，失败返回 1
        exit 0
        ;;
    status)
        # 检查应用运行状态，运行中返回 0，未运行返回 3
        exit 0
        ;;
    *)
        exit 1
        ;;
esac
```

**状态返回码**:
- `exit 0`: 应用正在运行
- `exit 3`: 应用未运行
- `exit 1`: 其他错误

#### 3.1.5 错误异常处理

在应用启动、安装、更新等过程中遇到错误时，可以向 TRIM_TEMP_LOGFILE 写入错误信息，然后退出脚本并返回错误码 1：

```bash
# 检查配置文件是否存在
if [ ! -f "$TRIM_PKGETC/config.conf" ]; then
    echo "配置文件不存在, 应用启动失败！" > "${TRIM_TEMP_LOGFILE}"
    exit 1
fi
```

---

### 3.2 Manifest

manifest 文件是应用的"身份证"，定义应用的基本信息和运行属性。

#### 3.2.1 基本信息

```properties
# 应用标识（必须）
appname=myapp                           # 应用唯一标识符
version=1.0.0                           # 版本号格式: x[.y[.z]][-build]
display_name=我的应用                   # 显示名称
desc=这是一个示例应用                   # 详细介绍，支持HTML格式

# 系统要求
platform=x86                            # 架构类型: x86/arm/loongarch/risc-v/all

# 开发者信息
maintainer=开发者名称
maintainer_url=https://example.com
source=thirdparty                       # 固定为 thirdparty
```

#### 3.2.2 安装和运行控制

```properties
# 系统兼容性
os_min_version=0.9.0                    # 支持的最低系统版本
os_max_version=0.9.100                  # 支持的最高系统版本

# 应用控制
ctl_stop=true                           # 是否显示启动/停止功能

# 安装位置
install_type=root                       # 安装到系统分区 /usr/local/apps/@appcenter/
                                        # 为空时，用户可选择存储位置
```

#### 3.2.3 依赖管理

```properties
# 依赖应用列表
# 格式: app1>2.2.2:app2:app3
install_dep_apps=redis:minio
```

#### 3.2.4 用户界面

```properties
# 桌面集成
desktop_uidir=ui                        # UI组件目录路径
desktop_applaunchname=myapp.main       # 应用中心启动入口
```

#### 3.2.5 端口管理

```properties
# 端口检查
service_port=8080                       # 应用监听的端口号
checkport=true                           # 是否启用端口检查
```

#### 3.2.6 权限控制

```properties
# 是否禁用授权目录功能
disable_authorization_path=false
```

#### 3.2.7 应用更新

```properties
# 更新日志
changelog=更新内容描述
```

---

### 3.3 环境变量

环境变量是应用运行时的"工具箱"，系统会自动提供这些环境变量。

#### 3.3.1 应用相关变量

**基本信息**
| 变量名 | 说明 |
|--------|------|
| TRIM_APPNAME | 应用名称（来自 manifest 中的 appname） |
| TRIM_APPVER | 应用版本号 |
| TRIM_OLD_APPVER | 升级前的版本号（仅在升级时可用） |

**路径信息**
| 变量名 | 说明 |
|--------|------|
| TRIM_APPDEST | 应用可执行文件目录路径（target 文件夹） |
| TRIM_PKGETC | 配置文件目录路径（etc 文件夹） |
| TRIM_PKGVAR | 动态数据目录路径（var 文件夹） |
| TRIM_PKGTMP | 临时文件目录路径（tmp 文件夹） |
| TRIM_PKGHOME | 用户数据目录路径（home 文件夹） |
| TRIM_PKGMETA | 元数据目录路径（meta 文件夹） |
| TRIM_APPDEST_VOL | 应用安装的存储空间路径 |

**网络和端口**
| 变量名 | 说明 |
|--------|------|
| TRIM_SERVICE_PORT | 应用监听的端口号 |

**用户和权限**
| 变量名 | 说明 |
|--------|------|
| TRIM_USERNAME | 应用专用用户名 |
| TRIM_GROUPNAME | 应用专用用户组名 |
| TRIM_UID | 应用用户 ID |
| TRIM_GID | 应用用户组 ID |
| TRIM_RUN_USERNAME | 当前执行脚本的用户名 |
| TRIM_RUN_GROUPNAME | 当前执行脚本的用户组名 |
| TRIM_RUN_UID | 当前执行脚本的用户 ID |
| TRIM_RUN_GID | 当前执行脚本的用户组 ID |

**数据共享**
| 变量名 | 说明 |
|--------|------|
| TRIM_DATA_SHARE_PATHS | 数据共享路径列表，多个路径用冒号分隔 |
| TRIM_DATA_ACCESSIBLE_PATHS | 可访问路径列表 |

**临时日志**
| 变量名 | 说明 |
|--------|------|
| TRIM_TEMP_LOGFILE | 系统日志文件路径（用户可见的日志） |
| TRIM_TEMP_UPGRADE_FOLDER | 升级过程的临时目录 |
| TRIM_PKGINST_TEMP_DIR | 安装包解压的临时目录 |
| TRIM_TEMP_TPKFILE | fpk 包解压目录 |

**CMD 脚本**
| 变量名 | 说明 |
|--------|------|
| TRIM_APP_STATUS | 当前状态 (INSTALL/START/UPGRADE/UNINSTALL/STOP/CONFIG) |

#### 3.3.2 系统相关变量

| 变量名 | 说明 |
|--------|------|
| TRIM_SYS_VERSION | 完整的系统版本号 |
| TRIM_SYS_VERSION_MAJOR | 系统主版本号 |
| TRIM_SYS_VERSION_MINOR | 系统次版本号 |
| TRIM_SYS_VERSION_BUILD | 系统构建号 |
| TRIM_SYS_ARCH | 系统 CPU 架构（如 x86_64） |
| TRIM_KERNEL_VERSION | 系统内核版本号 |
| TRIM_SYS_MACHINE_ID | 设备的唯一标识符 |
| TRIM_SYS_LANGUAGE | 系统语言设置 |

#### 3.3.3 向导相关变量

当用户通过安装向导、配置向导等进行操作时，他们的选择会变成环境变量。这些变量没有 TRIM_ 前缀，完全由向导配置决定。

---

### 3.4 应用权限

权限定义应用在系统中的运行身份。

#### 3.4.1 默认权限模式（应用用户运行）

```json
{
  "defaults": {
    "run-as": "package"
  },
  "username": "myapp_user",
  "groupname": "myapp_group"
}
```

- 系统为应用创建专用用户和用户组
- 应用只能访问自己的目录和系统允许的公共资源

#### 3.4.2 Root 权限模式

> ⚠️ 仅适用于飞牛官方合作的企业开发者

```json
{
  "defaults": {
    "run-as": "root"
  },
  "username": "myapp_user",
  "groupname": "myapp_group"
}
```

#### 3.4.3 外部文件访问权限

- 应用默认无法访问用户的个人文件
- 用户需要在应用设置中明确授权
- 授权方式：读写、只读、禁止访问

---

### 3.5 应用资源

声明应用的扩展能力。

#### 3.5.1 数据共享 (data-share)

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

- `rw`: 读写权限
- `ro`: 只读权限

#### 3.5.2 系统集成 (usr-local-linker)

```json
{
  "usr-local-linker": {
    "bin": ["bin/myapp-cli"],
    "lib": ["lib/mylib.so"],
    "etc": ["etc/myapp.conf"]
  }
}
```

- `bin` → 链接到 `/usr/local/bin/`
- `lib` → 链接到 `/usr/local/lib/`
- `etc` → 链接到 `/usr/local/etc/`

#### 3.5.3 Docker 项目支持 (docker-project)

在 `app/docker/docker-compose.yaml` 定义容器编排。

---

### 3.6 应用入口

用户通过入口访问应用。

#### 3.6.1 入口类型

1. **桌面图标入口**: 点击图标直接访问应用
2. **文件右键入口**: 右键文件时使用应用打开

#### 3.6.2 入口配置文件

配置文件路径: `app/ui/config` (假设 desktop_uidir 为 ui)

```json
{
  ".url": {
    "myapp.main": {
      "title": "我的应用",
      "icon": "images/icon-{0}.png",
      "type": "url",
      "protocol": "http",
      "port": "8080",
      "url": "/",
      "allUsers": true
    },
    "myapp.admin": {
      "title": "管理后台",
      "icon": "images/admin-icon-{0}.png",
      "type": "url",
      "protocol": "http",
      "port": "8080",
      "url": "/admin",
      "allUsers": false
    }
  }
}
```

**参数说明**
| 参数 | 说明 |
|------|------|
| title | 入口显示标题 |
| icon | 图标路径（{0} 会自动替换为 64 或 256） |
| type | url 或 iframe |
| protocol | http/https（为空时自适应） |
| port | 端口号 |
| url | 访问路径 |
| allUsers | 是否所有用户可见 |

**文件右键入口额外参数**
| 参数 | 说明 |
|------|------|
| fileTypes | 关联文件类型，如 ["txt", "md", "json"] |
| noDisplay | 是否在桌面隐藏 |

---

### 3.7 用户向导

帮助用户完成安装、配置、卸载等操作。

#### 3.7.1 向导类型

- `wizard/install`: 安装向导
- `wizard/uninstall`: 卸载向导
- `wizard/upgrade`: 更新向导
- `wizard/config`: 配置向导

#### 3.7.2 表单项类型

**文本输入框 (text)**
```json
{
  "type": "text",
  "field": "wizard_username",
  "label": "用户名",
  "initValue": "admin",
  "rules": [
    {"required": true, "message": "请输入用户名"},
    {"min": 3, "max": 20, "message": "用户名长度应在3-20个字符之间"}
  ]
}
```

**密码输入框 (password)**
```json
{
  "type": "password",
  "field": "wizard_password",
  "label": "管理员密码",
  "rules": [
    {"required": true, "message": "请输入密码"},
    {"min": 6, "message": "密码长度不能少于6位"}
  ]
}
```

**单选按钮 (radio)**
```json
{
  "type": "radio",
  "field": "wizard_install_type",
  "label": "安装类型",
  "initValue": "standard",
  "options": [
    {"label": "标准安装", "value": "standard"},
    {"label": "自定义安装", "value": "custom"}
  ]
}
```

**多选框 (checkbox)**
```json
{
  "type": "checkbox",
  "field": "wizard_modules",
  "label": "安装模块",
  "initValue": ["web", "api"],
  "options": [
    {"label": "Web界面", "value": "web"},
    {"label": "API接口", "value": "api"}
  ]
}
```

**下拉选择 (select)**
```json
{
  "type": "select",
  "field": "wizard_database",
  "label": "数据库类型",
  "initValue": "sqlite",
  "options": [
    {"label": "SQLite", "value": "sqlite"},
    {"label": "MySQL", "value": "mysql"}
  ]
}
```

---

## 4. 开发指南 - 进阶

### 4.1 应用依赖关系

#### 4.1.1 声明依赖

```properties
install_dep_apps=dep2:dep1
```

- 依赖顺序从后往前执行
- 支持指定最低版本: `app1>2.2.2:app2`

#### 4.1.2 依赖检查逻辑

- **安装和启用**: 检查依赖应用是否已安装和已启用，未安装则自动安装
- **停用和卸载**: 检查是否有其他应用依赖当前应用
- **更新流程**: 检查是否有其他应用依赖当前应用

#### 4.1.3 嵌套依赖

应用中心仅对一层依赖进行检查。如有嵌套依赖，需平铺声明：

```properties
# 错误
install_dep_apps=depA:depB   # depB 依赖 depC，但未声明

# 正确
install_dep_apps=depA:depB:depC
```

---

### 4.2 运行时环境

#### 4.2.1 Python 环境

```properties
# manifest 声明
install_dep_apps=python312
```

```bash
# 可选版本：python312、python311、python310、python39、python38
export PATH=/var/apps/python312/target/bin:$PATH

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 4.2.2 Node.js 环境

```properties
# manifest 声明
install_dep_apps=nodejs_v22
```

```bash
# 可选版本：nodejs_v22、nodejs_v20、nodejs_v18、nodejs_v16、nodejs_v14
export PATH=/var/apps/nodejs_v22/target/bin:$PATH
node -v
npm -v
```

#### 4.2.3 Java 环境

```properties
# manifest 声明
install_dep_apps=java-21-openjdk
```

```bash
# 可选版本：java-21-openjdk、java-17-openjdk、java-11-openjdk
export PATH=/var/apps/java-21-openjdk/target/bin:$PATH
java --version
```

---

### 4.3 中间件服务

#### 4.3.1 Redis

```properties
install_dep_apps=redis
```

**Python 使用示例**
```python
import redis

pool = redis.ConnectionPool(host='127.0.0.1', port=6379, db=1, decode_responses=True, max_connections=10)
client = redis.Redis(connection_pool=pool)

client.lpush('my_list', 'item1', 'item2')
items = client.lrange('my_list', 0, -1)
```

#### 4.3.2 MinIO

```properties
install_dep_apps=minio
```

**Python 使用示例**
```python
from minio import Minio

client = Minio(
    endpoint="127.0.0.1:9000",
    access_key="your_access_key",
    secret_key="your_secret_key",
    secure=False
)

bucket_name = "my-bucket"
if not client.bucket_exists(bucket_name):
    client.make_bucket(bucket_name)
```

#### 4.3.3 RabbitMQ

```properties
install_dep_apps=rabbitmq
```

**Python 使用示例**
```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1', port=5672))
channel = connection.channel()
channel.queue_declare(queue='hello')
channel.basic_publish(exchange='', routing_key='hello', body='Hello World!')
connection.close()
```

#### 4.3.4 MySQL

```properties
install_dep_apps=mysql
```

**Python 使用示例**
```python
import pymysql

connection = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='root',
    password='password',
    database='test'
)
```

---

## 5. 开发指南 - 实战

### 5.1 Docker 应用构建

#### 5.1.1 创建应用

```bash
fnpack create my-app --template docker
```

#### 5.1.2 项目结构

```
my-app/
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml
│   ├── ui/
│   │   ├── images/
│   │   └── config
├── manifest
├── cmd/
│   ├── main
│   ├── install_init
│   ├── install_callback
│   ├── uninstall_init
│   ├── uninstall_callback
│   ├── upgrade_init
│   ├── upgrade_callback
│   ├── config_init
│   └── config_callback
├── config/
│   ├── privilege
│   └── resource
├── wizard/
├── LICENSE
├── ICON.PNG
└── ICON_256.PNG
```

#### 5.1.3 关键配置

**manifest 文件**
```properties
appname=my-app
version=1.0.0
display_name=我的应用
desc=描述
install_dep_apps=redis:minio
```

**docker-compose.yaml**
```yaml
version: '3.8'

services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ${TRIM_APPDEST}/ui:/usr/share/nginx/html
    restart: unless-stopped
```

#### 5.1.4 应用启停状态

默认使用第一个容器的状态作为应用的启停状态：

```bash
#!/bin/bash

FILE_PATH="${TRIM_APPDEST}/docker/docker-compose.yaml"

case $1 in
    start)
        # Docker 应用由应用中心管理，无需自定义
        exit 0
        ;;
    stop)
        # Docker 应用由应用中心管理，无需自定义
        exit 0
        ;;
    status)
        # 检查第一个容器状态
        CONTAINER_STATUS=$(docker-compose -f $FILE_PATH ps --services | head -1 | xargs docker-compose -f $FILE_PATH ps -q | head -1 | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null)
        if [ "$CONTAINER_STATUS" = "running" ]; then
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

---

### 5.2 Native 应用构建

#### 5.2.1 创建应用

```bash
fnpack create fnnas.notepad
```

#### 5.2.2 目录结构

```
notepad/
├── backend/          # NodeJS 后端
│   ├── server.js
│   └── package.json
├── frontend/         # React + Vite 前端
│   ├── src/
│   ├── index.html
│   └── vite.config.mjs
├── dist/             # 编译产物
├── fnnas.notepad/    # fnOS 应用包
│   ├── app/
│   │   └── server/   # 复制编译产物到此处
│   ├── manifest
│   ├── cmd/
│   ├── config/
│   └── wizard/
└── package.json
```

#### 5.2.3 manifest 配置

```properties
appname=fnnas.notepad
version=0.0.1
desc=A simple notepad
platform=x86
display_name=Notepad
source=thirdparty
maintainer=Your Name
service_port=8080
```

#### 5.2.4 cmd/main 启停脚本

```bash
#!/bin/bash

APP_NAME="fnnas.notepad"
APP_DIR="${TRIM_APPDEST}"
PORT=8080

start() {
    cd $APP_DIR/server
    nohup node server.js > $TRIM_PKGVAR/app.log 2>&1 &
    echo $! > $TRIM_PKGVAR/app.pid
}

stop() {
    if [ -f $TRIM_PKGVAR/app.pid ]; then
        kill $(cat $TRIM_PKGVAR/app.pid)
        rm $TRIM_PKGVAR/app.pid
    fi
}

status() {
    if [ -f $TRIM_PKGVAR/app.pid ]; then
        pid=$(cat $TRIM_PKGVAR/app.pid)
        if ps -p $pid > /dev/null 2>&1; then
            echo "running"
            return
        fi
    fi
    echo "stopped"
}

case "$1" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    *) echo "Usage: $0 {start|stop|status}" ;;
esac
```

---

## 6. 开发指南 - 规范

### 6.1 图标 Icon

**尺寸规格**
- 256 × 256 像素
- 64 × 64 像素

**文件格式**: PNG、JPG

**颜色空间**: sRGB

**文件大小**: ≤ 1024 KB

**形状规范**: 完整正方形直角图标

---

## 7. CLI 开发工具

### 7.1 fnpack

fnpack 是飞牛 fnOS 应用打包工具。

#### 7.1.1 工具下载

| 平台 | 文件名 |
|------|--------|
| Windows x86 | fnpack-1.2.1-windows-amd64 |
| Linux x86 | fnpack-1.2.1-linux-amd64 |
| Linux ARM | fnpack-1.2.1-linux-arm64 |
| Mac Intel | fnpack-1.2.1-darwin-amd64 |
| Mac M系列 | fnpack-1.2.1-darwin-arm64 |

#### 7.1.2 命令

```bash
# 创建应用项目
fnpack create <appname>
fnpack create <appname> --without-ui true
fnpack create <appname> --template docker

# 打包应用
fnpack build
fnpack build --directory <path>
```

#### 7.1.3 打包校验规则

| 路径 | 类型 | 校验规则 |
|------|------|----------|
| manifest | 文件 | 必须存在，且必选字段存在 |
| config/privilege | 文件 | 必须存在，且符合 JSON 格式 |
| config/resource | 文件 | 必须存在，且符合 JSON 格式 |
| ICON.PNG | 文件 | 必须存在 |
| ICON_256.PNG | 文件 | 必须存在 |
| app/ | 目录 | 必须存在 |
| cmd/ | 目录 | 必须存在 |
| wizard/ | 目录 | 必须存在 |
| app/{desktop_uidir}/ | 目录 | 若有定义，则目录必须存在 |

---

### 7.2 appcenter-cli

应用中心命令行管理工具（已在飞牛 fnOS 中预装）。

#### 7.2.1 安装应用

```bash
# 通过 fpk 文件安装
appcenter-cli install-fpk myapp.fpk

# 指定环境变量文件静默安装
appcenter-cli install-fpk myapp.fpk --env config.env

# 从本地目录安装（开发测试用）
cd /path/to/myapp
appcenter-cli install-local
```

#### 7.2.2 环境变量文件格式

```properties
# config.env
wizard_admin_username=admin
wizard_admin_password=mypassword123
wizard_database_type=sqlite
wizard_app_port=8080
wizard_agree_terms=true
```

#### 7.2.3 存储空间管理

```bash
# 查看当前默认存储空间
appcenter-cli default-volume

# 设置默认安装位置
appcenter-cli default-volume 1
appcenter-cli default-volume 2
```

#### 7.2.4 系统管理

```bash
# 手动安装功能
appcenter-cli manual-install         # 查看状态
appcenter-cli manual-install enable  # 开启
appcenter-cli manual-install disable # 关闭
```

#### 7.2.5 应用管理

```bash
# 查看已安装的应用列表
appcenter-cli list

# 启动应用
appcenter-cli start myapp

# 停止应用
appcenter-cli stop myapp
```

---

## 8. 文档更新日志

### 2025-12-31 更新

- 文档加入 New! 及 Update! 等徽标样式
- 重新调整文档结构
- 环境变量新增获取授权目录列表
- 应用入口新增配置文件支持环境变量特性
- Manifest 废除 arch 字段，改用 platform 字段
- fnpack 更新到 1.2.0 版本，新增 Linux ARM 版本

### 2025-12-16 更新

- 修复暗色主题模式下首页及 Footer 显示不友好的问题
- 优化首页一级分类命名
- manifest 新增应用更新分类，增加 changelog 属性
- fnpack 优化，补全注释，工具更新到 V1.0.4 版本
- 页面右上角全局添加搜索插件
- 创建应用文档改为前端基础开发语言教程
- Docker 应用文档注释补全，内容优化

---

*文档结束*
