# build.ps1 - qBittorrent for fnOS Local Build
param(
    [switch]$ForceDownload
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$MANIFEST_FILE = Join-Path $PROJECT_DIR "manifest"

# Read version from manifest
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
$ARCH = "arm64"
$BUILD_DIR = Join-Path $PROJECT_DIR ".local-build"

$FNPACK_URL = "https://static2.fnnas.com/fnpack/fnpack-1.2.1-windows-amd64"
$VUE_TORRENT_BASE = "https://github.com/VueTorrent/VueTorrent/releases/download"
$QBT_SOURCE_URL = "https://github.com/qbittorrent/qBittorrent/archive/refs/tags"

function Download-File {
    param($Url, $OutFile, $Description)
    Write-Host "  Downloading $Description..." -ForegroundColor Yellow
    $proxyPattern = "https://hk.gh-proxy.org/{0}"
    $downloadUrl = $Url
    if ($Url -match "github\.com") {
        $downloadUrl = $proxyPattern -f $Url.Replace("https://", "")
    }
    $curlPath = (Get-Command curl -ErrorAction SilentlyContinue).Path
    if ($curlPath) {
        $p = Start-Process -FilePath $curlPath -ArgumentList "-L", "-o", $OutFile, $downloadUrl, "--connect-timeout", "30", "--max-time", "300", "--retry", "3", "--retry-delay", "5" -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description (via proxy)" -ForegroundColor Green
            return $true
        }
    }
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
        if ((Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description (via proxy)" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "  ERROR: Failed to download $Description" -ForegroundColor Red
        return $false
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  qBittorrent for fnOS - Local Build" -ForegroundColor Cyan
Write-Host "  Version: $APP_VERSION" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "[1/6] Setting up build directory..." -ForegroundColor Yellow
@("app\bin", "app\ui\vuetorrent", "app\ui\www", "cmd", "config", "wizard") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $BUILD_DIR $_) | Out-Null
}
Write-Host "  Build directory ready" -ForegroundColor Green

Write-Host "[2/6] Copying project files..." -ForegroundColor Yellow
Copy-Item "$PROJECT_DIR\cmd\*" "$BUILD_DIR\cmd\" -Recurse -Force
Copy-Item "$PROJECT_DIR\config\*" "$BUILD_DIR\config\" -Recurse -Force
Copy-Item "$PROJECT_DIR\wizard\*" "$BUILD_DIR\wizard\" -Recurse -Force
Copy-Item "$PROJECT_DIR\manifest" "$BUILD_DIR\" -Force
@("LICENSE", "ICON.PNG", "ICON_256.PNG") | ForEach-Object {
    if (Test-Path "$PROJECT_DIR\$_") { Copy-Item "$PROJECT_DIR\$_" "$BUILD_DIR\" -Force }
}
if (Test-Path "$PROJECT_DIR\app\ui\config") { Copy-Item "$PROJECT_DIR\app\ui\config" "$BUILD_DIR\app\ui\" -Force }
if (Test-Path "$PROJECT_DIR\app\ui\images") { Copy-Item "$PROJECT_DIR\app\ui\images" "$BUILD_DIR\app\ui\" -Recurse -Force }
Write-Host "  Project files copied" -ForegroundColor Green

Write-Host "[3/6] Preparing qBittorrent-nox..." -ForegroundColor Yellow
$daemonCache = Join-Path $BUILD_DIR "qbittorrent-nox"
$daemonTarget = "$BUILD_DIR\app\bin\qbittorrent-nox"
if ((-not $ForceDownload) -and (Test-Path $daemonCache) -and ((Get-Item $daemonCache).Length -gt 0)) {
    Write-Host "  Using cached binary" -ForegroundColor Green
    Copy-Item $daemonCache $daemonTarget -Force
} else {
    $url = "https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${APP_VERSION}_v2.0.11/aarch64-qbittorrent-nox"
    $success = Download-File -Url $url -OutFile $daemonCache -Description "qBittorrent-nox $APP_VERSION"
    if (-not $success) {
        $url = "https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${APP_VERSION}_v1.2.20/aarch64-qbittorrent-nox"
        $success = Download-File -Url $url -OutFile $daemonCache -Description "qBittorrent-nox $APP_VERSION"
        if (-not $success) { Write-Host "  ERROR: Failed to download" -ForegroundColor Red; exit 1 }
    }
    Copy-Item $daemonCache $daemonTarget -Force
}

Write-Host "[4/6] Preparing VueTorrent WebUI..." -ForegroundColor Yellow
$VUE_VER = "2.31.3"
$vueCache = Join-Path $BUILD_DIR "vuetorrent.zip"
$vueTargetDir = "$BUILD_DIR\app\ui\vuetorrent"

# Check if already extracted (vue has index.html in public/, native has files in public/)
$vueReady = (Test-Path "$vueTargetDir\public\index.html")

if (-not $ForceDownload -and $vueReady) {
    Write-Host "  Using cached VueTorrent" -ForegroundColor Green
} else {
    # Download if needed
    if (-not (Test-Path $vueCache) -or ((Get-Item $vueCache).Length -lt 1000)) {
        $url = "$VUE_TORRENT_BASE/v$VUE_VER/vuetorrent.zip"
        if (-not (Download-File -Url $url -OutFile $vueCache -Description "VueTorrent $VUE_VER")) { exit 1 }
    }

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

Write-Host "[5/6] Preparing qBittorrent Native WebUI..." -ForegroundColor Yellow
$QBT_VER = "5.1.4"
$nativeCache = Join-Path $BUILD_DIR "qb-$QBT_VER.zip"
$nativeTargetDir = "$BUILD_DIR\app\ui\www"

# Check if already extracted (native WebUI has files in public/, vue has public/)
$nativeReady = (Test-Path "$nativeTargetDir\public\index.html") -or (Test-Path "$nativeTargetDir\.gitignore")

if (-not $ForceDownload -and $nativeReady) {
    Write-Host "  Using cached native WebUI" -ForegroundColor Green
} else {
    # Download if needed
    if (-not (Test-Path $nativeCache) -or ((Get-Item $nativeCache).Length -lt 1000)) {
        $url = "$QBT_SOURCE_URL/release-$QBT_VER.zip"
        if (-not (Download-File -Url $url -OutFile $nativeCache -Description "qBittorrent $QBT_VER source")) { exit 1 }
    }

    Write-Host "  Extracting native WebUI..." -ForegroundColor Gray
    $tempDir = Join-Path $BUILD_DIR "temp-qbt"
    Expand-Archive -Path $nativeCache -DestinationPath $tempDir -Force

    # Clean and create target
    if (Test-Path $nativeTargetDir) { Remove-Item $nativeTargetDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $nativeTargetDir | Out-Null

    # Extract: qBittorrent-release-VERSION/src/webui/www/* -> app/ui/www/
    if (Test-Path "$tempDir\qBittorrent-release-$QBT_VER\src\webui\www") {
        Copy-Item "$tempDir\qBittorrent-release-$QBT_VER\src\webui\www\*" $nativeTargetDir -Recurse -Force
    }

    Remove-Item $tempDir -Recurse -Force
    Write-Host "  Native WebUI ready" -ForegroundColor Green
}

# Copy update-check.js to VueTorrent public directory (before injection)
$vuePublicDir = "$BUILD_DIR\app\ui\vuetorrent\public"
if (Test-Path "$PROJECT_DIR\app\ui\update-check.js") {
    Copy-Item "$PROJECT_DIR\app\ui\update-check.js" "$vuePublicDir\" -Force
    Write-Host "  update-check.js copied to VueTorrent" -ForegroundColor Green
}

# Inject update check into WebUIs
Write-Host "[5.5/6] Injecting update check into WebUIs..." -ForegroundColor Yellow

# Prepare injection script
$injectScript = @"
    <script>
        window.QBITTORRENT_APP_VERSION = '$APP_VERSION';
    </script>
    <script src="update-check.js"></script>
"@

# Inject into VueTorrent
$vueIndexHtml = "$BUILD_DIR\app\ui\vuetorrent\public\index.html"
if (Test-Path $vueIndexHtml) {
    $vueContent = Get-Content $vueIndexHtml -Raw
    # Check if already injected
    if ($vueContent -match 'QBITTORRENT_APP_VERSION') {
        Write-Host "  Update check already in VueTorrent (skipping)" -ForegroundColor Gray
    } elseif ($vueContent -match '</body>') {
        $vueContent = $vueContent -replace '</body>', "$injectScript`n</body>"
        $vueContent | Set-Content $vueIndexHtml -NoNewline
        Write-Host "  Update check injected into VueTorrent" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Could not find </body> in VueTorrent index.html" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Warning: VueTorrent index.html not found" -ForegroundColor Yellow
}

Write-Host "[6/6] Building package..." -ForegroundColor Yellow
$FNPACK_FILE = $FNPACK_URL.Substring($FNPACK_URL.LastIndexOf('/') + 1)
$fnpackPath = Join-Path $BUILD_DIR $FNPACK_FILE
if ((-not $ForceDownload) -and (Test-Path $fnpackPath)) {
    Write-Host "  Using cached fnpack" -ForegroundColor Green
} else {
    if (-not (Download-File -Url $FNPACK_URL -OutFile $fnpackPath -Description "fnpack")) { exit 1 }
}

Remove-Item "$BUILD_DIR\qbittorrent.fpk" -Force -ErrorAction SilentlyContinue
Push-Location $BUILD_DIR
cmd /c "$fnpackPath build" *>&1 | Out-Null
$ok = Test-Path "qbittorrent.fpk"
Pop-Location

if ($ok) {
    Move-Item "$BUILD_DIR\qbittorrent.fpk" "$PROJECT_DIR\qbittorrent-vuetorrent-$APP_VERSION-$ARCH.fpk" -Force
    Write-Host "  Build successful!" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "  Output: qbittorrent-vuetorrent-$APP_VERSION-$ARCH.fpk" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
