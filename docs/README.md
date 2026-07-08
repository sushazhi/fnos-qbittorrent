# fnos-qbittorrent 文档

## 官方 fnOS 开发文档（权威来源）

> **所有通用 fnOS 应用开发知识**，不再本地维护副本。
> 官方已提供 AI 友好的文档索引和完整快照，始终保持最新。

| 资源 | URL | 用途 |
|------|-----|------|
| **文档索引** | https://developer.fnnas.com/llms.txt | 按分类列出所有文档链接，快速定位 |
| **完整文档** | https://developer.fnnas.com/llms-full.txt | 完整内容快照，AI 工具可直接批量摄入 |

**涵盖内容**：应用框架、Manifest、环境变量、应用权限、应用资源、应用入口、index.cgi、统一网关、用户向导、应用依赖、中间件服务、运行时环境、图标规范、CLI 工具（fnpack / appcenter-cli）、Native/Docker 应用案例、更新日志。

**使用方式**：

```bash
# AI 工具可直接读取完整文档
curl -fsSL https://developer.fnnas.com/llms-full.txt

# 或先看索引再定位到具体页面
curl -fsSL https://developer.fnnas.com/llms.txt
```

---

## 项目特有文档

| 文档 | 内容 |
|------|------|
| [CI_CD.md](./CI_CD.md) | GitHub Actions CI/CD 配置、构建工作流、发布流程 |
| [项目 README](../README.md) | 安装、构建、网关架构、项目结构、默认配置、界面说明 |

---

## 常见问题

### 为什么 docs/ 里没有传统的 fnOS 开发指南？

之前维护了 4 份本地通用开发文档（~4,000 行），但官方已提供 `llms.txt` / `llms-full.txt`，专门为 AI 和开发者设计且持续更新。本地维护副本必然过时，因此全部裁剪，统一指向官方源。

### 开发 fnOS 应用时怎么看文档？

1. 先看 `llms.txt` 了解文档结构
2. 需要某个主题的完整内容，直接读取 `llms-full.txt`（或打开具体页面）
3. 本项目特有的实现细节，参考上述「项目特有文档」

### 之前同步的 fnnas_developer_guide_full.md 呢？

已在 2026-07-08 同步到官方 2026-07-05 版本后，替换为指向官方 `llms-full.txt` 的引用。不再维护本地快照。
