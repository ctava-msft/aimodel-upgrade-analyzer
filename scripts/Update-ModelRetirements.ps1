<#
.SYNOPSIS
  Build / refresh the model retirement lifecycle table used by
  Find-RetiringAzureAIDeployments.ps1 (and consumable by the Model Upgrade
  Analyzer's --modeliq input).

.DESCRIPTION
  Produces a JSON file with the schema:
    [
      { "model": "gpt-4", "retirement_date": "2026-12-01",
        "replacement": "gpt-4o", "notes": "..." },
      ...
    ]

  Resolution order:
    1. If -Refresh is set, OR the cache file is missing, OR the cache is older
       than -MaxAgeDays, the table is rebuilt.
    2. Otherwise the existing cache file is reused as-is.

  When (re)building, the table is composed from:
    - The built-in seed list ($SeedRetirements) below — authoritative defaults
      that ship with this repo.
    - Optional remote JSON merge source via -SourceUrl. Schema must be the same
      array-of-objects shape. Remote rows OVERRIDE seed rows on matching model
      name (case-insensitive), so you can patch updates without editing the
      script.
    - Optional local JSON merge source via -MergePath. Same precedence rules:
      local merge wins over both seed and remote.

  Final output is sorted by retirement_date then model.

.PARAMETER OutputPath
  Path of the cache file to read/write. Defaults to ./data/retirements.json
  relative to the repo root.

.PARAMETER Refresh
  Force a rebuild even if the cache is fresh.

.PARAMETER MaxAgeDays
  Cache freshness window in days. Default 30. Use 0 to treat any existing
  cache as fresh (only -Refresh forces rebuild).

.PARAMETER SourceUrl
  Optional URL returning a JSON array in the schema described above. Merged
  on top of the built-in seed during rebuild.

.PARAMETER MergePath
  Optional path to a local JSON file (same schema). Merged on top of seed
  and SourceUrl.

.PARAMETER AsCsv
  Also write a sibling .csv file with headers: model,retirement_date,replacement,notes
  (the format Find-RetiringAzureAIDeployments.ps1 -RetirementDataPath accepts).

.EXAMPLE
  ./scripts/Update-ModelRetirements.ps1
  # Uses cache if fresh; otherwise builds from seeds.

.EXAMPLE
  ./scripts/Update-ModelRetirements.ps1 -Refresh -AsCsv

.EXAMPLE
  ./scripts/Update-ModelRetirements.ps1 -Refresh `
    -SourceUrl 'https://example.com/retirements.json' `
    -MergePath ./data/retirements.local.json

.EXAMPLE
  # End-to-end pipeline:
  ./scripts/Update-ModelRetirements.ps1 -Refresh
  ./scripts/Find-RetiringAzureAIDeployments.ps1 `
    -RetirementDataPath ./data/retirements.json `
    -OutputPath ./reports/modeliq.csv
  model-upgrade-analyzer --repo . --modeliq ./reports/modeliq.csv

.NOTES
  No Az modules required. Pure PowerShell + Invoke-RestMethod.
#>

[CmdletBinding()]
param(
    [string] $OutputPath = (Join-Path -Path (Split-Path -Parent $PSScriptRoot) -ChildPath 'data/retirements.json'),
    [switch] $Refresh,
    [int]    $MaxAgeDays = 30,
    [string] $SourceUrl,
    [string] $MergePath,
    [switch] $AsCsv
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

#------------------------------------------------------------------------------
# Seed retirement table (mirrors Find-RetiringAzureAIDeployments.ps1).
# Update this list when authoritative dates shift.
#------------------------------------------------------------------------------
$SeedRetirements = @(
    [pscustomobject]@{ model = 'gpt-35-turbo';           retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';           notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-3.5-turbo';          retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';           notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-35-turbo-16k';       retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';           notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-4';                  retirement_date = '2026-12-01'; replacement = 'gpt-4o';                notes = 'gpt-4 base retiring; migrate to gpt-4o or gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-32k';              retirement_date = '2026-12-01'; replacement = 'gpt-4o';                notes = 'Larger context covered by gpt-4o (128k) / gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-turbo';            retirement_date = '2026-12-01'; replacement = 'gpt-4o';                notes = 'Plan move to gpt-4o or gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-0314';             retirement_date = '2025-06-01'; replacement = 'gpt-4o';                notes = 'Dated snapshot already deprecated.' }
    [pscustomobject]@{ model = 'gpt-4-0613';             retirement_date = '2025-06-01'; replacement = 'gpt-4o';                notes = 'Dated snapshot already deprecated.' }
    [pscustomobject]@{ model = 'text-embedding-ada-002'; retirement_date = '2026-10-01'; replacement = 'text-embedding-3-small'; notes = 'Re-embed existing vectors on new model.' }
    [pscustomobject]@{ model = 'text-davinci-003';       retirement_date = '2024-01-04'; replacement = 'gpt-4o-mini';           notes = 'Legacy completion model already retired.' }
    [pscustomobject]@{ model = 'text-davinci-002';       retirement_date = '2024-01-04'; replacement = 'gpt-4o-mini';           notes = 'Legacy completion model already retired.' }
    [pscustomobject]@{ model = 'code-davinci-002';       retirement_date = '2024-01-04'; replacement = 'gpt-4o';                notes = 'Legacy code model already retired.' }
    [pscustomobject]@{ model = 'o1-preview';             retirement_date = '2026-08-01'; replacement = 'o3';                    notes = 'Preview reasoning model superseded by o3.' }
    [pscustomobject]@{ model = 'o1-mini';                retirement_date = '2026-08-01'; replacement = 'o3-mini';               notes = 'Move to o3-mini.' }
)

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

function Test-CacheFresh {
    param([string] $Path, [int] $MaxAgeDays)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($MaxAgeDays -le 0) { return $true }
    $age = (Get-Date) - (Get-Item -LiteralPath $Path).LastWriteTime
    return ($age.TotalDays -le $MaxAgeDays)
}

function ConvertTo-Row {
    param($Obj)
    if (-not $Obj) { return $null }
    $model = [string]$Obj.model
    if (-not $model) { return $null }
    return [pscustomobject]@{
        model           = $model.Trim()
        retirement_date = [string]$Obj.retirement_date
        replacement     = if ($Obj.PSObject.Properties.Name -contains 'replacement') { [string]$Obj.replacement } else { '' }
        notes           = if ($Obj.PSObject.Properties.Name -contains 'notes')       { [string]$Obj.notes }       else { '' }
    }
}

function Merge-Retirements {
    <#
    Merge $Override into $Base. Match on lower-cased model name; override wins.
    Returns a new ordered list.
    #>
    param(
        [Parameter(Mandatory)] $Base,
        $Override
    )
    $byKey = [ordered]@{}
    foreach ($row in $Base) {
        $r = ConvertTo-Row $row
        if ($r) { $byKey[$r.model.ToLowerInvariant()] = $r }
    }
    if ($Override) {
        foreach ($row in $Override) {
            $r = ConvertTo-Row $row
            if ($r) { $byKey[$r.model.ToLowerInvariant()] = $r }
        }
    }
    return @($byKey.Values)
}

function Get-RemoteRetirements {
    param([string] $Url)
    if (-not $Url) { return @() }
    Write-Host "Fetching remote retirements: $Url" -ForegroundColor Cyan
    try {
        $data = Invoke-RestMethod -Uri $Url -Method GET -TimeoutSec 30
    } catch {
        Write-Warning "Remote fetch failed ($Url): $($_.Exception.Message). Skipping remote merge."
        return @()
    }
    if ($data -is [System.Collections.IEnumerable] -and -not ($data -is [string])) {
        return @($data)
    }
    foreach ($key in 'records','retirements','data','items') {
        if ($data.PSObject.Properties.Name -contains $key -and $data.$key) {
            return @($data.$key)
        }
    }
    Write-Warning "Remote payload shape not recognized; expected JSON array. Skipping."
    return @()
}

function Get-LocalRetirements {
    param([string] $Path)
    if (-not $Path) { return @() }
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "MergePath not found: $Path"
    }
    $text = Get-Content -LiteralPath $Path -Raw
    if (-not $text.Trim()) { return @() }
    $data = $text | ConvertFrom-Json
    if ($data -is [System.Collections.IEnumerable] -and -not ($data -is [string])) {
        return @($data)
    }
    foreach ($key in 'records','retirements','data','items') {
        if ($data.PSObject.Properties.Name -contains $key -and $data.$key) {
            return @($data.$key)
        }
    }
    return @()
}

function Build-Table {
    param(
        [string] $SourceUrl,
        [string] $MergePath
    )
    $remote = Get-RemoteRetirements -Url $SourceUrl
    $local  = Get-LocalRetirements  -Path $MergePath

    $merged = Merge-Retirements -Base $SeedRetirements -Override $remote
    $merged = Merge-Retirements -Base $merged          -Override $local

    return $merged | Sort-Object @{Expression='retirement_date'}, @{Expression='model'}
}

function Write-Table {
    param(
        [Parameter(Mandatory)] $Rows,
        [Parameter(Mandatory)] [string] $Path,
        [switch] $AsCsv
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $Rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Path -Encoding UTF8
    Write-Host "Wrote $($Rows.Count) rows to $Path" -ForegroundColor Green

    if ($AsCsv) {
        $csvPath = [System.IO.Path]::ChangeExtension($Path, '.csv')
        $Rows | Select-Object model, retirement_date, replacement, notes |
            Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8
        Write-Host "Wrote $csvPath" -ForegroundColor Green
    }
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

if (-not $Refresh -and (Test-CacheFresh -Path $OutputPath -MaxAgeDays $MaxAgeDays)) {
    $age = [int]((Get-Date) - (Get-Item -LiteralPath $OutputPath).LastWriteTime).TotalDays
    Write-Host "Using cached retirements: $OutputPath (age: ${age}d, max: ${MaxAgeDays}d)" -ForegroundColor Green
    Write-Host "Pass -Refresh to rebuild." -ForegroundColor DarkGray
    return
}

Write-Host "Rebuilding retirement table…" -ForegroundColor Cyan
$rows = Build-Table -SourceUrl $SourceUrl -MergePath $MergePath
Write-Table -Rows $rows -Path $OutputPath -AsCsv:$AsCsv

# Summary on stdout
$today = [DateTime]::UtcNow.Date
$summary = $rows | ForEach-Object {
    $d = $null
    [void][DateTime]::TryParse($_.retirement_date, [ref]$d)
    $days = if ($d) { [int]($d - $today).TotalDays } else { $null }
    [pscustomobject]@{
        model           = $_.model
        retirement_date = $_.retirement_date
        days_to_retire  = $days
        replacement     = $_.replacement
    }
}
Write-Host ""
Write-Host "Retirement table:" -ForegroundColor Cyan
$summary | Sort-Object days_to_retire | Format-Table -AutoSize | Out-String | Write-Host
