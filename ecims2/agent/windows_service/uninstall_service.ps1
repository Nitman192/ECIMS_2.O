param(
  [string]$ServiceName = "ECIMSAgent"
)

$ErrorActionPreference = "Stop"

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
  if ($svc.Status -ne 'Stopped') {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
  }
  sc.exe delete $ServiceName | Out-Null
  Write-Host "Removed service $ServiceName"
} else {
  Write-Host "Service $ServiceName not found"
}
