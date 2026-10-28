param([string]$Tag = "run", [int]$TimeoutSec = 900, [int]$Seed = 210921, [int]$Port = 8188)

$ErrorActionPreference = 'Stop'
$base = "http://127.0.0.1:$Port"
$wfPath = 'E:\Codex\ComfyUI_H3\_unlock\comfy_qw21_ab.json'
$logPath = 'E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI (1)\logs\comfyui.log'
$outDir = 'E:\Codex\ComfyUI_H3\_unlock\results'

$wf = Get-Content $wfPath -Raw | ConvertFrom-Json
$wf."5".inputs.seed = $Seed
$logStart = (Get-Item $logPath).Length

$body = @{ prompt = $wf; client_id = 'dsh-ab' } | ConvertTo-Json -Depth 25 -Compress
$resp = Invoke-RestMethod -Uri "$base/prompt" -Method Post -Body $body -ContentType 'application/json'
$promptId = $resp.prompt_id
if (-not $promptId) { $resp | ConvertTo-Json -Depth 10; throw 'no prompt_id returned' }
"submitted prompt_id=$promptId"

$sw = [Diagnostics.Stopwatch]::StartNew()
$samples = New-Object System.Collections.ArrayList
$entry = $null
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Milliseconds 2000
    $h = $null
    try { $h = Invoke-RestMethod "$base/history/$promptId" -TimeoutSec 10 } catch { }
    if ($h -and $h.PSObject.Properties.Name -contains $promptId) {
        $cand = $h.$promptId
        if ($cand.status.status_str -eq 'success' -or $cand.status.status_str -eq 'error') { $entry = $cand; break }
    }
    $s = & nvidia-smi --query-gpu=power.draw,utilization.gpu,temperature.gpu,clocks.current.graphics --format=csv,noheader,nounits 2>$null
    [void]$samples.Add(($s -join ' '))
}
$sw.Stop()
if (-not $entry) { throw "timeout after $($sw.Elapsed.TotalSeconds)s" }

$newLog = Get-Content $logPath -Raw
$newLog = $newLog.Substring([Math]::Min($logStart, $newLog.Length))
$sIt = [regex]::Matches($newLog, '(\d+\.\d+)s/it') | ForEach-Object { [double]$_.Groups[1].Value }
$executed = [regex]::Matches($newLog, 'Prompt executed in ([0-9:]+)') | ForEach-Object { $_.Groups[1].Value }
$quant = ($newLog -match 'Detected mixed precision quantization')
$staged = [regex]::Matches($newLog, '([\d]+)MB Staged') | ForEach-Object { [int]$_.Groups[1].Value }

$pw = @(); $ut = @()
foreach ($s in $samples) { $p = $s -split ','; if ($p.Count -ge 2) { $pw += [double]$p[0].Trim(); $ut += [double]$p[1].Trim() } }
$res = [ordered]@{
    tag            = $Tag
    when           = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    status         = $entry.status.status_str
    wall_seconds   = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    executed       = ($executed -join ', ')
    s_per_it_last  = if ($sIt.Count) { $sIt[-1] } else { $null }
    s_per_it_median= if ($sIt.Count) { ($sIt | Sort-Object)[[int]($sIt.Count / 2)] } else { $null }
    quantization   = $quant
    staged_mb      = ($staged -join ',')
    power_max_w    = if ($pw.Count) { ($pw | Measure-Object -Maximum).Maximum } else { $null }
    power_median_w = if ($pw.Count) { ($pw | Sort-Object)[[int]($pw.Count / 2)] } else { $null }
    util_max_pct   = if ($ut.Count) { ($ut | Measure-Object -Maximum).Maximum } else { $null }
    util_median_pct= if ($ut.Count) { ($ut | Sort-Object)[[int]($ut.Count / 2)] } else { $null }
    samples        = $samples.Count
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$res | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outDir "comfy_$Tag.json") -Encoding UTF8
$res | ConvertTo-Json -Depth 5




