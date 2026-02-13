#!/bin/bash
# build.sh - qBittorrent for fnOS Local Build (Linux)
# Usage: ./build.sh [--force] [--arch <arm64|amd64>] [--version <version>]
# Example: ./build.sh --version 5.1.4.2 --arch arm64

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
FORCE_DOWNLOAD=false
ARCH="arm64"
VERSION=""
for arg in "$@"; do
    case $arg in
        --force)
            FORCE_DOWNLOAD=true
            shift
            ;;
        --arch)
            ARCH="$2"
            shift 2
            ;;
        --arch=*)
            ARCH="${arg#*=}"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --version=*)
            VERSION="${arg#*=}"
            shift
            ;;
    esac
done

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_DIR}/.local-build"
MANIFEST_FILE="${PROJECT_DIR}/manifest"

# Read version from manifest or use command line parameter
if [ -n "$VERSION" ]; then
    APP_VERSION="$VERSION"
    echo -e "${CYAN}Using version from parameter: ${APP_VERSION}${NC}"
else
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo -e "${RED}ERROR: manifest file not found${NC}"
        exit 1
    fi
    APP_VERSION=$(grep "^version\s*=" "$MANIFEST_FILE" | head -1 | sed 's/version\s*=\s*//' | tr -d ' ')
    if [ -z "$APP_VERSION" ]; then
        echo -e "${RED}ERROR: Cannot read version from manifest${NC}"
        exit 1
    fi
    echo -e "${CYAN}Using version from manifest: ${APP_VERSION}${NC}"
fi

# URLs
FNPACK_URL="https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-${ARCH}"
VUE_TORRENT_BASE="https://github.com/VueTorrent/VueTorrent/releases/download"
QBT_SOURCE_URL="https://github.com/qbittorrent/qBittorrent/archive/refs/tags"
QBT_VERSION="5.1.4"
VUE_VERSION="2.31.3"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  qBittorrent for fnOS - Local Build${NC}"
echo -e "${CYAN}  Version: ${APP_VERSION}${NC}"
echo -e "${CYAN}  Architecture: ${ARCH}${NC}"
echo -e "${CYAN}========================================${NC}"

# Download file with proxy fallback
download_file() {
    local url="$1"
    local out_file="$2"
    local description="$3"

    # Check if file already exists
    if [ -f "$out_file" ] && [ -s "$out_file" ]; then
        echo -e "${GREEN}  Using cached ${description}${NC}"
        return 0
    fi

    echo -e "${YELLOW}  Downloading ${description}...${NC}"

    # Try GitHub proxy first
    if [[ "$url" == *"github.com"* ]]; then
        proxy_url="https://hk.gh-proxy.org/${url#https://}"
        if curl -fsSL --connect-timeout 30 --max-time 300 --retry 3 -o "$out_file" "$proxy_url"; then
            if [ -f "$out_file" ] && [ -s "$out_file" ]; then
                echo -e "${GREEN}  Downloaded ${description} (via proxy)${NC}"
                return 0
            fi
        fi
    fi

    # Fallback to direct download
    if curl -fsSL --connect-timeout 30 --max-time 300 --retry 3 -o "$out_file" "$url"; then
        if [ -f "$out_file" ] && [ -s "$out_file" ]; then
            echo -e "${GREEN}  Downloaded ${description}${NC}"
            return 0
        fi
    fi

    echo -e "${RED}  ERROR: Failed to download ${description}${NC}"
    return 1
}

# [1/6] Setting up build directory
echo -e "${YELLOW}[1/6] Setting up build directory...${NC}"
mkdir -p "${BUILD_DIR}/app/bin" "${BUILD_DIR}/app/ui/vuetorrent" "${BUILD_DIR}/app/ui/www"
mkdir -p "${BUILD_DIR}/cmd" "${BUILD_DIR}/config" "${BUILD_DIR}/wizard"
echo -e "${GREEN}  Build directory ready${NC}"

