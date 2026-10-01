# GitHub Actions 使用指南

本文档说明如何使用 qBittorrent for fnOS 项目的 GitHub Actions 工作流。

## 概述

项目配置了两个 GitHub Actions 工作流文件：

1. **Build and Release**（`.github/workflows/build-and-release.yml`）- 构建 .fpk 包；推送 `v*` 标签时同时创建 GitHub Release
2. **Monthly Upstream Sync**（`.github/workflows/monthly-upstream-sync.yml`）- 每月最后一天检查并同步上游版本

> 发布（Release）不是独立文件，而是 `build-and-release.yml` 里的 `release` job，仅在标签构建时运行。

## Monthly Upstream Sync 工作流

### 触发条件

- **定时**：每月最后一天（UTC 00:00，即北京时间 08:00）
- **手动触发**：`workflow_dispatch`，支持 `force`（强制产生一次更新，仅手动触发有效）与 `dry_run`（只改 manifest、不提交）两个开关

### 功能

- ✅ 每月最后一天检查上游 `userdocs/qbittorrent-nox-static` 最新版本
- ✅ 有更新：改写 `manifest` 的 `version` 与 `changelog` → 提交推送 → 打 tag → 触发构建发布
- ✅ 无更新：不产生任何提交；但仍会检查「manifest 当前版本是否已完整发布」
- ✅ 自愈：若发现 manifest 版本**缺少远端 tag**或**缺少 GitHub Release**（上次运行部分失败），会补打 tag 并重新触发一次构建发布，避免永久漏发

### 「每月最后一天」的实现方式

GitHub Actions 的 cron 是标准 5 段表达式，**无法直接表达「每月最后一天」**，因此采用官方推荐的组合写法：

```yaml
on:
  schedule:
    - cron: '0 0 28-31 * *'   # 每月 28~31 日都触发
```

再在 job 内用运行时判断收敛到真正的最后一天：

```bash
TOMORROW=$(date -u -d "+1 day" +%d)
if [ "${TOMORROW}" = "01" ]; then ... # 今天是本月最后一天
```

这样可正确覆盖 31 天月、30 天月、平年 2 月（28 日）与闰年 2 月（29 日），且不会出现「重跑」。

> 注意：受 GitHub 定时任务排队延迟影响，触发时间可能晚于 UTC 00:00；若被延迟到次月 1-3 号才执行，guard 会把这种运行同样按「上月末」处理并继续执行，避免整月静默跳过。重复执行是安全的，因为下游的 tag / Release 检查是幂等的。另外，仓库连续 60 天无提交活动时 GitHub 会自动停用定时工作流，需在 Actions 页面重新启用。

### 版本判定规则

| 上游情况 | 处理 |
| --- | --- |
| 上游 qBittorrent 版本 > manifest 前 3 段 | 有新版本，`version = <上游版本>.0`，changelog 记为「同步上游版本」 |
| 上游 qBittorrent 相同，libtorrent 高于 manifest 记录 | 重新打包，第 4 段（修订号）+1，changelog 记为「重新打包」 |
| 上游 qBittorrent 相同，libtorrent 低于或等于 manifest 记录 | 无更新，跳过（降级不会触发新版本） |
| 其余 | 无更新，跳过 |

> 若 `manifest` 的 changelog 中缺少 libtorrent 记录，libtorrent 规则无法生效，脚本会输出 `::warning::` 提示，避免上游 libtorrent 升级被静默漏掉。

### 为什么用 `gh workflow run` 而不是靠标签推送自动触发

GitHub 有一条重要限制：**用默认的 `GITHUB_TOKEN` 推送的事件（包括标签推送）不会再次触发其它 workflow**（防止递归）。因此同步工作流在推送标签后，会显式调用：

```bash
gh workflow run build-and-release.yml --ref "v<new_version>" -f "qbt_release_tag=<upstream_tag>"
```

`workflow_dispatch` 事件不受该递归限制，所以构建与发布能被可靠触发。这也意味着工作流需要 `actions: write` 权限。

其中 `-f qbt_release_tag=...` 会把同步工作流解析出的上游 tag 直接传给构建，保证「下载的二进制」与「manifest/changelog 记录的版本」严格一致。若不传（例如补发路径），构建侧会退化为按 qBittorrent 版本前缀匹配并取 libtorrent 最高的一条。

> 如果希望「推标签自动触发构建」而不显式 dispatch，则需改用 Personal Access Token（PAT）来推送标签，但那样会与显式 dispatch 一起造成重复构建，故本项目采用显式 dispatch 的确定性方案。

### 脚本

版本检查逻辑封装在 `scripts/check_upstream.py`（仅用标准库，可本地直接运行）：

```bash
# 只检查
python3 scripts/check_upstream.py

# 检查并改写 manifest
python3 scripts/check_upstream.py --write

# 强制产生一次更新（测试用）
python3 scripts/check_upstream.py --force --write
```

## Build and Release 工作流

### 触发条件

- 推送 `v*` 标签（例如 `v5.2.4.0`）
- 创建 Pull Request 到 `main` / `develop` / `test`
- 手动触发（可选择 VueTorrent 版本）
- 被 Monthly Upstream Sync 通过 `gh workflow run` 触发（此时 `github.ref` 为该 tag，因此也会创建 Release）

### 功能

- ✅ 支持多架构（amd64, arm64）
- ✅ 从 userdocs 静态构建下载 qBittorrent-nox（musl 静态链接），版本由 `manifest` 决定
- ✅ 集成 VueTorrent WebUI 与更新检查脚本
- ✅ 创建 .fpk 包格式
- ✅ 上传构建产物（保留30天）
- ✅ 标签构建时自动创建 GitHub Release
- ✅ 校验下载到的二进制版本与 `manifest` 一致（不一致直接失败，避免产出「包名与内容不符」的包）

