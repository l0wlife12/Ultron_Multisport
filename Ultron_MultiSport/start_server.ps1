# Serveur HTTP Simple pour CryptoExchange

$port = 8000
$filePath = Join-Path $PSScriptRoot "crypto_exchange.html"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         CRYPTO EXCHANGE - SERVEUR LOCAL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Adresse: http://localhost:$port" -ForegroundColor Green
Write-Host "Fichier: $filePath" -ForegroundColor Green
Write-Host ""
Write-Host "Ouvrez votre navigateur et allez a: http://localhost:$port" -ForegroundColor Yellow
Write-Host ""
Write-Host "Appuyez sur Ctrl+C pour arreter" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$httpListener = New-Object System.Net.HttpListener
$httpListener.Prefixes.Add("http://localhost:$port/")
$httpListener.Start()

Write-Host "Serveur demarre!" -ForegroundColor Green
Write-Host ""

try {
    while ($true) {
        $context = $httpListener.GetContext()
        $request = $context.Request
        $response = $context.Response
        
        $requestPath = $request.Url.LocalPath
        if ($requestPath -eq "/" -or $requestPath -eq "") {
            $requestPath = "/crypto_exchange.html"
        }
        
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] GET $requestPath" -ForegroundColor Gray
        
        try {
            $content = [System.IO.File]::ReadAllBytes($filePath)
            $response.ContentType = "text/html; charset=utf-8"
            $response.ContentLength64 = $content.Length
            $response.OutputStream.Write($content, 0, $content.Length)
            Write-Host "OK 200" -ForegroundColor Green
        }
        catch {
            $response.StatusCode = 404
            Write-Host "Erreur 404" -ForegroundColor Red
        }
        finally {
            $response.OutputStream.Close()
        }
    }
}
catch {
    Write-Host ""
    Write-Host "Serveur arrete" -ForegroundColor Yellow
}
finally {
    $httpListener.Stop()
    $httpListener.Close()
}
