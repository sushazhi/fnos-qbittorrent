# AGENTS.md - Development Guide for Agentic Coding

This document provides guidelines for AI agents working on the qBittorrent for fnOS project.

## Project Overview

- **Type**: fnOS (Feiniu NAS) application package
- **Language**: Shell scripts (Bash) primarily
- **Binary**: Static qBittorrent 5.1.4 (ARM64)
- **License**: GPL-2.0

## Build Commands

```bash
# Full validation (shell, JSON, manifest)
npm run lint

# Individual linters
npm run lint:shell       # ShellCheck validation for all cmd/* and wizard/*
npm run lint:json        # JSON validation (python3 -m json.tool)
npm run lint:manifest    # Manifest key validation (grep-based)

# Package building
npm run package          # Build for ARM64 (default)
npm run package:x86      # Build for x86_64
npm run package:arm      # Build for ARM64 (explicit)

# Cleanup
npm run clean            # Remove build artifacts (app/src/build)
```

**Note**: No automated test framework exists. Use `npm run lint` for validation before committing.

## Code Style Guidelines

### Shell Scripts

| Rule | Requirement |
|------|-------------|
| Shebang | Always `#!/bin/bash` |
| Error handling | Always `set -e` at script top |
| File header | `# <filename> - <description in Chinese>` |
| Variable quoting | Always quote: `"$VAR"` not `$VAR` |
| Return codes | 0 for success, 1 for failure |

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Shell scripts | lowercase with underscores | `install_init`, `config_callback` |
| Functions | lowercase with underscores | `start()`, `stop()` |
| Variables | UPPERCASE with underscores | `DATA_DIR`, `PID_FILE` |
| Constants | UPPERCASE | `WEBUI_PORT=8080` |
| Comments | Chinese for explanations, English for errors | `# 创建必要的目录` |

### Error Handling

- **Always** check exit codes: `if command; then ...`
- **Never** use empty catch blocks
- **Use** descriptive error messages in English
- **Provide** helpful context in error output
- **Use** proper return codes in functions

Example:
```bash
#!/bin/bash
# cmd/main - qBittorrent应用生命周期管理脚本
set -e
APP_NAME="qbittorrent"
CONFIG_FILE="${DATA_DIR}/qBittorrent/config/qBittorrent.conf"
```

### JSON Configuration

- **Validate** with `python3 -m json.tool`
- **Use** consistent indentation (2 spaces)
- **No** trailing commas
- **Valid** JSON only (no comments in config files)

### Manifest File

Key-value format (no extension), validate with `npm run lint:manifest`:
```ini
appname = qbittorrent
version = 5.1.4
display_name = qBittorrent
desc = <b>描述内容</b>
platform = arm
```

## fnOS Environment Variables

Always use fnOS provided environment variables:

| Variable | Purpose |
|----------|---------|
| `TRIM_APPDEST` | Application destination directory |
| `TRIM_PKGETC` | Package etc directory |
| `TRIM_PKGVAR` | Package variable data directory |
| `TRIM_PKGHOME` | Package home directory |
| `TRIM_PKGTMP` | Package temporary directory |
| `TRIM_SERVICE_PORT` | Service port (optional, defaults to 8080) |

## Directory Structure

```
qb/
├── cmd/           # Lifecycle scripts (main, install, upgrade, etc.)
├── wizard/        # Installation/uninstallation wizards
├── config/        # JSON configuration files
│   ├── privilege  # App privilege configuration (JSON)
│   └── resource   # App resource configuration (JSON)
├── ui/            # VueTorrent web UI (Vue.js)
├── manifest       # Package metadata (key-value format, no extension)
├── package.json   # npm scripts and metadata
└── diagnose.sh    # Diagnostic script for troubleshooting
```

## Common Patterns

### Process Check with PID File
```bash
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "${APP_NAME} is running (PID: $PID)"
        return 0
    fi
fi
```

### Graceful Shutdown with Timeout
```bash
TIMEOUT=30
while ps -p "$PID" > /dev/null 2>&1 && [ $TIMEOUT -gt 0 ]; do
    sleep 1
    TIMEOUT=$((TIMEOUT - 1))
done
```

### CLI Arguments with Case Statement
```bash
case "$1" in
    start|stop|restart|status) $1 ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
```

### Stderr Handling
```bash
# Redirect stderr to null
command 2>/dev/null

# Redirect both stdout and stderr
command > /dev/null 2>&1
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `cmd/main` | Start/stop/restart/status control |
| `cmd/install_init` | Installation initialization |
| `cmd/install_callback` | Post-install actions |
| `cmd/uninstall_init` | Uninstall initialization |
| `cmd/config_callback` | Configuration changes |
| `manifest` | Package metadata (key-value format) |
| `config/privilege` | App privilege configuration (JSON) |
| `config/resource` | App resource configuration (JSON) |
| `diagnose.sh` | Diagnostic script for troubleshooting |

## Important Notes

- **ARM64 only**: Currently ARM64 only (use `npm run package:x86` for x86_64 builds)
- **Port 8080**: Hardcoded, not configurable at runtime
- **WebUI dual-mode**: VueTorrent (default) and native UI, switchable via config
- **Static binary**: qBittorrent-nox pre-compiled, no LD_LIBRARY_PATH needed
- **Config location**: `${TRIM_PKGVAR}/qBittorrent/config/qBittorrent.conf`
- **UI path**: `${TRIM_APPDEST}/ui/vuetorrent` for VueTorrent, `${TRIM_APPDEST}/ui` for native