### 环境配置

- **二进制来源**: userdocs/qbittorrent-nox-static (musl 静态)
- **qBittorrent / libtorrent 版本**: 以仓库根目录 `manifest` 为准（当前 5.2.4 / 2.0.15）
- **上游 tag**: 优先由调用方通过 `qbt_release_tag` 传入；未传时按 `manifest` 的 qBittorrent 版本匹配，并取 libtorrent 最高的一条

### 构建产物

每次构建会生成：
- `qbittorrent-{version}-{arch}.fpk` - fnOS 安装包（amd64 与 arm64 各一个）
- `qbittorrent-nox` - 二进制文件（构建过程中使用）

### 下载构建产物

1. 访问 GitHub Actions 页面
2. 选择对应的 workflow run
3. 在 "Artifacts" 部分下载所需产物

### 手动触发构建

1. 进入 Actions 标签
2. 选择 "Build and Release qBittorrent for fnOS" 工作流
3. 点击 "Run workflow"
4. 可选填写 VueTorrent 版本（留空为 `latest`）
5. 可选填写 `qbt_release_tag`（上游 tag，如 `release-5.2.4_v2.0.15`；留空则按 `manifest` 版本自动匹配 libtorrent 最高的一条）
6. 点击 "Run workflow" 按钮

> 架构由 workflow 内的 matrix 决定（arm64 + amd64 并行构建），无需手动选择。

## Release 发布

Release 由 `build-and-release.yml` 中的 `release` job 负责，**没有单独的 `release.yml`**。

### 触发条件

- `build` job 成功完成，且当前 ref 是 `v*` 标签（`if: startsWith(github.ref, 'refs/tags/v')`）

### 功能

- ✅ 下载两个架构的 .fpk 产物
- ✅ 从 `manifest` 的 `changelog` 生成发布说明
- ✅ 自动创建 GitHub Release 并附加 .fpk 包

### 创建发布

#### 方法 1: 手动推送标签

```bash
git tag -a v5.2.4.0 -m "Release version 5.2.4.0"
git push origin v5.2.4.0
```

#### 方法 2: 由 Monthly Upstream Sync 自动完成

每月最后一天检测到上游有更新时，会自动改写 `manifest` → 提交 → 打标签 → 触发构建发布，无需人工介入。

#### 方法 3: 手动触发同步工作流

在 Actions 中选择 "Monthly Upstream Sync"，勾选 `force` 可强制产生一次更新（`force` 仅对手动触发有效，定时触发时会被忽略）。

> 注意：`force` 会真实提交 manifest、打 tag 并触发构建发布；若只想预览，请改用 `dry_run`。

> 由于本仓库的 Release job 不是幂等的，若对**已发布过**的版本重复触发 `force`，`gh release create` 会因 Release 已存在而失败；此时请先删除对应 Release/标签，或先递增 `manifest` 版本。

## CI/CD 最佳实践

### Pull Request 流程

1. 创建功能分支
2. 提交代码
3. 创建 PR 到 `main` / `develop` / `test`
4. CI 自动运行 `build-and-release.yml` 的构建 job（不发布 Release）
5. 确保构建通过
6. 请求代码审查
7. 合并到 main

### 发布流程

**自动（推荐）**：每月最后一天由 Monthly Upstream Sync 检查上游，有更新则自动完成「改 manifest → 提交 → 打标签 → 构建 → 发布」。

**手动**：

1. 修改 `manifest` 的 `version` 与 `changelog`
2. 合并到 main
3. 推送同名标签（`git push origin v5.2.4.0`）
4. `build-and-release.yml` 自动构建并创建 GitHub Release

### 故障排查

#### 构建失败

1. 查看 Actions 日志
2. 检查错误信息
3. 本地用 `python build.py` 复现问题
4. 提交修复
5. 重新触发构建

#### 同步工作流失败

1. 查看 "Monthly Upstream Sync" 的日志
2. `check_upstream.py` 退出码含义：`2` manifest 缺失、`3` 无法获取上游 release、`4` 上游没有可识别的 tag
3. 确认 `GITHUB_TOKEN` 未被上游 API 限流（脚本会自动使用 `secrets.GITHUB_TOKEN` 访问 `api.github.com`，无需额外配置；若确实被限流，可改用 `--api-base` 走镜像）
4. 修复后手动 `workflow_dispatch` 重跑

#### 下载产物失败

1. 确认构建已成功完成
2. 检查 artifact 是否仍在保留期内（30天）
3. 尝试从不同的 run 下载

## 本地测试

### 本地测试版本检查脚本

`scripts/check_upstream.py` 只用 Python 标准库，可脱离 CI 直接运行：

```bash
python3 scripts/check_upstream.py                  # 只检查，打印结果
python3 scripts/check_upstream.py --write          # 检查并改写 manifest
python3 scripts/check_upstream.py --force --write  # 强制产生一次更新（测试用）
```

### 使用 act 本地测试 Actions

使用 [act](https://github.com/nektos/act) 在本地测试 GitHub Actions：

```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows
choco install act-cli
```

```bash
# 列出所有工作流
act -l

# 运行构建 job
act -j build

# 手动触发同步工作流（dry_run，只改 manifest 不提交）
act workflow_dispatch -j sync --input dry_run=true
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
- [fnOS 开发文档 (llms.txt)](https://developer.fnnas.com/llms.txt)
