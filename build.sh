#!/bin/bash
# build.sh - qBittorrent for fnOS Local Build (Linux)
# Usage: ./build.sh [--force] [--arch <arm64|amd64>] [--version <version>]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

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

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${PROJECT_DIR}/.local-build"
MANIFEST_FILE="${PROJECT_DIR}/manifest"
VERSION_FILE="${BUILD_DIR}/versions.json"

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

# Validate architecture
if [ "$ARCH" != "arm64" ] && [ "$ARCH" != "amd64" ]; then
    echo -e "${RED}ERROR: Invalid architecture '$ARCH'. Must be 'arm64' or 'amd64'${NC}"
    exit 1
fi
echo -e "${CYAN}Target architecture: ${ARCH}${NC}"

# URLs
FNPACK_URL="https://static2.fnnas.com/fnpack/fnpack-1.2.1-linux-${ARCH}"
VUE_TORRENT_API="https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest"
QBT_API="https://api.github.com/repos/userdocs/qbittorrent-nox-static/releases"

# Derive QBT_VER from manifest version (first 3 components)
QBT_VER=$(echo "$APP_VERSION" | cut -d. -f1-3)
echo -e "${CYAN}qBittorrent-nox version: ${QBT_VER} (from manifest ${APP_VERSION})${NC}"

# Get latest qBittorrent-nox release matching QBT_VER
echo -e "${CYAN}Fetching latest qBittorrent-nox release for ${QBT_VER}...${NC}"
QBT_RELEASE_TAG=$(curl -fsSL "$QBT_API" | grep '"tag_name"' | sed -E 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' | grep "^release-${QBT_VER}_v" | head -1)
if [ -z "$QBT_RELEASE_TAG" ]; then
    echo -e "${RED}ERROR: No qBittorrent-nox release found for version ${QBT_VER}${NC}"
    exit 1
fi
echo -e "${CYAN}qBittorrent-nox release: ${QBT_RELEASE_TAG}${NC}"

# Proxy configuration
MAIN_PROXY="https://gh-proxy.org/"
BINARY_PROXY="https://ghfast.top/"

# Version cache helpers
get_version_info() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "{}"
    fi
}

save_version_info() {
    local component="$1"
    local version="$2"
    mkdir -p "$(dirname "$VERSION_FILE")"
    if [ ! -f "$VERSION_FILE" ]; then
        echo "{}" > "$VERSION_FILE"
    fi
    local tmp=$(mktemp)
    if command -v jq >/dev/null 2>&1; then
        jq --arg c "$component" --arg v "$version" '. + {($c): $v}' "$VERSION_FILE" > "$tmp" && mv "$tmp" "$VERSION_FILE"
    else
        echo "{\"$component\":\"$version\"}" > "$VERSION_FILE"
    fi
}

test_version_match() {
    local component="$1"
    local expected="$2"
    if [ ! -f "$VERSION_FILE" ]; then
        return 1
    fi
    local cached
    if command -v jq >/dev/null 2>&1; then
        cached=$(jq -r --arg c "$component" '.[$c] // empty' "$VERSION_FILE" 2>/dev/null)
    else
        cached=$(grep "\"$component\"" "$VERSION_FILE" 2>/dev/null | sed 's/.*"'"$component"'":"\([^"]*\)".*/\1/')
    fi
    [ "$cached" = "$expected" ]
}

