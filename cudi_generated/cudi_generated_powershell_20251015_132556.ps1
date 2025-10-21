# PowerShell Script generiert von CUDI
# Basierend auf: generiere powershell script
# Domain: test
# Erstellt: 2025-10-15 13:25:56

Write-Host "CUDI PowerShell Script gestartet..." -ForegroundColor Green
Write-Host "Nachricht: generiere powershell script" -ForegroundColor Yellow
Write-Host "Domain: test" -ForegroundColor Cyan
Write-Host "Aktuelle Zeit: $(Get-Date)" -ForegroundColor White

# Erstelle Verzeichnis falls nicht vorhanden
if (!(Test-Path "cudi_output")) {
    New-Item -ItemType Directory -Path "cudi_output"
    Write-Host "Verzeichnis 'cudi_output' erstellt" -ForegroundColor Green
}

# Erstelle Ausgabe-Datei
$output = @"
CUDI PowerShell Script Output
Erstellt am: $(Get-Date)
Original-Nachricht: generiere powershell script
Domain: test
"@

$output | Out-File "cudi_output\powershell_output.txt" -Encoding UTF8
Write-Host "Ausgabe in 'cudi_output\powershell_output.txt' gespeichert" -ForegroundColor Green

Write-Host "Script erfolgreich abgeschlossen!" -ForegroundColor Green
