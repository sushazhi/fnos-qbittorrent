<#
.SYNOPSIS
  qBittorrent for fnOS Local Build Script

.DESCRIPTION
  Build qBittorrent fnOS package with specified version or from manifest

.PARAMETER Version
  Override version number (e.g., "5.1.4.2")

.PARAMETER ForceDownload
  Force re-download all dependencies (fnpack, VueTorrent, qBittorrent-nox)

.PARAMETER Arch
  Target architecture: arm64 (default) or amd64 (fnOS platform x86 = amd64)

.EXAMPLE
  .\build.ps1
  Build with version from manifest (default arm64)

.EXAMPLE
  .\build.ps1 -Version 5.1.4.2
  Build with specific version

.EXAMPLE
  .\build.ps1 -Arch x86
  Build for x86 architecture

.EXAMPLE
  .\build.ps1 -Version 5.1.4.2 -ForceDownload
  Build with specific version and force re-download all files
#>
param(
    [string]$Version,
    [string]$Arch = "arm64",
    [switch]$ForceDownload
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$MANIFEST_FILE = Join-Path $PROJECT_DIR "manifest"

# Read version from manifest or use command line parameter
if ($Version) {
    $APP_VERSION = $Version.Trim()
    Write-Host "Using version from parameter: $APP_VERSION" -ForegroundColor Cyan
} else {
    $Version = ""
    $lines = Get-Content $MANIFEST_FILE
    foreach ($line in $lines) {
        if ($line -match "^version\s*=\s*(\S+)") {
            $Version = $matches[1].Trim()
            break
        }
    }
    if (-not $Version) {
        Write-Host "ERROR: Cannot read version from manifest" -ForegroundColor Red
        exit 1
    }
    $APP_VERSION = $Version
    Write-Host "Using version from manifest: $APP_VERSION" -ForegroundColor Cyan
}

# Validate architecture
if ($Arch -notin @("arm64", "amd64")) {
    Write-Host "ERROR: Invalid architecture '$Arch'. Must be 'arm64' or 'amd64'" -ForegroundColor Red
    exit 1
}
$ARCH = $Arch
Write-Host "Target architecture: $ARCH" -ForegroundColor Cyan

$BUILD_DIR = Join-Path $PROJECT_DIR ".local-build"
$VERSION_FILE = Join-Path $BUILD_DIR "versions.json"

$FNPACK_URL = "https://static2.fnnas.com/fnpack/fnpack-1.2.3-windows-amd64"
$VUE_TORRENT_API = "https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest"
$QBT_API = "https://api.github.com/repos/userdocs/qbittorrent-nox-static/releases"

# Derive QBT_VER from manifest version (first 3 components)
$verParts = $APP_VERSION -split '\.'
$QBT_VER = ($verParts[0..2] -join '.')
Write-Host "qBittorrent-nox version: $QBT_VER (from manifest $APP_VERSION)" -ForegroundColor Cyan

# Proxy configuration
$MAIN_PROXY = "https://gh-proxy.com/"
$BINARY_PROXY = "https://ghfast.top/"

# ===== 版本缓存函数（须在使用前定义） =====
function Get-VersionInfo {
    if (Test-Path $VERSION_FILE) {
        try {
            return Get-Content $VERSION_FILE -Raw | ConvertFrom-Json
        } catch {
            return @{}
        }
    }
    return @{}
}

function Save-VersionInfo {
    param($Component, $Version)
    $versions = Get-VersionInfo
    if ($versions -is [System.Management.Automation.PSCustomObject]) {
        $hash = @{}
        $versions.PSObject.Properties | ForEach-Object { $hash[$_.Name] = $_.Value }
        $versions = $hash
    }
    $versions[$Component] = $Version
    $versions | ConvertTo-Json -Depth 10 | Set-Content $VERSION_FILE -Force
}

function Test-VersionMatch {
    param($Component, $ExpectedVersion)
    $versions = Get-VersionInfo
    return ($versions.$Component -eq $ExpectedVersion)
}

# 缓存优先：读取本地已缓存版本号
$cachedVersions = Get-VersionInfo

# ===== qBittorrent-nox release tag：获取网络最新版本并与缓存比对 =====
$cachedQbtTag = $cachedVersions."qbittorrent-nox_$ARCH"
$QBT_RELEASE_TAG = ""
$qbtNetOk = $false

if ($ForceDownload) {
    Write-Host "ForceDownload: 强制重新获取并下载" -ForegroundColor Yellow
} else {
    Write-Host "Fetching latest qBittorrent-nox release for $QBT_VER..." -ForegroundColor Cyan
    try {
        $qbtReleases = Invoke-RestMethod -Uri $QBT_API -UseBasicParsing -TimeoutSec 15
        $qbtPattern = "^release-${QBT_VER}_v"
        $matchingRelease = $qbtReleases | Where-Object { $_.tag_name -match $qbtPattern } | Select-Object -First 1
        if ($matchingRelease) {
            $QBT_RELEASE_TAG = $matchingRelease.tag_name
            $qbtNetOk = $true
        }
    } catch {
        Write-Host "  (网络获取失败，回退缓存)" -ForegroundColor Yellow
    }
}

if ($qbtNetOk) {
    if ($cachedQbtTag -eq $QBT_RELEASE_TAG) {
        Write-Host "qBittorrent-nox: 网络最新($QBT_RELEASE_TAG)与缓存一致，使用缓存" -ForegroundColor Green
    } else {
        if ($cachedQbtTag) {
            Write-Host "qBittorrent-nox: 缓存($cachedQbtTag)已过期，更新为 $QBT_RELEASE_TAG" -ForegroundColor Yellow
        } else {
            Write-Host "qBittorrent-nox: 无缓存，使用 $QBT_RELEASE_TAG" -ForegroundColor Cyan
        }
    }
} elseif ($cachedQbtTag) {
    # 网络失败，回退缓存
    $QBT_RELEASE_TAG = $cachedQbtTag
    Write-Host "qBittorrent-nox: 网络不可用，回退缓存 $QBT_RELEASE_TAG" -ForegroundColor Yellow
} else {
    Write-Host "ERROR: No qBittorrent-nox release found for version $QBT_VER" -ForegroundColor Red
    exit 1
}
Write-Host "  -> qBittorrent-nox release: $QBT_RELEASE_TAG" -ForegroundColor Cyan

# ===== VueTorrent 版本：获取网络最新版本并与缓存比对 =====
$cachedVueVer = $cachedVersions.vuetorrent
$VUE_VER = ""
$vueNetOk = $false

if ($ForceDownload) {
    # 强制模式下直接走网络
} else {
    Write-Host "Fetching latest VueTorrent version..." -ForegroundColor Cyan
    try {
        $vueRelease = Invoke-RestMethod -Uri $VUE_TORRENT_API -UseBasicParsing -TimeoutSec 15
        $VUE_VER = $vueRelease.tag_name -replace '^v', ''
        $vueNetOk = $true
    } catch {
        Write-Host "  (网络获取失败，回退缓存)" -ForegroundColor Yellow
    }
}

if ($vueNetOk) {
    if ($cachedVueVer -eq $VUE_VER) {
        Write-Host "VueTorrent: 网络最新($VUE_VER)与缓存一致，使用缓存" -ForegroundColor Green
    } else {
        if ($cachedVueVer) {
            Write-Host "VueTorrent: 缓存($cachedVueVer)已过期，更新为 $VUE_VER" -ForegroundColor Yellow
        } else {
            Write-Host "VueTorrent: 无缓存，使用 $VUE_VER" -ForegroundColor Cyan
        }
    }
} elseif ($cachedVueVer) {
    $VUE_VER = $cachedVueVer
    Write-Host "VueTorrent: 网络不可用，回退缓存 $VUE_VER" -ForegroundColor Yellow
} else {
    Write-Host "ERROR: Failed to fetch VueTorrent version" -ForegroundColor Red
    exit 1
}
Write-Host "  -> VueTorrent version: $VUE_VER" -ForegroundColor Cyan

function Get-File {
    param($Url, $OutFile, $Description, $Component, $Version, $UseBinaryProxy = $false)

    # Check version match
    if ((-not $ForceDownload) -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
        if (Test-VersionMatch -Component $Component -ExpectedVersion $Version) {
            Write-Host "  Using cached $Description (version $Version)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  Version mismatch for $Description (expected: $Version, cached: $((Get-VersionInfo).$Component)), re-downloading..." -ForegroundColor Yellow
        }
    }

    Write-Host "  Downloading $Description..." -ForegroundColor Yellow

    # Try MAIN_PROXY first
    $proxyUrl = $MAIN_PROXY + $Url
    Write-Host "    Trying $MAIN_PROXY ..." -ForegroundColor Gray
    $p = Start-Process -FilePath "curl" -ArgumentList "-L", "-o", $OutFile, $proxyUrl, "--connect-timeout", "10", "--max-time", "120", "--retry", "2", "--retry-delay", "3", "-s" -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
        Write-Host "  Downloaded $Description (via $MAIN_PROXY)" -ForegroundColor Green
        Save-VersionInfo -Component $Component -Version $Version
        return $true
    }

    # MAIN_PROXY failed, try BINARY_PROXY
    Write-Host "    Trying $BINARY_PROXY ..." -ForegroundColor Gray
    $proxyUrl = $BINARY_PROXY + $Url
    $p = Start-Process -FilePath "curl" -ArgumentList "-L", "-o", $OutFile, $proxyUrl, "--connect-timeout", "10", "--max-time", "120", "--retry", "2", "--retry-delay", "3", "-s" -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
        Write-Host "  Downloaded $Description (via $BINARY_PROXY)" -ForegroundColor Green
        Save-VersionInfo -Component $Component -Version $Version
        return $true
    }

    # Both proxies failed, try direct download
    Write-Host "    Proxies failed, trying direct download..." -ForegroundColor Gray
    $p = Start-Process -FilePath "curl" -ArgumentList "-L", "-o", $OutFile, $Url, "--connect-timeout", "15", "--max-time", "180", "--retry", "2", "--retry-delay", "5", "-s" -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
        Write-Host "  Downloaded $Description (direct)" -ForegroundColor Green
        Save-VersionInfo -Component $Component -Version $Version
        return $true
    }

    Write-Host "  ERROR: Failed to download $Description" -ForegroundColor Red
    return $false
}

