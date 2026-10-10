$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment' }
}
$taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $taskPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$fonts = (Join-Path $PSScriptRoot 'src/font_model') + ';font_model'
$license = (Join-Path $PSScriptRoot 'LICENSE') + ';.'
$disclaimer = (Join-Path $PSScriptRoot 'DISCLAIMER.md') + ';.'
& $taskPython -m PyInstaller --noconfirm --onefile --windowed --optimize 2 --exclude-module cv2.gapi --exclude-module cv2.mat_wrapper --exclude-module numpy.testing --exclude-module PIL.ImageQt --exclude-module PIL.ImageShow --name PlateStudio_16K_Fast --distpath dist --workpath work/build --specpath work --add-data $fonts --add-data $license --add-data $disclaimer src/plate_studio.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
Write-Output 'Built dist/PlateStudio_16K_Fast.exe'
