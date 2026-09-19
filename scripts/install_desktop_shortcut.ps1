#Requires -Version 5.0
<#
.SYNOPSIS
  Cria atalho "IA Financeira" na Area de Trabalho do Windows.

.DESCRIPTION
  Aponta para scripts\launch_ia_financeira.bat com o icone assets\ia_financeira.ico.
  Execute uma vez a partir da raiz do repositorio (ou de qualquer lugar; o script
  resolve o caminho relativo a esta pasta).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Launcher = Join-Path $RepoRoot "scripts\launch_ia_financeira.bat"
$IconPath = Join-Path $RepoRoot "assets\ia_financeira.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "IA Financeira.lnk"

if (-not (Test-Path $Launcher)) {
    throw "Launcher nao encontrado: $Launcher"
}
if (-not (Test-Path $IconPath)) {
    throw "Icone nao encontrado: $IconPath"
}

$Wsh = New-Object -ComObject WScript.Shell
$Shortcut = $Wsh.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $RepoRoot.Path
$Shortcut.WindowStyle = 1
$Shortcut.Description = "IA Financeira Local (Ollama + DuckDuckGo + MT5 dry-run)"
$Shortcut.IconLocation = "$IconPath,0"
$Shortcut.Save()

Write-Host ""
Write-Host "Atalho criado:" -ForegroundColor Green
Write-Host "  $ShortcutPath"
Write-Host ""
Write-Host "Aponta para:"
Write-Host "  $Launcher"
Write-Host "Icone:"
Write-Host "  $IconPath"
Write-Host ""
Write-Host "Onde roda o programa:"
Write-Host "  CLI:  python -m ia_financeira"
Write-Host "  GUI:  python -m ia_financeira.gui   (ou o atalho / .bat)"
Write-Host ""
