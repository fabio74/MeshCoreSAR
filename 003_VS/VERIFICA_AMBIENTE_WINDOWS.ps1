$ErrorActionPreference = "Continue"
Write-Host "=== MeshCore Tracker - verifica ambiente .NET MAUI ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "dotnet --version"
dotnet --version
Write-Host ""
Write-Host "SDK installati:"
dotnet --list-sdks
Write-Host ""
Write-Host "Workload installati:"
dotnet workload list
Write-Host ""
Write-Host "Workload MAUI disponibili:"
dotnet workload search maui
Write-Host ""
Write-Host "Se 'maui-windows' o 'maui' non compare tra i workload installati," -ForegroundColor Yellow
Write-Host "aprire Visual Studio Installer > Modifica e installare il workload .NET MAUI." -ForegroundColor Yellow
Write-Host ""
Read-Host "Premere INVIO per chiudere"
