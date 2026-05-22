# Load environment variables from config.env
$env_file = "config.env"
Write-Host "Loading from $env_file..."

$TELEGRAM_TOKEN = ""
$TELEGRAM_CHAT_VIP = ""

if (Test-Path $env_file) {
    $content = Get-Content $env_file | Where-Object { $_ -match "=" }
    foreach ($line in $content) {
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"')
            
            if ($key -eq "TELEGRAM_BOT_TOKEN") {
                $TELEGRAM_TOKEN = $value
            }
            elseif ($key -eq "TELEGRAM_CHAT_ID_VIP") {
                $TELEGRAM_CHAT_VIP = $value
            }
        }
    }
}

Write-Host "Token: $(if ($TELEGRAM_TOKEN) { 'LOADED' } else { 'MISSING' })"
Write-Host "Chat VIP: $(if ($TELEGRAM_CHAT_VIP) { 'LOADED' } else { 'MISSING' })"

if (-not $TELEGRAM_TOKEN -or -not $TELEGRAM_CHAT_VIP) {
    Write-Host "ERROR: Missing credentials"
    exit 1
}

$heure_qc = (Get-Date).ToString("HH:mm")

$msg = "ULTRON VIP TEST`n`n"
$msg += "=== NBA SPREAD (Celtics vs Heat) ===`n"
$msg += "ML: Celtics -200`n"
$msg += "SPREAD: Celtics -3.5 @ -110`n"
$msg += "Confidence: 74/100 (ATS 8/10 | Net +5.2)`n`n"

$msg += "=== NHL PUCK LINE (Hurricanes vs Rangers) ===`n"
$msg += "ML: Hurricanes -110`n"
$msg += "PUCK LINE: Hurricanes -1.5 @ -110`n"
$msg += "Confidence: 72/100 (ATS 7/10 | Goalie Anderson SV 0.918)`n`n"

$msg += "=== MLB RUNLINE (Dodgers vs Padres) ===`n"
$msg += "ML: Dodgers -140`n"
$msg += "RUNLINE: Dodgers -1.5 @ -115`n"
$msg += "Confidence: 70/100 (ATS 6/10 | Pitcher ERA 3.24)`n`n"

$msg += "All enrichments deployed today:`n"
$msg += "- NBA Spread: ATS, Net Rating, B2B detection`n"
$msg += "- NHL Puckline: ATS, Goalie SV%, Road trip`n"
$msg += "- MLB Runline: ATS, Pitcher ERA, Sharp money"

Write-Host "Sending to Telegram..."

$url = "https://api.telegram.org/bot$TELEGRAM_TOKEN/sendMessage"
$payload = @{
    chat_id = $TELEGRAM_CHAT_VIP
    text = $msg
    parse_mode = "HTML"
} | ConvertTo-Json

try {
    Write-Host "URL: $url"
    $response = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $payload -TimeoutSec 5
    Write-Host "SUCCESS: Message sent!" -ForegroundColor Green
    Write-Host "Response: $($response | ConvertTo-Json)"
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host $_.Exception
}