# Download file with MAIN_PROXY 10s timeout -> BINARY_PROXY fallback
download_file() {
    local url="$1"
    local out_file="$2"
    local description="$3"
    local component="$4"
    local version="$5"

    # Check version match
    if [ "$FORCE_DOWNLOAD" = false ] && [ -f "$out_file" ] && [ -s "$out_file" ]; then
        if test_version_match "$component" "$version"; then
            echo -e "${GREEN}  Using cached ${description} (version ${version})${NC}"
            return 0
        else
            echo -e "${YELLOW}  Version mismatch for ${description}, re-downloading...${NC}"
        fi
    fi

    echo -e "${YELLOW}  Downloading ${description}...${NC}"

    # Try MAIN_PROXY first (10s timeout, no retry)
    if curl -fsSL --connect-timeout 10 --max-time 10 -o "$out_file" "${MAIN_PROXY}${url}" 2>/dev/null; then
        if [ -f "$out_file" ] && [ -s "$out_file" ]; then
            echo -e "${GREEN}  Downloaded ${description} (via ${MAIN_PROXY})${NC}"
            save_version_info "$component" "$version"
            return 0
        fi
    fi

    # MAIN_PROXY timed out, switch to BINARY_PROXY
    echo -e "${YELLOW}  MAIN_PROXY timed out, switching to BINARY_PROXY...${NC}"
    if curl -fsSL --connect-timeout 30 --max-time 300 --retry 3 --retry-delay 5 -o "$out_file" "${BINARY_PROXY}${url}"; then
        if [ -f "$out_file" ] && [ -s "$out_file" ]; then
            echo -e "${GREEN}  Downloaded ${description} (via ${BINARY_PROXY})${NC}"
            save_version_info "$component" "$version"
            return 0
        fi
    fi

    echo -e "${RED}  ERROR: Failed to download ${description}${NC}"
    return 1
}

# Download file directly (no proxy)
download_file_direct() {
    local url="$1"
    local out_file="$2"
    local description="$3"
    local component="$4"
    local version="$5"

    if [ "$FORCE_DOWNLOAD" = false ] && [ -f "$out_file" ] && [ -s "$out_file" ]; then
        if test_version_match "$component" "$version"; then
            echo -e "${GREEN}  Using cached ${description} (version ${version})${NC}"
            return 0
        else
            echo -e "${YELLOW}  Version mismatch for ${description}, re-downloading...${NC}"
        fi
    fi

    echo -e "${YELLOW}  Downloading ${description}...${NC}"
    if curl -fsSL --connect-timeout 30 --max-time 300 --retry 3 --retry-delay 5 -o "$out_file" "$url"; then
        if [ -f "$out_file" ] && [ -s "$out_file" ]; then
            echo -e "${GREEN}  Downloaded ${description}${NC}"
            save_version_info "$component" "$version"
            return 0
        fi
    fi

    echo -e "${RED}  ERROR: Failed to download ${description}${NC}"
    return 1
}

# Get latest VueTorrent version
echo -e "${CYAN}Fetching latest VueTorrent version...${NC}"
VUE_VERSION=$(curl -fsSL "$VUE_TORRENT_API" | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
if [ -z "$VUE_VERSION" ]; then
    echo -e "${RED}ERROR: Failed to fetch VueTorrent version${NC}"
    exit 1
fi
echo -e "${CYAN}VueTorrent version: ${VUE_VERSION}${NC}"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  qBittorrent for fnOS - Local Build${NC}"
echo -e "${CYAN}  Version: ${APP_VERSION}${NC}"
echo -e "${CYAN}========================================${NC}"

# [1/5] Setting up build directory
echo -e "${YELLOW}[1/5] Setting up build directory...${NC}"
mkdir -p "${BUILD_DIR}/app/bin" "${BUILD_DIR}/app/ui/vuetorrent"
mkdir -p "${BUILD_DIR}/cmd" "${BUILD_DIR}/config" "${BUILD_DIR}/wizard"
echo -e "${GREEN}  Build directory ready${NC}"

# [2/5] Copying project files
echo -e "${YELLOW}[2/5] Copying project files...${NC}"
cp -r "${PROJECT_DIR}/cmd/"* "${BUILD_DIR}/cmd/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/config/"* "${BUILD_DIR}/config/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/wizard/"* "${BUILD_DIR}/wizard/" 2>/dev/null || true
sed "s/^version\s*=.*/version = ${APP_VERSION}/" "${PROJECT_DIR}/manifest" > "${BUILD_DIR}/manifest"
cp "${PROJECT_DIR}/LICENSE" "${BUILD_DIR}/" 2>/dev/null || true
cp "${PROJECT_DIR}/ICON.PNG" "${BUILD_DIR}/" 2>/dev/null || true
cp "${PROJECT_DIR}/ICON_256.PNG" "${BUILD_DIR}/" 2>/dev/null || true
if [ -d "${PROJECT_DIR}/app/ui/config" ]; then cp -r "${PROJECT_DIR}/app/ui/config" "${BUILD_DIR}/app/ui/"; fi
if [ -d "${PROJECT_DIR}/app/ui/images" ]; then cp -r "${PROJECT_DIR}/app/ui/images" "${BUILD_DIR}/app/ui/"; fi
if [ -f "${PROJECT_DIR}/app/ui/index.html" ]; then cp "${PROJECT_DIR}/app/ui/index.html" "${BUILD_DIR}/app/ui/"; fi
echo -e "${GREEN}  Project files copied${NC}"

# [3/5] Preparing qBittorrent-nox
echo -e "${YELLOW}[3/5] Preparing qBittorrent-nox...${NC}"
daemon_cache="${BUILD_DIR}/qbittorrent-nox-${ARCH}"
daemon_target="${BUILD_DIR}/app/bin/qbittorrent-nox"

case $ARCH in
    arm64)
        binary_arch="aarch64"
        ;;
    amd64)
        binary_arch="x86_64"
        ;;
    *)
        echo -e "${RED}ERROR: Unsupported architecture ${ARCH}${NC}"
        exit 1
        ;;
