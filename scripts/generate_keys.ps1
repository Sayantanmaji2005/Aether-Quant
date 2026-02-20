[CmdletBinding()]
param(
    [ValidateRange(16, 128)]
    [int]$Bytes = 32,
    [switch]$NoAdmin,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-HexKey {
    param(
        [int]$SizeBytes
    )

    $buffer = [byte[]]::new($SizeBytes)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return ([System.BitConverter]::ToString($buffer)).Replace("-", "")
}

$traderKey = New-HexKey -SizeBytes $Bytes
$adminKey = $null
if (-not $NoAdmin) {
    $adminKey = New-HexKey -SizeBytes $Bytes
}

$envLines = [ordered]@{
    AETHERQ_API_KEY = $traderKey
}
if ($adminKey) {
    $envLines["AETHERQ_ADMIN_API_KEY"] = $adminKey
}

if ($Json) {
    $payload = [ordered]@{
        generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        bytes            = $Bytes
        trader_key       = $traderKey
        admin_key        = $adminKey
        env              = $envLines
    }
    $payload | ConvertTo-Json -Depth 4
    return
}

Write-Output "Generated API keys:"
Write-Output "TRADER_KEY=$traderKey"
if ($adminKey) {
    Write-Output "ADMIN_KEY=$adminKey"
}
Write-Output ""
Write-Output "Paste into deployment secrets (.env or host secret manager):"
Write-Output "AETHERQ_API_KEY=$traderKey"
if ($adminKey) {
    Write-Output "AETHERQ_ADMIN_API_KEY=$adminKey"
}
