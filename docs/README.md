# fnOS 应用开发文档索引

> 本项目包含完整的 fnOS 应用开发文档体系

## 📚 文档列表

### 1. [fnOS_Developer_Guide.md](./fnOS_Developer_Guide.md) - 基础开发指南

**适合人群**: 初学者、新手开发者

**主要内容**:
- ✅ fnOS 系统概述
- ✅ 快速开始指南
- ✅ 应用结构说明
- ✅ 生命周期脚本详解
- ✅ 配置文件说明 (manifest, privilege, resource)
- ✅ 向导界面配置
- ✅ 环境变量说明
- ✅ 开发工具介绍

**文档规模**: 1,741 行

---

### 2. [fnOS_Advanced_Guide.md](./fnOS_Advanced_Guide.md) - 进阶开发指南

**适合人群**: 有一定经验的开发者

**主要内容**:
- ✅ 应用依赖关系管理
- ✅ 运行时环境配置 (Python, Node.js, Java)
- ✅ 中间件服务集成 (Redis, MinIO, RabbitMQ)
- ✅ Docker 应用构建完整流程
- ✅ Native 应用构建实战案例

**文档规模**: 600 行

---

### 3. [fnOS_Tools_Guide.md](./fnOS_Tools_Guide.md) - 开发工具完整指南

**适合人群**: 所有开发者

**主要内容**:
- ✅ 图标 Icon 设计规范
- ✅ fnpack 完整使用指南
- ✅ appcenter-cli 完整使用指南
- ✅ 最佳实践建议

**文档规模**: 400 行

---

### 4. [CI_CD.md](./CI_CD.md) - CI/CD 文档

**适合人群**: 需要自动化构建的开发者

**主要内容**:
- ✅ GitHub Actions 配置
- ✅ 自动化构建流程
- ✅ 发布管理

---

### 5. [IMPROVEMENT_SUGGESTIONS.md](./IMPROVEMENT_SUGGESTIONS.md) - 项目改进建议

**适合人群**: 维护者、贡献者

**主要内容**:
- ✅ 短期可落地优化项（安全、安装体验、FAQ、CI）
- ✅ 中长期演进方向（配置统一化、日志诊断、测试体系）
- ✅ 建议执行顺序与效果指标

---

## 🎯 学习路径建议

### 初学者路径

```
1. fnOS_Developer_Guide.md (基础概念)
   ↓
2. fnOS_Tools_Guide.md (工具使用)
   ↓
3. 实践开发
   ↓
4. fnOS_Advanced_Guide.md (进阶内容)
```

### 有经验开发者路径

```
1. fnOS_Developer_Guide.md (快速了解)
   ↓
2. fnOS_Advanced_Guide.md (深入内容)
   ↓
3. fnOS_Tools_Guide.md (工具参考)
   ↓
4. CI_CD.md (自动化构建)
```

---

## 📖 文档特点

### 1. 完整性

- ✅ 覆盖从基础到进阶的全部内容
- ✅ 包含 60+ 完整代码示例
- ✅ 提供实战案例参考

### 2. 准确性

- ✅ 所有内容基于官方文档
- ✅ 所有示例经过验证
- ✅ 所有配置符合规范

### 3. 实用性

- ✅ 提供详细使用说明
- ✅ 提供最佳实践建议
- ✅ 提供常见问题解答

---

## 🔍 快速查找

### 按主题查找

| 主题 | 文档 | 章节 |
|------|------|------|
| 应用结构 | Developer Guide | 应用结构 |
| 生命周期脚本 | Developer Guide | 生命周期脚本 |
| 配置文件 | Developer Guide | 配置文件 |
| 向导界面 | Developer Guide | 向导界面 |
| 环境变量 | Developer Guide | 环境变量 |
| 数据共享路径 | Developer Guide | 环境变量 → TRIM_DATA_SHARE_PATHS |
| 依赖管理 | Advanced Guide | 应用依赖关系 |
| 运行时环境 | Advanced Guide | 运行时环境 |
| 中间件服务 | Advanced Guide | 中间件服务 |
| Docker 应用 | Advanced Guide | Docker 应用构建 |
| Native 应用 | Advanced Guide | Native 应用构建 |
| 图标设计 | Tools Guide | 图标 Icon 设计规范 |
| fnpack 工具 | Tools Guide | fnpack 完整使用指南 |
| appcenter-cli | Tools Guide | appcenter-cli 完整使用指南 |

### 按需求查找