function Get-FileDirect {
    param($Url, $OutFile, $Description, $Component, $Version)

    # Check version match
    if ((-not $ForceDownload) -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
        if (Test-VersionMatch -Component $Component -ExpectedVersion $Version) {
            Write-Host "  Using cached $Description (version $Version)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  Version mismatch for $Description (expected: $Version, cached: $((Get-VersionInfo).$Component)), re-downloading..." -ForegroundColor Yellow
        }
    }

    Write-Host "  Downloading $Description..." -ForegroundColor Yellow

    # Try curl first
    $curlPath = (Get-Command curl -ErrorAction SilentlyContinue).Path
    if ($curlPath) {
        $p = Start-Process -FilePath $curlPath -ArgumentList "-L", "-o", $OutFile, $Url, "--connect-timeout", "30", "--max-time", "300", "--retry", "3", "--retry-delay", "5" -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description" -ForegroundColor Green
            Save-VersionInfo -Component $Component -Version $Version
            return $true
        }
    }

    # Fallback to Invoke-WebRequest
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
        if ((Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description" -ForegroundColor Green
            Save-VersionInfo -Component $Component -Version $Version
            return $true
        }
    } catch {
        Write-Host "  ERROR: Failed to download $Description" -ForegroundColor Red
        return $false
    }

    return $false
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  qBittorrent for fnOS - Local Build" -ForegroundColor Cyan
Write-Host "  Version: $APP_VERSION" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "[1/5] Setting up build directory..." -ForegroundColor Yellow
@("app\bin", "app\ui\vuetorrent", "cmd", "config", "wizard") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $BUILD_DIR $_) | Out-Null
}
Write-Host "  Build directory ready" -ForegroundColor Green

