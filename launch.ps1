# launch.ps1 — start QuantumFintek API + Web in parallel windows
# Usage: .\launch.ps1
# Requires: Python 3.11+, Node 18+, all deps installed

$Root = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuantumFintek — Local Dev Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API  → http://localhost:8000" -ForegroundColor Green
Write-Host "  Web  → http://localhost:3000" -ForegroundColor Green
Write-Host "  Docs → http://localhost:8000/docs" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start API in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; Write-Host 'Starting API...' -ForegroundColor Yellow; python dev_server.py"

# Give API 3s head-start
Start-Sleep 3

# Start Next.js dev server in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\apps\web'; Write-Host 'Starting Web...' -ForegroundColor Yellow; npm run dev"

Write-Host "Both servers launched in separate windows." -ForegroundColor Green
Write-Host "Open http://localhost:3000 in your browser." -ForegroundColor Cyan
Write-Host ""
