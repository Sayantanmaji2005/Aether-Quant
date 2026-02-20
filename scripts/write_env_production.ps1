[CmdletBinding()]
param(
    [string]$TraderKey,
    [string]$AdminKey,
    [switch]$NoAdmin,
    [switch]$GenerateKeys,
    [ValidateRange(16, 128)]
    [int]$Bytes = 32,
    [string]$OutputPath = ".env.production",
    [switch]$Force
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

if ($GenerateKeys -or [string]::IsNullOrWhiteSpace($TraderKey)) {
    $TraderKey = New-HexKey -SizeBytes $Bytes
}

if ($NoAdmin) {
    $AdminKey = ""
}
elseif ($GenerateKeys -or [string]::IsNullOrWhiteSpace($AdminKey)) {
    $AdminKey = New-HexKey -SizeBytes $Bytes
}

if ([string]::IsNullOrWhiteSpace($TraderKey)) {
    throw "Trader key is required. Pass -TraderKey or use -GenerateKeys."
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$templatePath = Join-Path $root ".env.production.example"
if (-not (Test-Path $templatePath)) {
    throw "Template not found: $templatePath"
}

$content = Get-Content -Raw $templatePath
$content = $content -replace "(?m)^AETHERQ_API_KEY=.*$", "AETHERQ_API_KEY=$TraderKey"
$content = $content -replace "(?m)^AETHERQ_ADMIN_API_KEY=.*$", "AETHERQ_ADMIN_API_KEY=$AdminKey"

$resolvedOutput = $OutputPath
if (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $resolvedOutput = Join-Path (Get-Location) $OutputPath
}

if ((Test-Path $resolvedOutput) -and -not $Force) {
    throw "Output exists: $resolvedOutput. Re-run with -Force to overwrite."
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($resolvedOutput, $content, $utf8NoBom)

Write-Output "Wrote $resolvedOutput"
Write-Output "AETHERQ_API_KEY=$TraderKey"
if ($NoAdmin) {
    Write-Output "AETHERQ_ADMIN_API_KEY="
}
else {
    Write-Output "AETHERQ_ADMIN_API_KEY=$AdminKey"
}