# [2/6] Copying project files
echo -e "${YELLOW}[2/6] Copying project files...${NC}"
cp -r "${PROJECT_DIR}/cmd/"* "${BUILD_DIR}/cmd/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/config/"* "${BUILD_DIR}/config/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/wizard/"* "${BUILD_DIR}/wizard/" 2>/dev/null || true
# Copy manifest (and update version if specified)
sed "s/^version\s*=.*/version = ${APP_VERSION}/" "${PROJECT_DIR}/manifest" > "${BUILD_DIR}/manifest"
cp "${PROJECT_DIR}/LICENSE" "${BUILD_DIR}/" 2>/dev/null || true
cp "${PROJECT_DIR}/ICON.PNG" "${BUILD_DIR}/" 2>/dev/null || true
cp "${PROJECT_DIR}/ICON_256.PNG" "${BUILD_DIR}/" 2>/dev/null || true
if [ -d "${PROJECT_DIR}/app/ui/config" ]; then cp -r "${PROJECT_DIR}/app/ui/config" "${BUILD_DIR}/app/ui/"; fi
if [ -d "${PROJECT_DIR}/app/ui/images" ]; then cp -r "${PROJECT_DIR}/app/ui/images" "${BUILD_DIR}/app/ui/"; fi
echo -e "${GREEN}  Project files copied${NC}"

# [3/6] Preparing qBittorrent-nox
echo -e "${YELLOW}[3/6] Preparing qBittorrent-nox...${NC}"
daemon_cache="${BUILD_DIR}/qbittorrent-nox"
daemon_target="${BUILD_DIR}/app/bin/qbittorrent-nox"

# Map ARCH to binary suffix
case $ARCH in
    arm64)
        binary_arch="aarch64"
        ;;
    amd64)
        binary_arch="x86_64"
        ;;
    *)
        binary_arch="$ARCH"
        ;;
esac

if [ "$FORCE_DOWNLOAD" = false ] && [ -f "$daemon_cache" ] && [ -s "$daemon_cache" ]; then
    echo -e "${GREEN}  Using cached binary${NC}"
    cp "$daemon_cache" "$daemon_target"
else
    url="https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${APP_VERSION}_v2.0.11/${binary_arch}-qbittorrent-nox"
    if ! download_file "$url" "$daemon_cache" "qBittorrent-nox ${APP_VERSION} (${ARCH})"; then
        url="https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${APP_VERSION}_v1.2.20/${binary_arch}-qbittorrent-nox"
        download_file "$url" "$daemon_cache" "qBittorrent-nox ${APP_VERSION} (${ARCH})" || exit 1
    fi
    cp "$daemon_cache" "$daemon_target"
fi

# [4/6] Preparing VueTorrent WebUI
echo -e "${YELLOW}[4/6] Preparing VueTorrent WebUI...${NC}"
vue_cache="${BUILD_DIR}/vuetorrent.zip"
vue_target_dir="${BUILD_DIR}/app/ui/vuetorrent"

vue_ready=false
if [ -f "${vue_target_dir}/public/index.html" ]; then
    vue_ready=true
fi

if [ "$FORCE_DOWNLOAD" = false ] && [ "$vue_ready" = true ]; then
    echo -e "${GREEN}  Using cached VueTorrent${NC}"
else
    if [ ! -f "$vue_cache" ] || [ ! -s "$vue_cache" ]; then
        url="${VUE_TORRENT_BASE}/v${VUE_VERSION}/vuetorrent.zip"
        download_file "$url" "$vue_cache" "VueTorrent ${VUE_VERSION}" || exit 1
    fi

    echo -e "${GRAY}  Extracting VueTorrent...${NC}"
    temp_dir="${BUILD_DIR}/temp-vuetorrent"
    rm -rf "$temp_dir"
    mkdir -p "$temp_dir"
    unzip -q "$vue_cache" -d "$temp_dir"

    rm -rf "$vue_target_dir"
    mkdir -p "$vue_target_dir"

    # Zip structure: vuetorrent/{public, version.txt} -> app/ui/vuetorrent/
    if [ -d "${temp_dir}/vuetorrent/public" ]; then
        cp -r "${temp_dir}/vuetorrent/"* "$vue_target_dir/"
    fi
    rm -rf "$temp_dir"

    if [ -d "${vue_target_dir}/public/screenshots" ]; then
        rm -rf "${vue_target_dir}/public/screenshots"
    fi
    echo -e "${GREEN}  VueTorrent ready${NC}"
fi

# [5/6] Preparing qBittorrent Native WebUI
echo -e "${YELLOW}[5/6] Preparing qBittorrent Native WebUI...${NC}"
native_cache="${BUILD_DIR}/qb-${QBT_VERSION}.zip"
native_target_dir="${BUILD_DIR}/app/ui/www"

native_ready=false
if [ -f "${native_target_dir}/public/index.html" ] || [ -f "${native_target_dir}/.gitignore" ]; then
    native_ready=true
fi