esac

url="https://github.com/userdocs/qbittorrent-nox-static/releases/download/${QBT_RELEASE_TAG}/${binary_arch}-qbittorrent-nox"
download_file "$url" "$daemon_cache" "qBittorrent-nox ${QBT_RELEASE_TAG} (${binary_arch})" "qbittorrent-nox_${ARCH}" "$QBT_RELEASE_TAG" || exit 1
cp "$daemon_cache" "$daemon_target"

if [ -f "${PROJECT_DIR}/app/bin/gateway-proxy.py" ]; then
    cp "${PROJECT_DIR}/app/bin/gateway-proxy.py" "${BUILD_DIR}/app/bin/"
fi
if [ -f "${PROJECT_DIR}/app/bin/qbt_password.py" ]; then
    cp "${PROJECT_DIR}/app/bin/qbt_password.py" "${BUILD_DIR}/app/bin/"
fi

# [4/5] Preparing VueTorrent WebUI
echo -e "${YELLOW}[4/5] Preparing VueTorrent WebUI...${NC}"
vue_cache="${BUILD_DIR}/vuetorrent.zip"
vue_target_dir="${BUILD_DIR}/app/ui/vuetorrent"

vue_ready=false
if [ -f "${vue_target_dir}/public/index.html" ] && test_version_match "vuetorrent" "$VUE_VERSION"; then
    vue_ready=true
fi

if [ "$FORCE_DOWNLOAD" = false ] && [ "$vue_ready" = true ]; then
    echo -e "${GREEN}  Using cached VueTorrent ${VUE_VERSION}${NC}"
else
    url="https://github.com/VueTorrent/VueTorrent/releases/download/v${VUE_VERSION}/vuetorrent.zip"
    download_file "$url" "$vue_cache" "VueTorrent ${VUE_VERSION}" "vuetorrent" "$VUE_VERSION" || exit 1

    echo -e "${YELLOW}  Extracting VueTorrent...${NC}"
    temp_dir="${BUILD_DIR}/temp-vuetorrent"
    rm -rf "$temp_dir"
    mkdir -p "$temp_dir"
    unzip -q "$vue_cache" -d "$temp_dir"

    rm -rf "$vue_target_dir"
    mkdir -p "$vue_target_dir"

    if [ -d "${temp_dir}/vuetorrent/public" ]; then
        cp -r "${temp_dir}/vuetorrent/"* "$vue_target_dir/"
    fi
    rm -rf "$temp_dir"

    if [ -d "${vue_target_dir}/public/screenshots" ]; then
        rm -rf "${vue_target_dir}/public/screenshots"
    fi
    echo -e "${GREEN}  VueTorrent ready${NC}"
