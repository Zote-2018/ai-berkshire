<#
.SYNOPSIS
卸载 AI-Berkshire-Daily-Monitor 任务。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts/uninstall-daily-monitor.ps1
#>

$taskName = "AI-Berkshire-Daily-Monitor"

Write-Host "卸载任务: $taskName"
schtasks /Delete /TN $taskName /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] 任务已卸载" -ForegroundColor Green
} else {
    Write-Host "[WARN] 卸载失败（任务可能不存在，exit code $LASTEXITCODE）" -ForegroundColor Yellow
}
