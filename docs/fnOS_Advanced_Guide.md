# fnOS 应用开发进阶指南

> 本文档是 fnOS_Developer_Guide.md 的补充,包含进阶开发内容

## 目录

1. [应用依赖关系](#应用依赖关系)
2. [运行时环境](#运行时环境)
3. [中间件服务](#中间件服务)
4. [Docker 应用构建](#docker-应用构建)
5. [Native 应用构建](#native-应用构建)

---

## 应用依赖关系

在飞牛 fnOS 应用生态中，应用之间可能存在依赖关系。理解和管理这些依赖关系对于应用的正确运行至关重要。

### 声明依赖关系

应用依赖是指一个应用需要其他应用先安装并运行才能正常工作。在 `manifest` 文件中，通过 `install_dep_apps` 字段来声明应用依赖。

**manifest 示例:**

```yaml
version=1.0.0
install_dep_apps=dep2:dep1
```

### 依赖管理

#### 依赖检查逻辑

应用中心在应用安装、启用、停用、卸载、更新等流程中，会自动检查依赖关系：

1. **安装和启用流程**：检查依赖应用是否已安装和已启用，如果未安装则自动安装，如果未启用则自动启用
2. **停用和卸载流程**：检查是否有其他应用依赖当前应用，如果有则提示自动停用
3. **更新流程**：检查是否有其他应用依赖当前应用，如果有则提示更新期间自动停用

#### 依赖顺序

当存在多个依赖时，执行自动安装和自动启用的顺序是从后往前一个一个执行。

```yaml
# 正确的依赖顺序，安装时将先安装dep1，后安装dep2
install_dep_apps=dep2:dep1

# 错误的依赖顺序，如果dep2依赖于dep1，可能导致问题
install_dep_apps=dep1:dep2
```

#### 嵌套依赖处理

应用中心仅对一层依赖进行检查，不做递归检查。如果 **应用A** 依赖 **应用B**，但不直接依赖于 **应用C**，同时 **应用B** 又依赖 **应用C**，则需要在 **应用A** 中同时声明依赖 **应用B** 和 **应用C**：

```yaml
# 嵌套依赖的平铺定义
install_dep_apps=depB:depC
```

---

## 运行时环境

### Python 环境

通过 `manifest` 声明应用依赖指定版本的 Python 应用，应用中心将确保您的应用安装和启动时指定的 Python 环境已安装。

**manifest 配置:**

```yaml
install_dep_apps=python312
```

**使用示例:**

```bash
# 可选版本：python312、python311、python310、python39、python38
export PATH=/var/apps/python312/target/bin:$PATH

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装 python 相关依赖到 .venv
pip install -r requirements.txt
```

### Node.js 环境

通过 `manifest` 声明应用依赖指定版本的 Node.js 应用，应用中心将确保您的应用安装和启动时指定的 Node.js 环境已安装。

**manifest 配置:**

```yaml
install_dep_apps=nodejs_v22
```

**使用示例:**

```bash
# 可选版本：nodejs_v22、nodejs_v20、nodejs_v18、nodejs_v16、nodejs_v14
export PATH=/var/apps/nodejs_v22/target/bin:$PATH

# 确认node的版本
node -v

# 确认npm的版本
npm -v
```

### Java 环境

通过 `manifest` 声明应用依赖指定版本的 Java 应用，应用中心将确保您的应用安装和启动时指定的 Java 环境已安装。

**manifest 配置:**

```yaml
install_dep_apps=java-21-openjdk
```

**使用示例:**

```bash
# 可选版本：java-21-openjdk、java-17-openjdk、java-11-openjdk
export PATH=/var/apps/java-21-openjdk/target/bin:$PATH

# 确认java的版本
java --version
```

---

## 中间件服务

### Redis

如果你的应用需要依赖 redis，请在 `manifest` 的 `install_dep_apps` 字段中添加 redis，应用中心将确保您的应用安装和启动时 redis 服务已在运行。

**manifest 配置:**

```yaml
install_dep_apps=redis
```

**Python 使用示例:**

```python
import redis

def main():
    # 创建连接池，指定逻辑数据库（如 db=1），防止冲突
    # 默认配置下的 redis 可通过 host 127.0.0.1 和 port 6739 连接
    pool = redis.ConnectionPool(host='127.0.0.1', port=6379, db=1, decode_responses=True, max_connections=10)
    
    # 从连接池获取连接
    client = redis.Redis(connection_pool=pool)
    
    # 使用连接
    client.lpush('my_list', 'item1', 'item2')
    items = client.lrange('my_list', 0, -1)
    print(items)  # 输出: ['item2', 'item1']

if __name__ == "__main__":
    main()
```

### MinIO

MinIO 是一个高性能、云原生的开源对象存储系统，完全兼容 Amazon S3 API，且支持私有化部署。

**manifest 配置:**

```yaml
install_dep_apps=minio
```

**Python 使用示例:**

```python
from minio import Minio
from minio.error import S3Error

# 初始化客户端
# 默认配置下的 MinIO 可通过 host 127.0.0.1 和 port 9000 连接
client = Minio(
    endpoint="127.0.0.1:9000",
    access_key="your_access_key",   # 替换为你的 MinIO 管理员用户名 或 Access Key 
    secret_key="your_secret_key",   # 替换为你的 MinIO 管理员密码 或 Secret Key 
    secure=False                    # 本地测试通常为 False
)

# 定义桶名
bucket_name = "my-bucket"

# 创建 Bucket 示例
def main():
    try:
        # 检查桶是否存在，如果不存在则创建它
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' 已创建.")
        else:
            print(f"Bucket '{bucket_name}' 已存在.")
    except S3Error as err:
        print("创建 Bucket 时发生错误:", err)

if __name__ == "__main__":
    main()
```

### RabbitMQ

如果你的应用需要依赖 RabbitMQ，请在 `manifest` 的 `install_dep_apps` 字段中添加 rabbitmq。

**manifest 配置:**

```yaml
install_dep_apps=rabbitmq
```

**Python 使用示例:**

```python
import pika

HOST = "127.0.0.1"
PORT = 5672
VHOST = "/"
USERNAME = "guest"
PASSWORD = "guest"

# 创建连接
credentials = pika.PlainCredentials(USERNAME, PASSWORD)
connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=HOST,
    port=PORT,
    virtual_host=VHOST,
    credentials=credentials
))
channel = connection.channel()

# 声明队列
channel.queue_declare(queue='hello')

# 发送消息
channel.basic_publish(exchange='',
                      routing_key='hello',
                      body='Hello World!')
print(" [x] Sent 'Hello World!'")

# 关闭连接
connection.close()
```

### MySQL

如果你的应用需要依赖 MySQL，请在 `manifest` 的 `install_dep_apps` 字段中添加 mysql。

**manifest 配置:**

```yaml
install_dep_apps=mysql
```

**Python 使用示例:**

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

## Docker 应用构建

### 创建应用

使用 `fnpack create my-app -t docker` 命令创建应用目录，my-app 请自行替换为你的应用名。

**创建后的应用目录结构:**

```text
my-app/
├── app/                            # 应用可执行文件目录
│   ├── docker/                     # Docker 资源目录
│   │   └── docker-compose.yaml     # Docker Compose 编排文件
│   ├── ui/                         # 应用入口及视图
│   │   ├── images/                 # 应用图标及图片资源目录
│   │   └── config                  # 应用入口配置文件
├── manifest                        # 应用包基本信息描述文件
├── cmd/                            # 应用生命周期管理脚本
│   ├── main                        # 应用主脚本
│   ├── install_init                # 应用安装初始化脚本
│   ├── install_callback            # 应用安装回调脚本
│   ├── uninstall_init              # 应用卸载初始化脚本
│   ├── uninstall_callback          # 应用卸载回调脚本  
│   ├── upgrade_init                # 应用更新初始化脚本
│   ├── upgrade_callback            # 应用更新回调脚本
│   ├── config_init                 # 应用配置初始化脚本
│   └── config_callback             # 应用配置回调脚本
├── config/                         # 应用配置目录
│   ├── privilege                   # 应用权限配置
│   └── resource                    # 应用资源配置
├── wizard/                         # 应用向导目录
├── LICENSE                         # 应用许可证文件
├── ICON.PNG                        # 应用包 64*64 图标文件
└── ICON_256.PNG                    # 应用包 256*256 图标文件
```

### 1. 编辑 manifest 文件

定义必须字段：

- `appname` - 应用的唯一标识符
- `version` - 应用版本号
- `display_name` - 在应用中心显示的名称
- `desc` - 应用的详细介绍

其他字段可参考 manifest 指南，按需进行定义。

### 2. 编辑 docker-compose.yaml 文件

系统将根据 `docker-compose.yaml` 创建和启动容器编排。

`docker-compose.yaml` 允许使用环境变量，在执行前将进行替换，相关环境变量可参考环境变量指南。

### 3. 检查应用启停状态

默认情况下，无需定义启停逻辑，因为 Docker 应用的启停均由应用中心执行 compose 来管理。

然而，依然需要定义 Docker 应用是否在运行中，脚本中默认选择第一个容器的状态作为应用的启停状态。

**cmd/main 示例:**

```bash
#!/bin/bash

FILE_PATH="${TRIM_APPDEST}/docker/docker-compose.yaml"

is_docker_running () {
    DOCKER_NAME=""
    
    if [ -f "$FILE_PATH" ]; then
        DOCKER_NAME=$(cat $FILE_PATH | grep "container_name" | awk -F ':' '{print $2}' | xargs)
        echo "DOCKER_NAME is set to: $DOCKER_NAME"
    fi
    
    if [ -n "$DOCKER_NAME" ]; then
        docker inspect $DOCKER_NAME | grep -q "\"Status\": \"running\"," || exit 1
        return
    fi
}

case $1 in
start)
    # Docker 应用由应用中心自动启动
    exit 0
    ;;
stop)
    # Docker 应用由应用中心自动停止
    exit 0
    ;;
status)
    # 检查第一个容器状态
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

### 4. 定义用户入口

定义在飞牛 fnOS 上的桌面图标，详情可参考用户入口指南。

### 5. 执行打包和测试

在根目录，使用 `fnpack build` 命令进行打包，获得 `fpk` 文件，参考测试应用指南进行实机测试。

---

## Native 应用构建

### 一个简单的 Notepad 应用示例

我们使用 NodeJS + express 开发后端，React + vite 开发前端，实现了一个简易的 Notepad 程序。

**技术栈:**
- 后端: NodeJS + express
- 前端: React + vite

**代码目录结构:**

```text
notepad/
├── backend/
│   ├── server.js
│   └── package.json
├── frontend/
│   ├── public/
│   │   └── styles.css
│   ├── src/
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.mjs
├── scripts/
│   └── build-combined.js
├── package-lock.json
├── package.json
└── README.md
```

### 本地运行

```bash
npm install --workspaces
npm run start
```

访问 http://localhost:5001 来体验应用。

### 打包应用

```bash
npm run build
```

完成后，在 `dist/` 目录看到最终的可执行文件。

### 创建飞牛 fnOS 应用打包目录

在 `notepad/` 目录下执行 `fnpack create fnnas.notepad` 命令创建应用打包目录。

### 复制编译产物

在 `notepad/fnnas.notepad/app/` 目录下创建 `server/`，并复制 `notepad/dist/` 目录下的全部内容到 `server/` 目录下。

### 编辑应用基本信息

**manifest 示例:**

```yaml
appname=fnnas.notepad
version=0.0.1
desc=A simple notepad
platform=x86
display_name=Notepad
maintainer=someone
distributor=someone
desktop_uidir=ui
desktop_applaunchname=fnnas.notepad.Application
source=thirdparty
```

### 编辑应用权限

**config/privilege 示例:**

```json
{
    "defaults": {
        "run-as": "package"
    },
    "username": "fnnas.notepad",
    "groupname": "fnnas.notepad"
}
```

### 编辑应用配置

**config/resource 示例:**

```json
{
    "data-share": {
        "shares": [
            {
                "name": "fnnas.notepad",
                "permission": {
                    "rw": [
                        "fnnas.notepad"
                    ]
                }
            }
        ]
    }
}
```

### 编辑应用启停脚本

**cmd/main 示例:**

```bash
#!/bin/bash

LOG_FILE="${TRIM_PKGVAR}/info.log"
PID_FILE="${TRIM_PKGVAR}/app.pid"

export PATH=/var/apps/nodejs_v22/target/bin:$PATH
# data directory to write note.txt
DATA_DIR="${TRIM_DATA_SHARE_PATHS%%:*}"
# write the command to start your program here 
CMD="DATA_DIR=${DATA_DIR} PORT=5001 node ${TRIM_APPDEST}/server/server.js"

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> ${LOG_FILE}
}

start_process() {
    if status; then
        return 0
    fi
    
    log_msg "Starting process ..."
    bash -c "${CMD}" >> ${LOG_FILE} 2>&1 &
    printf "%s" "$!" > ${PID_FILE}
    return 0
}

stop_process() {
    log_msg "Stopping process ..."
    
    if [ -r "${PID_FILE}" ]; then
        pid=$(head -n 1 "${PID_FILE}" | tr -d '[:space:]')
        
        if ! check_process "${pid}"; then
            rm -f "${PID_FILE}"
            return
        fi
        
        kill -TERM ${pid} >> ${LOG_FILE} 2>&1
        
        local count=0
        while check_process "${pid}" && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        if check_process "${pid}"; then
            kill -KILL "${pid}"
            sleep 1
            rm -f "${PID_FILE}"
        fi
    fi
    
    return 0
}

check_process() {
    local pid=$1
    if kill -0 "${pid}" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

status() {
    if [ -f "${PID_FILE}" ]; then
        pid=$(head -n 1 "${PID_FILE}" | tr -d '[:space:]')
        if check_process "${pid}"; then
            return 0
        else
            rm -f "${PID_FILE}"
        fi    
    fi
    
    return 1
}

case $1 in
start)
    start_process
    ;;
stop)
    stop_process
    ;;
status)
    if status; then 
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

### 编辑桌面图标

**app/ui/config 示例:**

```json
{
    ".url": {
        "fnnas.notepad.Application": {
            "title": "Notepad",
            "icon": "images/icon_{0}.png",
            "type": "url",
            "protocol": "http",
            "port": "5001"
        }
    }
}
```

新增两个图标文件，分辨率分别是 64x64 和 256x256。

---

## 相关资源

- [fnOS 官方网站](https://www.fnnas.com/)
- [fnOS 开发者文档](https://developer.fnnas.com/)
- [fnOS 论坛](https://club.fnnas.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
