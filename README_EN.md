# qBittorrent for fnOS 🚀

🌐 **语言/Language** 
 - [简体中文]( README.md ) | [English]( README_EN.md )

A powerful and beautiful BitTorrent download tool for Feiniu NAS.

![qBittorrent](https://img.shields.io/badge/qBittorrent-5.1.4-blue?style=flat-square&logo=qbittorrent)
![VueTorrent](https://img.shields.io/badge/VueTorrent-2.31.3-purple?style=flat-square&logo=vue.js)
![Platform](https://img.shields.io/badge/Platform-fnOS-green?style=flat-square&logo=nas)
![License](https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Dual WebUI** | VueTorrent by default, switchable to native interface |
| 📡 **Full BT Protocol** | BitTorrent v1/v2, DHT/PEX/LSD P2P network |
| 📰 **RSS Support** | RSS auto-download and subscription management |
| 🔍 **Search Engine** | Built-in multi-engine search |
| ⚡ **Speed Control** | Flexible speed limits and queue management |
| 🌐 **Remote Access** | Built-in Web UI, access anywhere |
| 📁 **File Management** | Sequential download, selective download, file priority |
| 🛡️ **IP Filtering** | IP filter list and protocol encryption |

---

## 🎨 Dual WebUI Design

This app includes **two beautiful interfaces**, VueTorrent by default:

| Interface | Features |
|-----------|----------|
| **VueTorrent** ✨ | Modern UI, responsive design, Vue 3 + Vuetify 3, multi-language |
| **qBittorrent Native** | Full-featured, lightweight, quick switch |

> 💡 **How to switch**: Go to qBittorrent → Settings → Web UI → Uncheck "Use alternative Web UI"
> 
> 📌 **Note**: When using native UI, you must **open a new tab** to access settings and switch.

---

## 📦 Installation

> 📌 **Note**: This app currently **supports ARM64 only** (e.g., fnOS ARM version)

### Manual Installation

1. Open **App Center**
2. Click **Manual Install** in the bottom left
3. Select `qbittorrent-vuetorrent-5.1.4-arm64.fpk` package

```bash
# Command line installation (optional)
appcenter-cli install-local qbittorrent-vuetorrent-5.1.4-arm64.fpk
```

---

## 💻 System Requirements

| Item | Default |
|------|---------|
| Access URL | `http://<your_NAS_IP>:8080` |
| Default Username | `admin` |
| Default Password | `adminadmin` |
| WebUI Port | `8080` (not modifiable yet) |

> ⚠️ **Security Tip**: Please change the default password after first login!

---

## 🤝 Support & Feedback

- 🐛 [Report Issues](https://github.com/sushazhi/fnos-qbittorrent/issues)
- 💬 [fnOS Forum](https://club.fnnas.com/)
- 📖 [fnOS Developer Docs](https://developer.fnnas.com/)

---

## 📁 Project Structure

### Core Directory Structure

```
fnos-qb/
├── .github/             # GitHub Actions workflow configurations
│   └── workflows/       # CI/CD build and release configurations
├── app/                 # Application core files
│   └── ui/              # User interface related files
│       ├── images/      # Application icons
│       └── www/         # Web interface files
├── cmd/                 # Application command scripts
├── config/              # Configuration files directory
├── docs/                # Project documentation
├── wizard/              # Installation wizard files
├── artifacts/           # Build artifacts directory
├── README.md            # Chinese documentation
├── README_EN.md         # English documentation
├── LICENSE              # License file
├── manifest             # Application manifest file
└── package.json         # Project configuration file
```

### Build Artifacts

The build process generates the following files in the `artifacts/` directory:

| File Type | Description |
|-----------|-------------|
| `.fpk` file | fnOS application installation package |
| `.sha256sum` file | SHA256 checksum for the installation package |

Examples:
- `qbittorrent-vuetorrent-5.1.4.1-test-arm64.fpk`
- `qbittorrent-vuetorrent-5.1.4.1-test-arm64.fpk.sha256sum`

## 📄 License

This project is open source under the [GPL-2.0](LICENSE) license.

**Credits**:
- [qBittorrent](https://www.qbittorrent.org/) - Powerful BitTorrent client
- [VueTorrent](https://github.com/VueTorrent/VueTorrent) - Beautiful qBittorrent WebUI
- [qbittorrent-nox-static](https://userdocs.github.io/qbittorrent-nox-static/) - qBittorrent static compilation guide
- [fnOS](https://www.fnnas.com/) - Excellent Chinese NAS system


