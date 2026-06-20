Param()
$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Root = Resolve-Path (Join-Path $Root '..')
$PyDir = Join-Path $Root 'python-backend'
$Venv = Join-Path $Root '.venv'

Write-Host "Creating virtualenv in $Venv"
python -m venv $Venv

Write-Host "Activating virtualenv and installing dependencies"
& "$Venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r (Join-Path $PyDir 'requirements-cpu.txt')

Write-Host "Installing MineForgeAI backend as editable package"
pip install -e $PyDir

Write-Host "Installation complete. Activate the venv with:`n  & .\.venv\Scripts\Activate.ps1`
Run the CLI with:
  mineforge  # or use `node bin/mineforge.js` for the node launcher"