fi

# Copy update-check.js to VueTorrent public directory
vue_public_dir="${BUILD_DIR}/app/ui/vuetorrent/public"
if [ -f "${PROJECT_DIR}/app/ui/update-check.js" ]; then
    cp "${PROJECT_DIR}/app/ui/update-check.js" "$vue_public_dir/"
    echo -e "${GREEN}  update-check.js copied to VueTorrent${NC}"
fi
# Also copy to app/ui/ for gateway-proxy.py runtime injection (native WebUI)
cp "${PROJECT_DIR}/app/ui/update-check.js" "${BUILD_DIR}/app/ui/"
echo -e "${GREEN}  update-check.js copied to gateway for native WebUI${NC}"

# [4.5/5] Inject update check into VueTorrent
echo -e "${YELLOW}[4.5/5] Injecting update check into WebUIs...${NC}"

vue_index_html="${BUILD_DIR}/app/ui/vuetorrent/public/index.html"
if [ -f "$vue_index_html" ]; then
    if grep -q "QBITTORRENT_APP_VERSION" "$vue_index_html"; then
        sed -i "s/window\.QBITTORRENT_APP_VERSION = '[^']*'/window.QBITTORRENT_APP_VERSION = '$APP_VERSION'/g" "$vue_index_html"
        if grep -q "QBITTORRENT_APP_ARCH" "$vue_index_html"; then
            sed -i "s/window\.QBITTORRENT_APP_ARCH = '[^']*'/window.QBITTORRENT_APP_ARCH = '$ARCH'/g" "$vue_index_html"
        else
            sed -i "/window\.QBITTORRENT_APP_VERSION = '[^']*'/a\\        window.QBITTORRENT_APP_ARCH = '$ARCH'" "$vue_index_html"
        fi
        echo -e "${GREEN}  Update check version/arch updated to ${APP_VERSION}/${ARCH}${NC}"
    else
        awk -v ver="$APP_VERSION" -v arch="$ARCH" '
            /<\/body>/ {
                print "    <script>"
                print "        window.QBITTORRENT_APP_VERSION = '\''" ver "'\'';"
                print "        window.QBITTORRENT_APP_ARCH = '\''" arch "'\'';"
                print "    </script>"
                print "    <script src=\"update-check.js\"></script>"
                print ""
            }
            { print }
        ' "$vue_index_html" > "${vue_index_html}.tmp" && mv "${vue_index_html}.tmp" "$vue_index_html"
        echo -e "${GREEN}  Update check injected into VueTorrent (${APP_VERSION}/${ARCH})${NC}"
    fi
else
    echo -e "${YELLOW}  Warning: VueTorrent index.html not found${NC}"
fi

# [5/5] Building package
echo -e "${YELLOW}[5/5] Building package...${NC}"
FNPACK_VER="1.2.1"
fnpack_file="${FNPACK_URL##*/}"
fnpack_path="${BUILD_DIR}/${fnpack_file}"

if [ "$FORCE_DOWNLOAD" = false ] && [ -f "$fnpack_path" ] && [ -s "$fnpack_path" ] && test_version_match "fnpack" "$FNPACK_VER"; then
    echo -e "${GREEN}  Using cached fnpack ${FNPACK_VER}${NC}"
else
    download_file_direct "$FNPACK_URL" "$fnpack_path" "fnpack" "fnpack" "$FNPACK_VER" || exit 1
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
    mv "${BUILD_DIR}/qbittorrent.fpk" "${PROJECT_DIR}/qbittorrent-${APP_VERSION}-${ARCH}.fpk"
    echo -e "${GREEN}  Build successful!${NC}"
else
    echo -e "${RED}  ERROR: Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Complete!${NC}"
echo -e "${GREEN}  Output: qbittorrent-${APP_VERSION}-${ARCH}.fpk${NC}"
echo -e "${GREEN}========================================${NC}"
