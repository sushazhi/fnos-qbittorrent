# AGENTS.md - Development Guide for Agentic Coding

This document provides guidelines for AI agents working on the qBittorrent for fnOS project.

## Project Overview

- **Type**: fnOS (Feiniu NAS) application package
- **Language**: Shell scripts (Bash) primarily
- **Binary**: Static qBittorrent 5.1.4 (ARM64)
- **License**: GPL-2.0

## Build Commands

```bash
# Full linting (shell, JSON, manifest)
npm run lint

# Individual linters
npm run lint:shell       # ShellCheck validation
npm run lint:json        # JSON validation (python3)
npm run lint:manifest    # Manifest key validation

# Package building
npm run package          # Build for ARM64 (default)
npm run package:x86      # Build for x86_64
npm run package:arm      # Build for ARM64 (explicit)

# Cleanup
npm run clean            # Remove build artifacts (app/src/build)
```

## Code Style Guidelines

### Shell Scripts

- **Always** use `set -e` at the script top
- **Always** use `#!/bin/bash` shebang
- **Prefix** file with comment: `# <filename> - <description in Chinese>`
- **Use** descriptive variable names: `APP_NAME`, `BIN_DIR`, `CONFIG_FILE`
- **Use** uppercase for environment variables: `TRIM_APPDEST`, `TRIM_PKGVAR`
- **Quote** all variable expansions: `"$VAR"` not `$VAR`
- **Use** `2>/dev/null` or `2>&1` for stderr handling
- **Return** 0 for success, 1 for failure
- **Use** `echo "message"` for user output (English for errors, Chinese for info)
- **Functions**: Named with underscores, contain Chinese comments

Example:
```bash
#!/bin/bash
# cmd/main - qBittorrent应用生命周期管理脚本
set -e
APP_NAME="qbittorrent"
CONFIG_FILE="${DATA_DIR}/qBittorrent/config/qBittorrent.conf"
```

### Error Handling

- **Always** check exit codes: `if command; then ...`
- **Never** use empty catch blocks
- **Use** descriptive error messages in English
- **Provide** helpful context in error output
- **Use** proper return codes in functions

### JSON Configuration

- **Validate** with `python3 -m json.tool`
- **Use** consistent indentation (2 spaces)
- **No** trailing commas
- **Valid** JSON only (no comments in config files)

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Shell scripts | lowercase with underscores | `install_init`, `config_callback` |
| Functions | lowercase with underscores | `start()`, `stop()` |
| Variables | UPPERCASE with underscores | `DATA_DIR`, `PID_FILE` |
| Constants | UPPERCASE | `WEBUI_PORT=8080` |
| Comments | Chinese for explanations, English for errors | `# 创建必要的目录` |

## Directory Structure

```
qb/
├── cmd/           # Lifecycle scripts (main, install, upgrade, etc.)
├── wizard/        # Installation/uninstallation wizards
├── config/        # JSON configuration files
├── ui/            # VueTorrent web UI (Vue.js)
├── manifest       # Package metadata (no extension)
├── package.json   # npm scripts and metadata
└── diagnose.sh    # Diagnostic script for troubleshooting
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

## Common Patterns

```bash
# Process check with PID file
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "${APP_NAME} is running (PID: $PID)"
        return 0
    fi
fi

# Graceful shutdown with timeout
TIMEOUT=30
while ps -p "$PID" > /dev/null 2>&1 && [ $TIMEOUT -gt 0 ]; do
    sleep 1
    TIMEOUT=$((TIMEOUT - 1))
done

# CLI args with case statement
case "$1" in
    start|stop|restart|status) $1 ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
```

## Testing

No automated test framework exists. Manual testing: `npm run lint` (runs shellcheck, json validation, manifest checks).

## Key Files Reference

| File | Purpose |
|------|---------|
| `cmd/main` | Start/stop/restart/status control |
| `cmd/install_init` | Installation initialization |
| `cmd/install_callback` | Post-install actions |
| `cmd/uninstall_init` | Uninstall initialization |
| `cmd/config_callback` | Configuration changes |
| `manifest` | Package metadata (key-value format) |
| `config/privilege` | App privilege configuration |
| `config/resource` | App resource configuration |
| `diagnose.sh` | Diagnostic script for troubleshooting |

## Important Notes

- **No test framework**: Run `npm run lint` before committing
- **Static binary**: qBittorrent-nox pre-compiled, no LD_LIBRARY_PATH needed
- **WebUI dual-mode**: VueTorrent (default) and native UI, switchable via config
- **ARM64 only**: Currently ARM64 only
- **Port 8080**: Hardcoded, not configurable at runtime
- **Config location**: `${TRIM_PKGVAR}/qBittorrent/config/qBittorrent.conf`
