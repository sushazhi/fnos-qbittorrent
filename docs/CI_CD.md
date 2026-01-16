# GitHub Actions 使用指南

本文档说明如何使用 qBittorrent for fnOS 项目的 GitHub Actions 工作流。

## 概述

项目配置了三个主要的 GitHub Actions 工作流：

1. **Build** - 自动构建 .fpk 包
2. **Test & Lint** - 代码质量检查和测试
3. **Release** - 自动创建发布

## Build 工作流

### 触发条件

- 推送到 `main` 或 `develop` 分支
- 创建 Pull Request
- 手动触发（支持选择架构）

### 功能

- ✅ 支持多架构（x86_64, ARM64）
- ✅ 从 userdocs 静态构建下载 qBittorrent-nox 5.1.4 (musl 静态链接)
- ✅ 集成 WebUI
- ✅ 创建 .fpk 包格式
- ✅ 生成 SHA256 校验和
- ✅ 上传构建产物（保留30天）

### 环境配置

- **二进制来源**: userdocs/qbittorrent-nox-static (musl 静态)
- **qBittorrent 版本**: 5.1.4
- **libtorrent 版本**: 2.0.11

### 构建产物

每次构建会生成：
- `qbittorrent-{version}-{arch}.fpk` - fnOS 安装包
- `qbittorrent-{version}-{arch}.fpk.sha256sum` - SHA256 校验和
- `qbittorrent-nox-{arch}` - 二进制文件（调试用）

### 下载构建产物

1. 访问 GitHub Actions 页面
2. 选择对应的 workflow run
3. 在 "Artifacts" 部分下载所需产物

### 手动触发构建

1. 进入 Actions 标签
2. 选择 "Build qBittorrent for fnOS" 工作流
3. 点击 "Run workflow"
4. 选择目标架构（x86_64 或 ARM64）
5. 点击 "Run workflow" 按钮

## Test & Lint 工作流

### 触发条件

- 推送到 `main` 或 `develop` 分支
- 创建 Pull Request
- 手动触发

### 检查项目

#### Lint 检查

1. **Shell 脚本 Lint**
   - 工具: shellcheck
   - 检查: `cmd/*`, `wizard/*`
   - 规则: POSIX 兼容、错误处理、最佳实践

2. **JSON 格式验证**
   - 工具: jq
   - 检查: `config/privilege`, `config/resource`, `package.json`

3. **Manifest 格式验证**
   - 检查必需字段
   - 格式规范验证

4. **脚本权限检查**
   - 验证可执行文件权限
   - 检查 shebang

5. **硬编码路径检查**
   - 检查脚本中的硬编码路径
   - 推荐使用环境变量

6. **文件结构验证**
   - 验证必需文件存在

#### 集成测试

1. **应用结构测试**
   - 验证 fnOS 应用结构

2. **环境变量使用测试**
   - 验证脚本使用正确的 fnOS 环境变量

3. **配置默认值测试**
   - 从 manifest 提取关键配置

4. **脚本语法测试**
   - bash 语法验证

### 查看测试结果

1. 进入 Actions 标签
2. 选择对应的 workflow run
3. 展开 "Test & Lint" job
4. 查看每个步骤的详细输出

## Release 工作流

### 触发条件

- 推送版本标签（例如 `v5.1.4`）
- 手动触发（支持指定版本、草稿模式、预发布模式）

### 功能

- ✅ 自动创建 GitHub Release
- ✅ 生成发布说明
- ✅ 上传所有架构的 .fpk 包
- ✅ 生成并上传 SHA256 校验和
- ✅ 提取 changelog 和 commits
- ✅ 支持 Slack/Discord 通知（可选）

### 创建发布

#### 方法 1: 推送标签

```bash
# 创建并推送标签
git tag -a v5.1.4 -m "Release version 5.1.4"
git push origin v5.1.4
```

#### 方法 2: 手动触发

1. 进入 Actions 标签
2. 选择 "Create Release" 工作流
3. 点击 "Run workflow"
4. 填写版本号（例如 `v5.1.4`）
5. 选择是否为草稿或预发布
6. 点击 "Run workflow" 按钮

### Release 内容

自动生成的 Release 包含：

- **版本信息和 changelog**
- **下载表格**（包含所有架构和 SHA256）
- **安装指南**
- **验证方法**
- **系统要求**
- **默认凭据信息**
- **支持链接**
- **Git commits 历史记录**

### 配置通知（可选）

要启用 Slack 或 Discord 通知，需要配置 Secrets：

#### Slack

1. 创建 Slack Webhook
2. 在 GitHub 仓库设置中添加 Secret: `SLACK_WEBHOOK_URL`
3. 在 `release.yml` 中设置 `if: false` 为 `if: true`

#### Discord

1. 创建 Discord Webhook
2. 在 GitHub 仓库设置中添加 Secret: `DISCORD_WEBHOOK`
3. 在 `release.yml` 中设置 `if: false` 为 `if: true`

## CI/CD 最佳实践

### Pull Request 流程

1. 创建功能分支
2. 提交代码
3. 创建 PR
4. CI 自动运行：
   - Test & Lint 检查
   - Build 检查
5. 确保所有检查通过
6. 请求代码审查
7. 合并到 develop

### 发布流程

1. 从 develop 创建 release 分支
2. 更新版本号和 changelog
3. 合并到 main
4. 推送标签触发 Release workflow
5. Release workflow 自动创建 GitHub Release

### 故障排查

#### 构建失败

1. 查看 Actions 日志
2. 检查错误信息
3. 本地复现问题
4. 提交修复
5. 重新触发构建

#### 测试失败

1. 查看 Test & Lint 日志
2. 定位具体失败的检查
3. 修复问题
4. 提交修复

#### 下载产物失败

1. 确认构建已成功完成
2. 检查 artifact 是否仍在保留期内（30天）
3. 尝试从不同的 run 下载

## 本地测试 Actions

使用 [act](https://github.com/nektos/act) 在本地测试 GitHub Actions：

### 安装 act

```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows
choco install act-cli
```

### 运行工作流

```bash
# 列出所有工作流
act -l

# 运行 Build 工作流
act -j build

# 运行 Test & Lint 工作流
act -j lint

# 模拟 Pull Request 事件
act pull_request
```

## 性能优化建议

### 减少构建时间

1. **使用 Docker 层缓存**（已在 workflow 中配置）
2. **并行构建**：使用 `matrix` 策略
3. **仅构建必要内容**：使用条件执行

### 减少存储空间

1. **清理旧 artifacts**：自动删除超过保留期的产物
2. **压缩产物**：使用 .fpk 格式（已压缩）

## 监控和维护

### 监控构建状态

- Actions 页面显示所有 workflow 运行状态
- 设置失败通知（GitHub 自动发送）

### 更新依赖

定期检查并更新：
- Qt 版本
- libtorrent 版本
- qBittorrent 版本
- Actions 版本

### 审查工作流

定期审查 workflow 文件以确保：
- 安全性（secrets 使用）
- 效率（构建时间）
- 准确性（测试覆盖）

## 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [fnOS 开发者文档](https://developer.fnnas.com/)
- [项目 README](../README.md)
- [开发指南](../AGENTS.md)
