# ====== CUDI-Diagnose.ps1 ======
$ErrorActionPreference = "SilentlyContinue"
$diag = New-Object System.Text.StringBuilder
function W($s){ $diag.AppendLine($s) | Out-Null; Write-Host $s }

# === KONFIG: Bitte anpassen ===
$ToolPingUrl   = $env:CUDI_PING_URL    # z.B. http://localhost:8000/ping
$ToolSearchUrl = $env:CUDI_SEARCH_URL  # z.B. http://localhost:8000/search?q=
$ConfigPath    = ".\cudi.tools.json"   # Toolschema-Datei (falls vorhanden)

W "== CUDI DIAG = $(Get-Date -Format o)"
W "PWD: $(Get-Location)"
W "User: $env:USERNAME | Host: $env:COMPUTERNAME"
W "PS: $($PSVersionTable.PSVersion)"
W "Node: $(node -v) | NPM: $(npm -v)"
W "Python: $(python --version)"
W "Git: $(git --version)"

# Env (Secrets maskieren)
$mask = { param($v) if([string]::IsNullOrWhiteSpace($v)){return ""} return ($v.Substring(0,[Math]::Min(6,$v.Length)) + "***") }
W "ENV:CUDI_ENV=$env:CUDI_ENV"
W "ENV:CUDI_API_KEY=$(& $mask $env:CUDI_API_KEY)"
W "ENV:CUDI_LOG_LEVEL=$env:CUDI_LOG_LEVEL"

# Schreibrechte
$tmpFile = ".\_cudi_write_test.txt"
"ok" | Out-File $tmpFile -Encoding utf8
if(Test-Path $tmpFile){ W "WRITE: OK ($tmpFile)"; Remove-Item $tmpFile -Force } else { W "WRITE: FAIL (kein Schreibrecht)" }

# Ports
W "PORTS (LISTEN):"
(netstat -ano | Select-String "LISTENING") | Select-Object -First 20 | ForEach-Object { W $_.ToString() }

# Toolschema laden
if (Test-Path $ConfigPath) {
  W "TOOLS: Lade $ConfigPath"
  try {
    $json = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    foreach($t in $json.tools){
      $name=$t.name; $url=$t.url
      W " - $name @ $url"
    }
  } catch { W "TOOLS: JSON-Fehler in $ConfigPath → $_" }
} else { W "TOOLS: $ConfigPath nicht gefunden (überspringe Schema-Check)" }

# HTTP-PING
function TryGet($url){
  try{
    $sw=[System.Diagnostics.Stopwatch]::StartNew()
    $resp=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
    $sw.Stop()
    return @{ ok=$true; code=$resp.StatusCode; ms=$sw.ElapsedMilliseconds; body=$resp.Content.Substring(0,[Math]::Min(200,$resp.Content.Length)) }
  } catch {
    return @{ ok=$false; err=$_.Exception.Message }
  }
}

if($ToolPingUrl){
  $r=TryGet "$ToolPingUrl"
  if($r.ok){ W "PING: OK ($($r.code)) in $($r.ms)ms :: $($r.body)" } else { W "PING: FAIL :: $($r.err)" }
} else { W "PING: URL fehlt (setze CUDI_PING_URL)" }

# SEARCH Dry-Run
if($ToolSearchUrl){
  $r=TryGet "$ToolSearchUrl`cudi+sanity"
  if($r.ok){ W "SEARCH: OK ($($r.code)) in $($r.ms)ms :: $($r.body)" } else { W "SEARCH: FAIL :: $($r.err)" }
} else { W "SEARCH: URL fehlt (setze CUDI_SEARCH_URL)" }

# Fallback-Spuren im Log
$logDir = ".\.cudi\logs"
if(Test-Path $logDir){
  W "LOGS: Prüfe Fallback-Einträge"
  Get-ChildItem $logDir -Recurse -Filter *.log -ErrorAction SilentlyContinue | Select-Object -Last 3 | ForEach-Object {
    W " - $($_.FullName)"
    (Get-Content $_.FullName -Tail 20) | ForEach-Object { W "   $_" }
  }
}else{ W "LOGS: $logDir nicht vorhanden" }

$path = ".\cudi_diag.txt"
$diag.ToString() | Out-File $path -Encoding utf8
W "== DONE -> $path"