if [ "$FORCE_DOWNLOAD" = false ] && [ "$native_ready" = true ]; then
    echo -e "${GREEN}  Using cached native WebUI${NC}"
else
    if [ ! -f "$native_cache" ] || [ ! -s "$native_cache" ]; then
        url="${QBT_SOURCE_URL}/release-${QBT_VERSION}.zip"
        download_file "$url" "$native_cache" "qBittorrent ${QBT_VERSION} source" || exit 1
    fi

    echo -e "${GRAY}  Extracting native WebUI...${NC}"
    temp_dir="${BUILD_DIR}/temp-qbt"
    rm -rf "$temp_dir"
    mkdir -p "$temp_dir"
    unzip -q "$native_cache" -d "$temp_dir"

    rm -rf "$native_target_dir"
    mkdir -p "$native_target_dir"

    # Extract: qBittorrent-release-VERSION/src/webui/www/* -> app/ui/www/
    if [ -d "${temp_dir}/qBittorrent-release-${QBT_VERSION}/src/webui/www" ]; then
        cp -r "${temp_dir}/qBittorrent-release-${QBT_VERSION}/src/webui/www/"* "$native_target_dir/"
    fi
    rm -rf "$temp_dir"
    echo -e "${GREEN}  Native WebUI ready${NC}"
fi

# [5.5/6] Inject update check into VueTorrent
echo -e "${YELLOW}[5.5/6] Injecting update check into WebUIs...${NC}"

# Copy update-check.js to VueTorrent public directory
vue_public_dir="${BUILD_DIR}/app/ui/vuetorrent/public"
if [ -f "${PROJECT_DIR}/app/ui/update-check.js" ]; then
    cp "${PROJECT_DIR}/app/ui/update-check.js" "$vue_public_dir/"
    echo -e "${GREEN}  update-check.js copied to VueTorrent${NC}"
fi

# Inject script into index.html
vue_index_html="${BUILD_DIR}/app/ui/vuetorrent/public/index.html"
if [ -f "$vue_index_html" ]; then
    # Check if already injected
    if grep -q "QBITTORRENT_APP_VERSION" "$vue_index_html"; then
        # Update version number
        sed -i "s/window\.QBITTORRENT_APP_VERSION = '[^']*'/window.QBITTORRENT_APP_VERSION = '$APP_VERSION'/g" "$vue_index_html"
        echo -e "${GREEN}  Update check version updated to ${APP_VERSION}${NC}"
    else
        # Use awk to insert before </body>
        awk -v ver="$APP_VERSION" '
            /<\/body>/ {
                print "      <script>"
                print "          window.QBITTORRENT_APP_VERSION = '\''" ver "'\'';"
                print "      </script>"
                print "      <script src=\"update-check.js\"></script>"
                print ""
            }
            { print }
        ' "$vue_index_html" > "${vue_index_html}.tmp" && mv "${vue_index_html}.tmp" "$vue_index_html"
        echo -e "${GREEN}  Update check injected into VueTorrent${NC}"
    fi
else
    echo -e "${YELLOW}  Warning: VueTorrent index.html not found${NC}"
fi

# [6/6] Building package
echo -e "${YELLOW}[6/6] Building package...${NC}"
fnpack_file="${FNPACK_URL##*/}"
fnpack_path="${BUILD_DIR}/${fnpack_file}"

if [ "$FORCE_DOWNLOAD" = false ] && [ -f "$fnpack_path" ]; then
    echo -e "${GREEN}  Using cached fnpack${NC}"
else
    download_file "$FNPACK_URL" "$fnpack_path" "fnpack" || exit 1
fi

chmod +x "$fnpack_path"

rm -f "${BUILD_DIR}/qbittorrent.fpk"
cd "$BUILD_DIR"
"./${fnpack_file}" build . > /dev/null 2>&1
build_ok=false
if [ -f "qbittorrent.fpk" ]; then
    build_ok=true
fi
cd "$PROJECT_DIR"

if [ "$build_ok" = true ]; then
    mv "${BUILD_DIR}/qbittorrent.fpk" "${PROJECT_DIR}/qbittorrent-vuetorrent-${APP_VERSION}-${ARCH}.fpk"
    echo -e "${GREEN}  Build successful!${NC}"
else
    echo -e "${RED}  ERROR: Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Complete!${NC}"
echo -e "${GREEN}  Output: qbittorrent-vuetorrent-${APP_VERSION}-${ARCH}.fpk${NC}"
echo -e "${GREEN}========================================${NC}"
