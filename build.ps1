<#
.SYNOPSIS
  qBittorrent for fnOS Local Build Script

.DESCRIPTION
  Build qBittorrent fnOS package with specified version or from manifest

.PARAMETER Version
  Override version number (e.g., "5.1.4.2")

.PARAMETER ForceDownload
  Force re-download all dependencies (fnpack, VueTorrent, qBittorrent-nox)

.EXAMPLE
  .\build.ps1
  Build with version from manifest

.EXAMPLE
  .\build.ps1 -Version 5.1.4.2
  Build with specific version

.EXAMPLE
  .\build.ps1 -Version 5.1.4.2 -ForceDownload
  Build with specific version and force re-download all files
#>
param(
    [string]$Version,
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
$ARCH = "arm64"
$BUILD_DIR = Join-Path $PROJECT_DIR ".local-build"
$VERSION_FILE = Join-Path $BUILD_DIR "versions.json"

$FNPACK_URL = "https://static2.fnnas.com/fnpack/fnpack-1.2.1-windows-amd64"
$VUE_TORRENT_BASE = "https://github.com/VueTorrent/VueTorrent/releases/download"
$QBT_SOURCE_URL = "https://github.com/qbittorrent/qBittorrent/archive/refs/tags"
$VUE_VER = "2.31.3"
$QBT_VER = "5.1.4"

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
    # Convert PSCustomObject to Hashtable if needed
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

function Download-File {
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
    $proxyPattern = "https://hk.gh-proxy.org/{0}"
    $downloadUrl = $Url
    if ($Url -match "github\.com") {
        $downloadUrl = $proxyPattern -f $Url.Replace("https://", "")
    }
    
    # Try curl first
    $curlPath = (Get-Command curl -ErrorAction SilentlyContinue).Path
    if ($curlPath) {
        $p = Start-Process -FilePath $curlPath -ArgumentList "-L", "-o", $OutFile, $downloadUrl, "--connect-timeout", "30", "--max-time", "300", "--retry", "3", "--retry-delay", "5" -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description (via proxy)" -ForegroundColor Green
            Save-VersionInfo -Component $Component -Version $Version
            return $true
        }
    }
    
    # Fallback to Invoke-WebRequest
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
        if ((Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 0) {
            Write-Host "  Downloaded $Description (via proxy)" -ForegroundColor Green
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

# Copy manifest (and update version if specified)
$manifestLines = Get-Content $MANIFEST_FILE -Raw -Encoding UTF8
$manifestLines = $manifestLines -replace "(?m)^version\s*=.*", "version = $APP_VERSION"
[System.IO.File]::WriteAllText("$BUILD_DIR\manifest", $manifestLines, [System.Text.Encoding]::UTF8)
@("LICENSE", "ICON.PNG", "ICON_256.PNG") | ForEach-Object {
    if (Test-Path "$PROJECT_DIR\$_") { Copy-Item "$PROJECT_DIR\$_" "$BUILD_DIR\" -Force }
}
if (Test-Path "$PROJECT_DIR\app\ui\config") { Copy-Item "$PROJECT_DIR\app\ui\config" "$BUILD_DIR\app\ui\" -Force }
if (Test-Path "$PROJECT_DIR\app\ui\images") { Copy-Item "$PROJECT_DIR\app\ui\images" "$BUILD_DIR\app\ui\" -Recurse -Force }
if (Test-Path "$PROJECT_DIR\app\ui\index.html") { Copy-Item "$PROJECT_DIR\app\ui\index.html" "$BUILD_DIR\app\ui\" -Force }
Write-Host "  Project files copied" -ForegroundColor Green

Write-Host "[3/5] Preparing qBittorrent-nox..." -ForegroundColor Yellow
$daemonCache = Join-Path $BUILD_DIR "qbittorrent-nox"
$daemonTarget = "$BUILD_DIR\app\bin\qbittorrent-nox"
$url = "https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${QBT_VER}_v2.0.11/aarch64-qbittorrent-nox"
$success = Download-File -Url $url -OutFile $daemonCache -Description "qBittorrent-nox $QBT_VER" -Component "qbittorrent-nox" -Version $QBT_VER
if (-not $success) {
    $url = "https://github.com/userdocs/qbittorrent-nox-static/releases/download/release-${QBT_VER}_v1.2.20/aarch64-qbittorrent-nox"
    $success = Download-File -Url $url -OutFile $daemonCache -Description "qBittorrent-nox $QBT_VER" -Component "qbittorrent-nox" -Version $QBT_VER
    if (-not $success) { Write-Host "  ERROR: Failed to download" -ForegroundColor Red; exit 1 }
}
Copy-Item $daemonCache $daemonTarget -Force

Write-Host "[4/5] Preparing VueTorrent WebUI..." -ForegroundColor Yellow
$vueCache = Join-Path $BUILD_DIR "vuetorrent.zip"
$vueTargetDir = "$BUILD_DIR\app\ui\vuetorrent"

# Check if already extracted and version matches
$vueReady = (Test-Path "$vueTargetDir\public\index.html") -and (Test-VersionMatch -Component "vuetorrent" -ExpectedVersion $VUE_VER)

if ((-not $ForceDownload) -and $vueReady) {
    Write-Host "  Using cached VueTorrent $VUE_VER" -ForegroundColor Green
} else {
    # Download if needed
    $url = "$VUE_TORRENT_BASE/v$VUE_VER/vuetorrent.zip"
    if (-not (Download-File -Url $url -OutFile $vueCache -Description "VueTorrent $VUE_VER" -Component "vuetorrent" -Version $VUE_VER)) { exit 1 }

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

# Inject update check into WebUIs
Write-Host "[4.5/5] Injecting update check into WebUIs..." -ForegroundColor Yellow

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
    # Update version if already exists, or inject new
    if ($vueContent -match "window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'") {
        $vueContent = $vueContent -replace "window\.QBITTORRENT_APP_VERSION\s*=\s*'[^']*'", "window.QBITTORRENT_APP_VERSION = '$APP_VERSION'"
        $vueContent | Set-Content $vueIndexHtml -NoNewline -Encoding UTF8
        Write-Host "  Update check version updated to $APP_VERSION" -ForegroundColor Green
    } elseif ($vueContent -match '</body>') {
        $vueContent = $vueContent -replace '</body>', "$injectScript`n</body>"
        $vueContent | Set-Content $vueIndexHtml -NoNewline -Encoding UTF8
        Write-Host "  Update check injected into VueTorrent" -ForegroundColor Green
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
    if (-not (Download-File -Url $FNPACK_URL -OutFile $fnpackPath -Description "fnpack" -Component "fnpack" -Version $FNPACK_VER)) { exit 1 }
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
