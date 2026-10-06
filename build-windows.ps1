$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m PyInstaller --noconfirm --clean windows/SilenceTrim.spec
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
Copy-Item README.md dist/SilenceTrim/README.md
Copy-Item THIRD_PARTY_NOTICES.md dist/SilenceTrim/THIRD_PARTY_NOTICES.md
# Include upstream license texts alongside the dynamically loaded libraries.
$QtPackage = python -c "import pathlib, PySide6; print(pathlib.Path(PySide6.__file__).parent)"
if ($LASTEXITCODE -ne 0) { throw 'Could not locate Qt.' }
$LicenseFiles = Get-ChildItem $QtPackage -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING)' }
New-Item -ItemType Directory -Force dist/SilenceTrim/licenses | Out-Null
Copy-Item third_party/licenses/* dist/SilenceTrim/licenses/
foreach ($License in $LicenseFiles) {
    Copy-Item $License.FullName (Join-Path 'dist/SilenceTrim/licenses' $License.Name) -Force
}
Write-Host 'Built: dist/SilenceTrim/SilenceTrim.exe and SilenceTrim-CLI.exe'
