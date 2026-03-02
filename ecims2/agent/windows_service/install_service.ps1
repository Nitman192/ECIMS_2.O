param(
  [string]$ServiceName = "ECIMSAgent",
  [string]$DisplayName = "ECIMS Agent",
  [string]$AgentRoot = "C:\ECIMS\agent",
  [string]$ConfigPath = "C:\ECIMS\agent\agent.yaml",
  [string]$LogDir = "C:\ECIMS\logs",
  [string]$RunAsUser = "LocalSystem",
  [string]$RunAsPassword = ""
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path "$AgentRoot\backup" | Out-Null

if (Test-Path $ConfigPath) {
  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  Copy-Item $ConfigPath "$AgentRoot\backup\agent.yaml.$stamp.bak"
}

$entry = Join-Path $AgentRoot "run_agent.ps1"
@"
`$env:PYTHONPATH = "$AgentRoot"
python -m ecims_agent.main --config "$ConfigPath" *>> "$LogDir\agent.log"
"@ | Set-Content -Encoding UTF8 $entry

$binaryPath = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$entry`""

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
  sc.exe delete $ServiceName | Out-Null
  Start-Sleep -Seconds 1
}

if ($RunAsUser -eq "LocalSystem") {
  New-Service -Name $ServiceName -DisplayName $DisplayName -BinaryPathName $binaryPath -StartupType Automatic
} else {
  $secure = ConvertTo-SecureString $RunAsPassword -AsPlainText -Force
  $cred = New-Object System.Management.Automation.PSCredential ($RunAsUser, $secure)
  New-Service -Name $ServiceName -DisplayName $DisplayName -BinaryPathName $binaryPath -StartupType Automatic -Credential $cred
}

Start-Service -Name $ServiceName
Write-Host "Installed and started service $ServiceName"
