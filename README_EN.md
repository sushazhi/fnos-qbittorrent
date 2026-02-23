# qBittorrent for fnOS 🚀

🌐 **语言/Language** 
 - [简体中文]( README.md ) | [English]( README_EN.md )

A powerful and beautiful BitTorrent download tool for Feiniu NAS.

![qBittorrent](https://img.shields.io/badge/qBittorrent-5.1.4.3-blue?style=flat-square&logo=qbittorrent)
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
| 🔔 **Update Detection** | VueTorrent interface auto-detects latest version on GitHub |
| 🔧 **Port Configuration** | Customize port during installation or in app settings |

---

## 🎨 Dual WebUI Design

This app includes **two beautiful interfaces**, VueTorrent by default:

| Interface | Features |
|-----------|----------|
| **VueTorrent** ✨ | Modern UI, responsive design, Vue 3 + Vuetify 3, multi-language (Recommended) |
| **qBittorrent Native** | Full-featured, lightweight, classic interface |

### UI Switching Methods

This app provides **three ways** to switch interfaces:

#### Method 1: Installation Wizard (Recommended)

During installation, select **Interface Type**:
- VueTorrent (Recommended) - Modern Vue 3 interface
- qBittorrent Native - Classic native interface

#### Method 2: App Settings

Modify in fnOS **App Settings**:
1. Go to App Center
2. Find qBittorrent
3. Click **Settings**
4. Select **Interface Type**: VueTorrent or Native
5. Save and restart the app

#### Method 3: Switch in WebUI

Go to qBittorrent → Settings → Web UI → Uncheck "Use alternative Web UI"

> ⚠️ **Note**: When using native UI, you must **open a new tab** to access settings. Settings changes in fnOS iframe window won't work.

---

## 📦 Installation & Updates

> 📌 **Note**: This app supports **ARM64 and AMD64 architectures**, requires **fnOS v1.1.19+**.

### Manual Installation/Update

1. Open **App Center**
2. Click **Manual Install** in the bottom left
3. Select `qbittorrent-vuetorrent-5.1.4.3-arm64.fpk` file

Or use command line:

```bash
appcenter-cli install-local qbittorrent-vuetorrent-5.1.4.3-arm64.fpk
```

---

## 🏗️ Local Build

### Windows Build

Build using PowerShell on Windows:

```powershell
# 1. Open PowerShell (Run as Administrator)
# 2. Navigate to project directory
cd C:\Path\To\fnos-qbittorrent

# 3. Run build (default arm64)
.\build.ps1

# 4. Or specify parameters
.\build.ps1 -Version 5.1.4.3    # Specify version
.\build.ps1 -Arch amd64         # Specify architecture (arm64 or amd64)
.\build.ps1 -ForceDownload      # Force re-download all files
```

**Build Features:**
- Auto GitHub proxy (hk.gh-proxy.org → ghfast.top)
- qBittorrent binary and VueTorrent UI downloaded via proxy
- fnpack tool direct access (faster for China servers)
- GitHub API direct access (proxy can't handle API correctly)
- Version caching to avoid repeated downloads

### Linux Build

Build using Bash on Linux:

```bash
# 1. Add execute permission
chmod +x build.sh

# 2. Run build (default arm64)
./build.sh

# 3. Or specify parameters
./build.sh --version 5.1.4.3  # Specify version
./build.sh --arch arm64       # Specify architecture (arm64 or amd64)
./build.sh --force            # Force re-download all files
```

### Build Output

| Architecture | Output File |
|--------------|-------------|
| ARM64 | `qbittorrent-vuetorrent-<version>-arm64.fpk` |
| AMD64 | `qbittorrent-vuetorrent-<version>-amd64.fpk` |

---

## 🔄 Upgrade & Data Retention

### Upgrade Data Protection

The app automatically protects your data during upgrades:

1. **Before upgrade**: Automatically backs up data to shared directory
2. **After upgrade**: Automatically restores data from backup
3. **Choice**: Option to "Keep data" or "Delete data" during upgrade

> 📌 **Note**: fnOS cleans data directory during upgrades. The app protects your torrents, RSS subscriptions, and configurations through backup mechanism.

### Uninstall Data Retention

Uninstallation also provides data retention options:

- **Keep data**: Reinstall to restore all data
- **Delete data**: Completely remove all data

> 💡 **Recommendation**: Choose "Keep data" unless necessary, for future recovery.

---

## 💻 System Requirements

| Item | Default |
|------|---------|
| System Version | fnOS v1.1.19+ |
| Access URL | `http://<your_NAS_IP>:<port>` |
| Default Username | `admin` |
| Default Password | `adminadmin` |
| Default Port | `8080` (configurable during installation or in app settings) |

> ⚠️ **Security Tip**: Please change the default password after first login!
> 
> 📌 **Port Modification**: Port can be customized during installation or in app settings. **Do NOT modify port in WebUI**, otherwise fnOS iframe window cannot access the UI.

---

## 📋 Changelog

| Version | Changes |
|---------|---------|
| v5.1.4.3 | Fixed conflict with system download process<br>Download directory configuration required during installation (must exist) |
| v5.1.4.2 | Support interface type selection during installation and app settings (VueTorrent/Native)<br>Port/UI modification in app settings, do NOT modify port in WebUI |
| v5.1.4.1 | Support port modification during installation and app settings (do NOT modify in WebUI)<br>Added update detection (VueTorrent interface auto-detects latest version on GitHub)<br>Run as app user by default |

---

## 🤝 Support & Feedback

- 🐛 [Report Issues](https://github.com/sushazhi/fnos-qbittorrent/issues)
- 💬 [fnOS Forum](https://club.fnnas.com/)
- 📖 [fnOS Developer Docs](https://developer.fnnas.com/)

---

## 📁 Project Structure

### Core Directory Structure

```
fnos-qbittorrent/
├── .github/                # GitHub configuration
│   └── workflows/          # CI/CD workflows
├── app/                    # fnOS application resources
│   ├── bin/                # Build-generated executable files
│   │   └── qbittorrent-nox # qBittorrent daemon
│   └── ui/                 # WebUI resources
│       ├── vuetorrent/     # VueTorrent WebUI
│       ├── config          # App entry configuration
│       ├── images/         # App icons
│       └── update-check.js # VueTorrent update detection script
├── cmd/                    # fnOS lifecycle scripts
│   ├── main                # App lifecycle management (start/stop/restart/status)
│   ├── install_init        # Installation initialization (validate download directory exists)
│   ├── install_callback    # Post-installation configuration (port/UI type/download directory)
│   ├── config_init         # Configuration initialization (read current config)
│   ├── config_callback     # Configuration changes (port/UI type) and restart service
│   ├── upgrade_init        # Pre-upgrade stop service and backup data
│   ├── upgrade_callback    # Post-upgrade restore data, set permissions, start service
│   ├── uninstall_init      # Uninstallation initialization
│   └── uninstall_callback  # Post-uninstallation cleanup
├── config/                 # Configuration files
│   ├── privilege           # Permission configuration
│   └── resource            # Resource mapping configuration
├── wizard/                 # Wizard UI definitions
│   ├── install             # Installation wizard (port/download directory/UI type)
│   ├── config              # Configuration wizard (port/UI type)
│   ├── uninstall           # Uninstallation wizard
│   └── upgrade             # Upgrade wizard
├── docs/                   # Documentation
│   ├── fnOS_Developer_Guide.md  # fnOS Developer Guide
│   ├── fnOS_Tools_Guide.md      # fnOS Tools Guide
│   ├── fnOS_Advanced_Guide.md   # fnOS Advanced Guide
│   └── CI_CD.md                 # CI/CD Documentation
├── build.ps1               # Windows build script
├── build.sh                # Linux build script
├── manifest                # Application manifest file
├── ICON.PNG                # Application icon (64x64)
├── ICON_256.PNG            # Application icon (256x256)
├── LICENSE                 # License file
├── README.md               # Chinese documentation
└── README_EN.md            # English documentation
```

## 📄 License

This project is open source under the [GPL-2.0](LICENSE) license.

**Credits**:
- [qBittorrent](https://www.qbittorrent.org/) - Powerful BitTorrent client
- [VueTorrent](https://github.com/VueTorrent/VueTorrent) - Beautiful qBittorrent WebUI
- [qbittorrent-nox-static](https://userdocs.github.io/qbittorrent-nox-static/) - qBittorrent static compilation guide
- [fnOS](https://www.fnnas.com/) - Excellent Chinese NAS system

