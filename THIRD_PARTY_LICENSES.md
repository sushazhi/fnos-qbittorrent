# 第三方许可与源代码说明（Third-Party Licenses / NOTICE）

本应用（`qBittorrent for fnOS`，整体以 **GPL-2.0** 分发）在发布包（`.fpk`）中包含以下上游开源组件的预编译/构建产物。

根据 GPL-2.0 第 3 条与 MIT 许可条件，下方说明各组件的许可证、版权及**对应源代码的获取方式**（即 GPL-2.0 要求的"书面要约"）。

---

## 1. qBittorrent（核心 BT 下载引擎）

- **组件**：`qbittorrent-nox`（FNOS 包内 `app/bin/qbittorrent-nox`）
- **上游来源**：[userdocs/qbittorrent-nox-static](https://github.com/userdocs/qbittorrent-nox-static)（静态编译构建）
- **原始项目**：[qBittorrent/qBittorrent](https://github.com/qbittorrent/qBittorrent)
- **许可证**：GPL-2.0
- **对应源代码获取方式**：
  - qBittorrent 源码：<https://github.com/qbittorrent/qBittorrent> （按包版本 tag 获取，如 `release-5.2.3`）
  - 静态构建（含 libtorrent/qt 依赖及构建脚本）：<https://github.com/userdocs/qbittorrent-nox-static>
  - 本包构建脚本 `build.py` 从 `userdocs/qbittorrent-nox-static` 对应 release tag 下载 `qbittorrent-nox` 二进制；其完整对应源代码（含所有依赖的版本与构建步骤）均在上述仓库公开可获取，并随本仓库 `build.py` 一同提供"如何从源码复现"的说明。

## 2. VueTorrent（现代 WebUI 界面）

- **组件**：`app/ui/vuetorrent/`（构建产物）
- **项目**：[VueTorrent/VueTorrent](https://github.com/VueTorrent/VueTorrent)
- **许可证**：MIT
- **许可证文本**：随包提供于 `app/ui/vuetorrent/LICENSE`（MIT 全文，含原始版权声明）
- **对应源代码获取方式**：<https://github.com/VueTorrent/VueTorrent> （按包内 VueTorrent 版本 tag 获取）

## 3. 本项目（qBittorrent for fnOS 包装层）

- **许可证**：GPL-2.0
- **源代码**：<https://github.com/sushazhi/fnos-qbittorrent>
- **许可证全文**：随包提供于 `LICENSE`

---

> 说明：本项目作为 qBittorrent / VueTorrent 的封装与网关适配层，自身以 GPL-2.0 许可开源。VueTorrent（MIT）与 GPL-2.0 兼容，可被整体以 GPL-2.0 聚合分发，但其 MIT 许可证与版权声明已按上述要求随包保留。