Write-Host "[2/5] Copying project files..." -ForegroundColor Yellow
Copy-Item "$PROJECT_DIR\cmd\*" "$BUILD_DIR\cmd\" -Recurse -Force
Copy-Item "$PROJECT_DIR\config\*" "$BUILD_DIR\config\" -Recurse -Force
Copy-Item "$PROJECT_DIR\wizard\*" "$BUILD_DIR\wizard\" -Recurse -Force

# Copy manifest (and update version)
$manifestLines = Get-Content $MANIFEST_FILE -Raw -Encoding UTF8
$manifestLines = $manifestLines -replace "(?m)^version\s*=.*", "version = $APP_VERSION"
[System.IO.File]::WriteAllText("$BUILD_DIR\manifest", $manifestLines, [System.Text.Encoding]::UTF8)
@("ICON.PNG", "ICON_256.PNG") | ForEach-Object {
    if (Test-Path "$PROJECT_DIR\$_") { Copy-Item "$PROJECT_DIR\$_" "$BUILD_DIR\" -Force }
}
if (Test-Path "$PROJECT_DIR\app\ui\config") { Copy-Item "$PROJECT_DIR\app\ui\config" "$BUILD_DIR\app\ui\" -Force }
if (Test-Path "$PROJECT_DIR\app\ui\images") { Copy-Item "$PROJECT_DIR\app\ui\images" "$BUILD_DIR\app\ui\" -Recurse -Force }
if (Test-Path "$PROJECT_DIR\app\ui\index.html") { Copy-Item "$PROJECT_DIR\app\ui\index.html" "$BUILD_DIR\app\ui\" -Force }
Write-Host "  Project files copied" -ForegroundColor Green

Write-Host "[3/5] Preparing qBittorrent-nox..." -ForegroundColor Yellow
$daemonCache = Join-Path $BUILD_DIR "qbittorrent-nox-$ARCH"
$daemonTarget = "$BUILD_DIR\app\bin\qbittorrent-nox"

# Select qBittorrent-nox URL based on architecture
if ($ARCH -eq "arm64") {
    $targetArch = "aarch64"
} elseif ($ARCH -eq "amd64") {
    $targetArch = "x86_64"
} else {
    Write-Host "ERROR: Unsupported architecture $ARCH" -ForegroundColor Red
    exit 1
}

$url = "https://github.com/userdocs/qbittorrent-nox-static/releases/download/${QBT_RELEASE_TAG}/${targetArch}-qbittorrent-nox"
$success = Get-File -Url $url -OutFile $daemonCache -Description "qBittorrent-nox $QBT_RELEASE_TAG ($targetArch)" -Component "qbittorrent-nox_$ARCH" -Version $QBT_RELEASE_TAG -UseBinaryProxy $true
if (-not $success) { Write-Host "  ERROR: Failed to download" -ForegroundColor Red; exit 1 }
Copy-Item $daemonCache $daemonTarget -Force

if (Test-Path "$PROJECT_DIR\app\bin\gateway-proxy.py") {
    Copy-Item "$PROJECT_DIR\app\bin\gateway-proxy.py" "$BUILD_DIR\app\bin\" -Force
}
if (Test-Path "$PROJECT_DIR\app\bin\qbt_password.py") {
    Copy-Item "$PROJECT_DIR\app\bin\qbt_password.py" "$BUILD_DIR\app\bin\" -Force
}

Write-Host "[4/5] Preparing VueTorrent WebUI..." -ForegroundColor Yellow
$vueCache = Join-Path $BUILD_DIR "vuetorrent.zip"
$vueTargetDir = "$BUILD_DIR\app\ui\vuetorrent"

# Check if already extracted and version matches
$vueReady = (Test-Path "$vueTargetDir\public\index.html") -and (Test-VersionMatch -Component "vuetorrent" -ExpectedVersion $VUE_VER)

if ((-not $ForceDownload) -and $vueReady) {
    Write-Host "  Using cached VueTorrent $VUE_VER" -ForegroundColor Green
} else {
    # Download if needed
    $url = "https://github.com/VueTorrent/VueTorrent/releases/download/v$VUE_VER/vuetorrent.zip"
    if (-not (Get-File -Url $url -OutFile $vueCache -Description "VueTorrent $VUE_VER" -Component "vuetorrent" -Version $VUE_VER -UseBinaryProxy $true)) { exit 1 }

    Write-Host "  Extracting VueTorrent..." -ForegroundColor Gray
    $tempDir = Join-Path $BUILD_DIR "temp-vuetorrent"
    Expand-Archive -Path $vueCache -DestinationPath $tempDir -Force

    # Clean and create target
    if (Test-Path $vueTargetDir) { Remove-Item $vueTargetDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $vueTargetDir | Out-Null

    # Zip structure: vuetorrent/{public, version.txt} -> app/ui/vuetorrent/
    $src = "$tempDir\vuetorrent"
    if (Test-Path "$src\public") { Copy-Item "$src\*" $vueTargetDir -Recurse -Force }
    Remove-Item $tempDir -Recurse -Force

    if (Test-Path "$vueTargetDir\public\screenshots") { Remove-Item "$vueTargetDir\public\screenshots" -Recurse -Force }
    Write-Host "  VueTorrent ready" -ForegroundColor Green
}

# Copy update-check.js to VueTorrent public directory (before injection)
$vuePublicDir = "$BUILD_DIR\app\ui\vuetorrent\public"
if (Test-Path "$PROJECT_DIR\app\ui\update-check.js") {
    Copy-Item "$PROJECT_DIR\app\ui\update-check.js" "$vuePublicDir\" -Force
    Write-Host "  update-check.js copied to VueTorrent" -ForegroundColor Green
}
# Also copy to app/ui/ for gateway-proxy.py runtime injection (native WebUI)
Copy-Item "$PROJECT_DIR\app\ui\update-check.js" "$BUILD_DIR\app\ui\" -Force
Write-Host "  update-check.js copied to gateway for native WebUI" -ForegroundColor Green

# Inject update check into WebUIs
Write-Host "[4.5/5] Injecting update check into WebUIs..." -ForegroundColor Yellow

# Prepare injection script
$injectScript = @"
    <script>
        window.QBITTORRENT_APP_VERSION = '$APP_VERSION';
        window.QBITTORRENT_APP_ARCH = '$ARCH';
    </script>
    <script src="update-check.js"></script>
"@

# Inject into VueTorrent
$vueIndexHtml = "$BUILD_DIR\app\ui\vuetorrent\public\index.html"
if (Test-Path $vueIndexHtml) {
    $vueContent = Get-Content $vueIndexHtml -Raw
    # Update version if already exists, or inject new
    if ($vueContent -match "window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'") {
        $vueContent = $vueContent -replace "window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'", "window.QBITTORRENT_APP_VERSION = '$APP_VERSION'"
        # Also update or add arch
        if ($vueContent -match "window\.QBITTORRENT_APP_ARCH\s*=\s*'[^']*'") {
            $vueContent = $vueContent -replace "window\.QBITTORRENT_APP_ARCH\s*=\s*'[^']*'", "window.QBITTORRENT_APP_ARCH = '$ARCH'"
        } else {
            $vueContent = $vueContent -replace "(window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*')", "`$1`n        window.QBITTORRENT_APP_ARCH = '$ARCH'"
        }
        $vueContent | Set-Content $vueIndexHtml -NoNewline -Encoding UTF8
        Write-Host "  Update check version/arch updated to $APP_VERSION/$ARCH" -ForegroundColor Green
    } elseif ($vueContent -match '</body>') {
        $vueContent = $vueContent -replace '</body>', "$injectScript`n</body>"
        $vueContent | Set-Content $vueIndexHtml -NoNewline -Encoding UTF8
        Write-Host "  Update check injected into VueTorrent ($APP_VERSION/$ARCH)" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Could not find </body> in VueTorrent index.html" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Warning: VueTorrent index.html not found" -ForegroundColor Yellow
}

Write-Host "[5/5] Building package..." -ForegroundColor Yellow
$FNPACK_VER = "1.2.1"
$FNPACK_FILE = $FNPACK_URL.Substring($FNPACK_URL.LastIndexOf('/') + 1)
$fnpackPath = Join-Path $BUILD_DIR $FNPACK_FILE
if ((-not $ForceDownload) -and (Test-Path $fnpackPath) -and (Test-VersionMatch -Component "fnpack" -ExpectedVersion $FNPACK_VER)) {
    Write-Host "  Using cached fnpack $FNPACK_VER" -ForegroundColor Green
} else {
    if (-not (Get-FileDirect -Url $FNPACK_URL -OutFile $fnpackPath -Description "fnpack" -Component "fnpack" -Version $FNPACK_VER)) { exit 1 }
}

Remove-Item "$BUILD_DIR\qbittorrent.fpk" -Force -ErrorAction SilentlyContinue
Push-Location $BUILD_DIR
cmd /c "$fnpackPath build" *>&1 | Out-Null
$ok = Test-Path "qbittorrent.fpk"
Pop-Location

if ($ok) {
    Move-Item "$BUILD_DIR\qbittorrent.fpk" "$PROJECT_DIR\qbittorrent-$APP_VERSION-$ARCH.fpk" -Force
    Write-Host "  Build successful!" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "  Output: qbittorrent-$APP_VERSION-$ARCH.fpk" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