| 需求 | 推荐文档 |
|------|----------|
| 我要快速开始 | Developer Guide → 快速开始 |
| 我要了解应用结构 | Developer Guide → 应用结构 |
| 我要配置安装向导 | Developer Guide → 向导界面 |
| 我要使用 Python | Advanced Guide → 运行时环境 |
| 我要使用 Redis | Advanced Guide → 中间件服务 |
| 我要开发 Docker 应用 | Advanced Guide → Docker 应用构建 |
| 我要设计图标 | Tools Guide → 图标 Icon 设计规范 |
| 我要打包应用 | Tools Guide → fnpack 完整使用指南 |
| 我要安装应用 | Tools Guide → appcenter-cli 完整使用指南 |
| 我要使用数据共享路径 | Developer Guide → 环境变量 → TRIM_DATA_SHARE_PATHS |

---

## 📝 文档更新记录

### 2025-02-25

- ✅ 补充 `TRIM_DATA_SHARE_PATHS` 环境变量说明
- ✅ 添加数据共享路径使用示例
- ✅ 补充安装后目录结构说明
- ✅ 补充目录功能说明表格
- ✅ 更新 manifest 字段说明（platform、install_dep_apps 等）
- ✅ 补充 resource 配置：usr-local-linker、docker-project

### 2025-02-22

- ✅ 完整阅读官方文档 3,612 行
- ✅ 创建基础开发指南 (1,741 行)
- ✅ 创建进阶开发指南 (600 行)
- ✅ 创建工具完整指南 (400 行)
- ✅ 更正所有错误内容
- ✅ 补充所有缺失内容

---

## 🔗 相关资源

### 官方资源

- [fnOS 官方网站](https://www.fnnas.com/)
- [fnOS 开发者文档](https://developer.fnnas.com/docs/guide)
- [fnOS 论坛](https://club.fnnas.com/)

### 官方文档链接

> 来源：https://developer.fnnas.com/docs/category/开发指南

**📚 【基础】**

| 文档 | URL |
|------|-----|
| 架构概述 | https://developer.fnnas.com/docs/core-concepts/framework |
| Manifest | https://developer.fnnas.com/docs/core-concepts/manifest |
| 环境变量 | https://developer.fnnas.com/docs/core-concepts/environment-variables |
| 应用权限 | https://developer.fnnas.com/docs/core-concepts/privilege |
| 应用资源 | https://developer.fnnas.com/docs/core-concepts/resource |
| 应用入口 | https://developer.fnnas.com/docs/core-concepts/app-entry |
| 用户向导 | https://developer.fnnas.com/docs/core-concepts/wizard |

**🔥 【进阶】**

| 文档 | URL |
|------|-----|
| 应用依赖关系 | https://developer.fnnas.com/docs/core-concepts/dependency |
| 运行时环境 | https://developer.fnnas.com/docs/core-concepts/runtime |
| 中间件服务 | https://developer.fnnas.com/docs/core-concepts/middleware |

**💻 【实战】**

| 文档 | URL |
|------|-----|
| Docker 应用构建 | https://developer.fnnas.com/docs/core-concepts/docker |
| Native 应用构建 | https://developer.fnnas.com/docs/core-concepts/native |

**📜 【规范】**

| 文档 | URL |
|------|-----|
| 图标 Icon | https://developer.fnnas.com/docs/core-concepts/icon |

**🚀 快速开始**

| 文档 | URL |
|------|-----|
| 准备工作 | https://developer.fnnas.com/docs/quick-started/prerequisites |
| 创建应用 | https://developer.fnnas.com/docs/quick-started/create-application |
| 测试应用 | https://developer.fnnas.com/docs/quick-started/test-application |
| 上架应用 | https://developer.fnnas.com/docs/quick-started/publish-application |

**🔧 CLI 工具**

| 文档 | URL |
|------|-----|
| fnpack | https://developer.fnnas.com/docs/cli/fnpack |
| appcenter-cli | https://developer.fnnas.com/docs/cli/appcentercli |

### 开发工具

- [fnpack 下载](https://static2.fnnas.com/fnpack/)
- [appcenter-cli 下载](https://static2.fnnas.com/cli/)

### 设计资源

- [图标 PSD 源文件](https://static.fnnas.com/appcenter-marketing/fnpack_ICON_256.zip)
- [iconfont 图标库](https://www.iconfont.cn/)

---

## 💡 使用建议

1. **离线查阅**: 所有文档均为 Markdown 格式,可离线使用
2. **快速搜索**: 使用 Ctrl+F 在文档中搜索关键词
3. **代码复制**: 所有代码示例均可直接复制使用
4. **实践优先**: 建议边学边做,快速上手

---

**文档维护**: 本文档体系基于官方文档创建,将持续更新以保持与官方同步。
