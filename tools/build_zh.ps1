param(
    [switch]$Rebuild,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Version = 'v24.1-zh-HD2'
)
$ErrorActionPreference = 'Stop'
$vbaRoot = Split-Path -Parent $PSScriptRoot
$vbaVswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vbaVisualStudio = & $vbaVswhere -all -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$vbaVisualStudio) { throw 'Visual C++ build tools are missing.' }
$vbaMSBuild = Join-Path $vbaVisualStudio 'MSBuild\Current\Bin\MSBuild.exe'
$vbaProps = Join-Path $vbaRoot 'win32\modern-build.props'
$vbaLog = Join-Path $vbaRoot 'build\logs\source-build.log'
New-Item -ItemType Directory -Force (Split-Path -Parent $vbaLog), (Join-Path $vbaRoot 'win32\userconfig') | Out-Null
if (Test-Path -LiteralPath (Join-Path $vbaRoot '.git')) {
    $vbaCommit = (& git -C $vbaRoot rev-parse --short HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read source revision.' }
} elseif (Test-Path -LiteralPath (Join-Path $vbaRoot 'SOURCE-INFO.json')) {
    $vbaSnapshot = Get-Content -LiteralPath (Join-Path $vbaRoot 'SOURCE-INFO.json') -Raw | ConvertFrom-Json
    $vbaCommit = $vbaSnapshot.source_base_commit.Substring(0, 7)
} else { throw 'Build from a Git checkout or the complete source archive.' }
$vbaRevision = "#define SVN_REV 0`r`n#define SVN_REV_STR `"git$vbaCommit-zh`"`r`n"
$vbaRevisionPath = Join-Path $vbaRoot 'win32\userconfig\svnrev.h'
if (!(Test-Path -LiteralPath $vbaRevisionPath) -or [System.IO.File]::ReadAllText($vbaRevisionPath) -ne $vbaRevision) {
    [System.IO.File]::WriteAllText($vbaRevisionPath, $vbaRevision, [System.Text.Encoding]::ASCII)
}
$vbaTarget = if ($Rebuild) { 'Rebuild' } else { 'Build' }
Push-Location $vbaRoot
try {
    & $vbaMSBuild 'win32\VBA2010.sln' '/p:Configuration=Release' '/p:Platform=Win32' '/p:PlatformToolset=v143' '/p:WindowsTargetPlatformVersion=10.0.22621.0' "/p:ForceImportBeforeCppTargets=$vbaProps" "/t:$vbaTarget" '/v:minimal' '/nologo' '/m:2' '/fl' "/flp:logfile=$vbaLog;verbosity=normal"
    if ($LASTEXITCODE -ne 0) { throw "Build failed. See $vbaLog" }
    & python (Join-Path $PSScriptRoot 'package_release.py') --version $Version
    if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
} finally { Pop-Location }
