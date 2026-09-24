# Validate Zoom webhook URL through your public tunnel (cloudflared/ngrok).
# Usage (PowerShell):
#   .\scripts\test_zoom_webhook.ps1 https://YOUR-TUNNEL.trycloudflare.com

param(
  [Parameter(Mandatory = $true)]
  [string]$PublicBaseUrl
)

$ErrorActionPreference = "Stop"
$base = $PublicBaseUrl.TrimEnd("/")
$url = "$base/api/zoom/webhook"
$bodyFile = Join-Path $PSScriptRoot "zoom_webhook_validate.json"

Write-Host "POST $url"
curl.exe -s -D - -o "$PSScriptRoot\zoom_webhook_validate.out.json" `
  -X POST $url `
  -H "Content-Type: application/json" `
  --data-binary "@$bodyFile"

Write-Host ""
Write-Host "Response body:"
Get-Content "$PSScriptRoot\zoom_webhook_validate.out.json"
Write-Host ""
Write-Host "Expect HTTP 200 and JSON with plainToken + encryptedToken."
