# fnOS 开发工具完整指南

> 本文档补充 fnOS_Developer_Guide.md 中的工具使用说明

## 目录

1. [图标 Icon 设计规范](#图标-icon-设计规范)
2. [fnpack 完整使用指南](#fnpack-完整使用指南)
3. [appcenter-cli 完整使用指南](#appcenter-cli-完整使用指南)

---

## 图标 Icon 设计规范

### 标准设计规范

- **尺寸规格**: 256 × 256 像素、64 × 64 像素
- **文件格式**: PNG、JPG
- **颜色空间**: sRGB
- **文件大小**: ≤ 1024 KB
- **形状规范**: 完整正方形直角图标

### 图标要求

**包文件图标:**
- `ICON.PNG` - 64 × 64 像素
- `ICON_256.PNG` - 256 × 256 像素
- 放置在项目根目录

**应用入口图标:**
- `app/ui/images/icon_64.png` - 64 × 64 像素
- `app/ui/images/icon_256.png` - 256 × 256 像素
- **注意**: 文件名必须小写

### 设计资源

- 含圆角矩形背景图层图标 PSD 源文件: [下载](https://static.fnnas.com/appcenter-marketing/fnpack_ICON_256.zip)
- 图标设计素材: [iconfont](https://www.iconfont.cn/)

---

## fnpack 完整使用指南

`fnpack` 是飞牛 fnOS 应用打包的便利工具，它帮助您快速创建应用项目结构并将应用打包成可安装的 `fpk` 文件。

### 工具下载

`fnpack` 已预置到飞牛 fnOS 中，同时也支持在本地使用：

- **Windows x86**: [fnpack-1.2.1-windows-amd64](https://static2.fnnas.com/fnpack/fnpack-1.2.1-windows-amd64)
- **Linux x86**: [fnpack-1.2.1-linux-amd64](https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-amd64)
- **Linux ARM**: [fnpack-1.2.1-linux-arm64](https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-arm64)
- **Mac Intel**: [fnpack-1.2.1-darwin-amd64](https://static2.fnnas.com/fnpack/fnpack-1.2.1-darwin-amd64)
- **Mac M系列**: [fnpack-1.2.1-darwin-arm64](https://static2.fnnas.com/fnpack/fnpack-1.2.1-darwin-arm64)

### 创建应用项目

#### 基本创建命令

```bash
# 创建独立项目
fnpack create <appname>

# 不带应用访问入口，使用纯服务类型的项目
fnpack create <appname> --without-ui true

# 创建 Docker 应用项目
fnpack create <appname> --template docker

# 无应用访问入口Docker应用，使用纯服务类型的项目
fnpack create <appname> --template docker --without-ui true
```

#### 关于 Docker 应用模板

- 自动生成 `docker-compose.yaml` 文件，需手动编辑
- 自动生成 `shares/data` 目录的挂载映射配置，可自行修改
- 自动生成 `cmd/main` 的 `status` 检查代码，可自行修改

#### 项目结构示例

创建后的项目结构如下：

```text
myapp/
├── app/                            # 应用可执行文件目录
│   ├── ui/
│   │   ├── images/
│   │   └── config
│   └── docker/                     # Docker 配置（Docker 应用模板）
│       └── docker-compose.yaml
├── cmd/                            # 应用生命周期管理脚本
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
│   ├── privilege                   # 应用权限配置
│   └── resource                    # 应用资源配置
├── wizard/
│   ├── install                     # 安装向导配置
│   ├── uninstall                   # 卸载向导配置
│   └── config                      # 配置向导
├── manifest                        # 应用基本信息
├── LICENSE                         # 许可证文件
├── ICON.PNG                        # 应用图标（64x64）
└── ICON_256.PNG                    # 应用图标（256x256）
```

### 打包应用项目

#### 基本打包命令

```bash
# 在应用目录中执行打包
cd myapp
fnpack build

# 指定打包的目录
fnpack build --directory <path>
```

#### 打包校验规则

| 路径 | 类型 | 校验规则 |
|------|------|----------|
| `manifest` | 文件 | 必须存在，且必选字段存在 |
| `config/privilege` | 文件 | 必须存在，且符合 JSON 格式 |
| `config/resource` | 文件 | 必须存在，且符合 JSON 格式 |
| `ICON.PNG` | 文件 | 必须存在 |
| `ICON_256.PNG` | 文件 | 必须存在 |
| `app/` | 目录 | 必须存在 |
| `cmd/` | 目录 | 必须存在 |
| `wizard/` | 目录 | 必须存在 |
| `app/{manifest.desktop_uidir}/` | 目录 | 若有定义，则目录必须存在 |

### 本地安装工具方法

```bash
# Linux/macOS 安装
chmod +x fnpack-1.2.1-linux-amd64
sudo mv fnpack-1.2.1-linux-amd64 /usr/local/bin/fnpack

# 验证安装
fnpack --help
```

### 最佳实践

1. **模板选择**: 根据应用类型选择合适的模板
2. **集成编译**: 将打包目录创建于代码目录下，并将 `fnpack build` 命令集成到代码编译脚本中

---

## appcenter-cli 完整使用指南

`appcenter-cli` 是飞牛 fnOS 系统预装的应用中心管理工具，它让您能够通过命令行来管理应用的安装、配置和系统设置。

### 安装应用

#### 通过 fpk 文件安装

```bash
# 基本安装命令
appcenter-cli install-fpk myapp.fpk

# 指定环境变量文件进行静默安装
appcenter-cli install-fpk myapp.fpk --env config.env
```

#### 环境变量文件格式

当应用包含安装向导时，您可以通过环境变量文件来跳过交互式配置：

**config.env 示例:**

```yaml
# 应用配置
wizard_admin_username=admin
wizard_admin_password=mypassword123
wizard_database_type=sqlite
wizard_app_port=8080

# 系统设置
wizard_agree_terms=true
```

#### 设置默认安装位置

如果您的系统有多个存储空间，可以设置默认的安装位置：

```bash
# 查看当前默认存储空间
appcenter-cli default-volume

# 设置存储空间1为默认安装位置
appcenter-cli default-volume 1

# 设置存储空间2为默认安装位置
appcenter-cli default-volume 2
```

#### 从本地目录安装

当您在开发环境中测试应用时，可以直接从应用目录安装，无需先打包成 fpk 文件：

```bash
# 在应用开发目录中执行
cd /path/to/myapp
appcenter-cli install-local
```

这个命令会自动完成打包和安装过程，大大提升开发测试效率。

### 系统管理

#### 手动安装功能

当您需要与团队成员分享应用时，可以临时开启手动安装功能：

```bash
# 查看当前状态
appcenter-cli manual-install

# 开启手动安装功能
appcenter-cli manual-install enable

# 关闭手动安装功能
appcenter-cli manual-install disable
```

开启后，其他用户就可以通过应用中心的手动安装入口来安装您分享的 fpk 文件。

### 应用管理

```bash
# 查看已安装的应用列表
appcenter-cli list

# 启动应用
appcenter-cli start myapp

# 停止应用
appcenter-cli stop myapp

# 重启应用
appcenter-cli restart myapp

# 查看应用状态
appcenter-cli status myapp

# 卸载应用
appcenter-cli uninstall myapp

# 查看应用日志
appcenter-cli logs myapp
```

### 最佳实践

#### 安装前准备

1. **检查存储空间**: 确保有足够的存储空间安装应用
2. **准备配置文件**: 为包含向导的应用准备环境变量文件
3. **验证 fpk 文件**: 确保 fpk 文件完整且未损坏

#### 开发工作流

1. **本地开发**: 使用 `install-local` 快速测试
2. **打包测试**: 使用 `install-fpk` 测试打包版本
3. **配置管理**: 使用环境变量文件管理不同环境的配置

#### 安全考虑

- 手动安装功能仅在需要时开启，使用完毕后及时关闭
- 环境变量文件包含敏感信息，注意文件权限管理
- 生产环境安装前先在测试环境验证

---

## 相关资源

- [fnOS 官方网站](https://www.fnnas.com/)
- [fnOS 开发者文档](https://developer.fnnas.com/)
- [fnOS 论坛](https://club.fnnas.com/)
