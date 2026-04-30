<#
.SYNOPSIS
  Enumerate Azure AI / Azure OpenAI deployments and flag models that are retiring.

.DESCRIPTION
  Scans one or more Azure subscriptions for Microsoft.CognitiveServices/accounts
  (kind = OpenAI or AIServices) and their /deployments children. For each
  deployment it resolves:
    - deployment name
    - current model name + version
    - SKU / deployment type (Standard / GlobalStandard / ProvisionedManaged / ...)
    - capacity (PTU units when applicable)
    - region, subscription, resource group, environment (from tags)
    - retirement date + recommended replacement (from a lifecycle table)
    - urgency bucket (immediate / high / medium / low) based on days-to-retire

  The output is a CSV that is directly consumable by the Model Upgrade
  Analyzer's Model IQ loader, i.e.:
    model-upgrade-analyzer --repo <path> --modeliq <this-output>.csv

  Retirement data can be supplied via -RetirementDataPath (JSON/CSV). If
  omitted, a built-in default table is used (update it before relying on it).

.PARAMETER SubscriptionId
  One or more subscription IDs. If omitted, subscriptions are auto-discovered
  from -TenantId (when provided) or from the current Az context.

.PARAMETER TenantId
  Optional Microsoft Entra tenant ID. When supplied, the script ensures the
  current Az context is connected to this tenant (running Connect-AzAccount
  -TenantId if needed) and enumerates only the subscriptions that live in it.
  Mutually compatible with -SubscriptionId: if both are given, -SubscriptionId
  wins and -TenantId is only used for connection scoping.

.PARAMETER RetirementDataPath
  Optional path to a JSON or CSV file describing model retirement metadata.
  Schema (JSON): array of { "model": "gpt-4", "retirement_date": "2026-06-30",
  "replacement": "gpt-4o", "notes": "..." }
  CSV: headers = model,retirement_date,replacement,notes

.PARAMETER OutputPath
  Path for the CSV output. Defaults to ./modeliq-retirements.csv

.PARAMETER AsJson
  If set, also write a JSON report next to the CSV.

.PARAMETER DaysAhead
  Upper bound (in days) for "retiring" deployments to include. Default 365.
  Use 0 to include everything, including already-retired models.

.EXAMPLE
  ./scripts/Find-RetiringAzureAIDeployments.ps1

.EXAMPLE
  ./scripts/Find-RetiringAzureAIDeployments.ps1 `
    -SubscriptionId 'aaaa-bbbb' `
    -RetirementDataPath ./data/retirements.json `
    -OutputPath ./reports/modeliq.csv

.EXAMPLE
  # Discover every subscription in a single tenant and scan them all.
  ./scripts/Find-RetiringAzureAIDeployments.ps1 `
    -TenantId '72f988bf-86f1-41af-91ab-2d7cd011db47' `
    -OutputPath ./reports/modeliq.csv

.NOTES
  Requires: Az.Accounts, Az.Resources. Tested with Az 12.x.
#>

[CmdletBinding()]
param(
    [string[]] $SubscriptionId,
    [string]   $TenantId,
    [string]   $RetirementDataPath,
    [string]   $OutputPath = (Join-Path -Path (Get-Location) -ChildPath 'modeliq-retirements.csv'),
    [switch]   $AsJson,
    [int]      $DaysAhead = 365
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

#------------------------------------------------------------------------------
# 1. Prerequisites
#------------------------------------------------------------------------------

function Ensure-AzModule {
    param([string] $Name)
    if (-not (Get-Module -ListAvailable -Name $Name)) {
        throw "Required module '$Name' is not installed. Run: Install-Module $Name -Scope CurrentUser"
    }
    Import-Module $Name -ErrorAction Stop | Out-Null
}

Ensure-AzModule -Name Az.Accounts
Ensure-AzModule -Name Az.Resources

$ctx = Get-AzContext -ErrorAction SilentlyContinue
if (-not $ctx) {
    Write-Host "No Az context found. Running Connect-AzAccount..." -ForegroundColor Yellow
    if ($TenantId) {
        Connect-AzAccount -TenantId $TenantId | Out-Null
    } else {
        Connect-AzAccount | Out-Null
    }
    $ctx = Get-AzContext
} elseif ($TenantId -and $ctx.Tenant.Id -ne $TenantId) {
    Write-Host "Current Az context is on tenant $($ctx.Tenant.Id); reconnecting to $TenantId..." -ForegroundColor Yellow
    Connect-AzAccount -TenantId $TenantId | Out-Null
    $ctx = Get-AzContext
}

#------------------------------------------------------------------------------
# 2. Retirement table
#------------------------------------------------------------------------------

# Built-in defaults. These are conservative placeholders — replace with
# authoritative Model IQ / lifecycle data before treating as ground truth.
$DefaultRetirements = @(
    [pscustomobject]@{ model = 'gpt-35-turbo';        retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';   notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-3.5-turbo';       retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';   notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-35-turbo-16k';    retirement_date = '2026-07-01'; replacement = 'gpt-4o-mini';   notes = 'Upgrade to gpt-4o-mini or gpt-4.1-mini.' }
    [pscustomobject]@{ model = 'gpt-4';               retirement_date = '2026-12-01'; replacement = 'gpt-4o';        notes = 'gpt-4 base retiring; migrate to gpt-4o or gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-32k';           retirement_date = '2026-12-01'; replacement = 'gpt-4o';        notes = 'Larger context covered by gpt-4o (128k) / gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-turbo';         retirement_date = '2026-12-01'; replacement = 'gpt-4o';        notes = 'Plan move to gpt-4o or gpt-4.1.' }
    [pscustomobject]@{ model = 'gpt-4-0314';          retirement_date = '2025-06-01'; replacement = 'gpt-4o';        notes = 'Dated snapshot already deprecated.' }
    [pscustomobject]@{ model = 'gpt-4-0613';          retirement_date = '2025-06-01'; replacement = 'gpt-4o';        notes = 'Dated snapshot already deprecated.' }
    [pscustomobject]@{ model = 'text-embedding-ada-002'; retirement_date = '2026-10-01'; replacement = 'text-embedding-3-small'; notes = 'Re-embed existing vectors on new model.' }
    [pscustomobject]@{ model = 'text-davinci-003';    retirement_date = '2024-01-04'; replacement = 'gpt-4o-mini';   notes = 'Legacy completion model already retired.' }
    [pscustomobject]@{ model = 'text-davinci-002';    retirement_date = '2024-01-04'; replacement = 'gpt-4o-mini';   notes = 'Legacy completion model already retired.' }
    [pscustomobject]@{ model = 'code-davinci-002';    retirement_date = '2024-01-04'; replacement = 'gpt-4o';        notes = 'Legacy code model already retired.' }
    [pscustomobject]@{ model = 'o1-preview';          retirement_date = '2026-08-01'; replacement = 'o3';            notes = 'Preview reasoning model superseded by o3.' }
    [pscustomobject]@{ model = 'o1-mini';             retirement_date = '2026-08-01'; replacement = 'o3-mini';       notes = 'Move to o3-mini.' }
)

function Load-RetirementTable {
    param([string] $Path)

    if (-not $Path) { return $DefaultRetirements }
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Retirement data file not found: $Path"
    }

    $ext = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    switch ($ext) {
        '.json' { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
        '.csv'  { return Import-Csv -LiteralPath $Path }
        default { throw "Unsupported retirement data format '$ext'. Use .json or .csv." }
    }
}

function Normalize-ModelName {
    param([string] $Name)
    if (-not $Name) { return '' }
    return $Name.ToLowerInvariant().Trim()
}

function Get-RetirementInfo {
    param(
        [Parameter(Mandatory)] $Table,
        [Parameter(Mandatory)] [string] $Model,
        [string] $Version
    )

    $needle = Normalize-ModelName $Model
    $versioned = if ($Version) { Normalize-ModelName "$Model-$Version" } else { '' }

    foreach ($row in $Table) {
        $candidate = Normalize-ModelName $row.model
        if ($candidate -eq $needle -or ($versioned -and $candidate -eq $versioned)) {
            return $row
        }
    }
    return $null
}

#------------------------------------------------------------------------------
# 3. Helpers
#------------------------------------------------------------------------------

function Get-DeploymentType {
    <# Map an Azure OpenAI SKU name to our PTU / Standard / Batch bucket. #>
    param([string] $SkuName)
    if (-not $SkuName) { return 'unknown' }
    $s = $SkuName.ToLowerInvariant()
    if ($s -match 'provisioned') { return 'ptu' }
    if ($s -match 'batch')       { return 'batch' }
    if ($s -match 'standard' -or $s -match 'payasyougo' -or $s -match 'payg') { return 'standard' }
    return 'unknown'
}

function Get-UrgencyBucket {
    param([Nullable[int]] $DaysToRetire)
    if ($null -eq $DaysToRetire) { return 'unknown' }
    if ($DaysToRetire -le 0)   { return 'immediate' }
    if ($DaysToRetire -le 30)  { return 'immediate' }
    if ($DaysToRetire -le 90)  { return 'high' }
    if ($DaysToRetire -le 180) { return 'medium' }
    return 'low'
}

function Get-EnvironmentTag {
    param($Tags)
    if (-not $Tags) { return '' }
    foreach ($key in 'environment','env','Environment','Env') {
        if ($Tags.PSObject.Properties.Name -contains $key) {
            return [string] $Tags.$key
        }
    }
    return ''
}

#------------------------------------------------------------------------------
# 4. Enumerate subscriptions and deployments
#------------------------------------------------------------------------------

$retirementTable = Load-RetirementTable -Path $RetirementDataPath

$targetSubs = if ($SubscriptionId) {
    $SubscriptionId | ForEach-Object {
        if ($TenantId) {
            Get-AzSubscription -SubscriptionId $_ -TenantId $TenantId -ErrorAction SilentlyContinue
        } else {
            Get-AzSubscription -SubscriptionId $_ -ErrorAction SilentlyContinue
        }
    }
} elseif ($TenantId) {
    Write-Host "Discovering subscriptions in tenant $TenantId..." -ForegroundColor Cyan
    $found = @(Get-AzSubscription -TenantId $TenantId -ErrorAction SilentlyContinue 3>$null |
        Where-Object { $_.State -eq 'Enabled' })
    Write-Host "  Found $($found.Count) enabled subscription(s) in tenant." -ForegroundColor Cyan
    $found
} else {
    Get-AzSubscription -ErrorAction SilentlyContinue 3>$null |
        Where-Object { $_.State -eq 'Enabled' }
}

$targetSubs = @($targetSubs | Where-Object { $_ })

if (-not $targetSubs -or $targetSubs.Count -eq 0) {
    if ($TenantId) {
        throw "No accessible subscriptions found in tenant $TenantId."
    }
    throw "No accessible subscriptions found."
}

$results = [System.Collections.Generic.List[object]]::new()
$inventory = [System.Collections.Generic.List[object]]::new()
$today = [DateTime]::UtcNow.Date

foreach ($sub in $targetSubs) {
    Write-Host "Scanning subscription: $($sub.Name) ($($sub.Id))" -ForegroundColor Cyan
    Set-AzContext -SubscriptionId $sub.Id | Out-Null

    # Get all Azure OpenAI / AIServices accounts in the subscription.
    $accounts = @(Get-AzResource -ResourceType 'Microsoft.CognitiveServices/accounts' -ErrorAction SilentlyContinue |
        Where-Object { $_.Kind -in @('OpenAI','AIServices') })
    Write-Host "  Found $($accounts.Count) OpenAI/AIServices account(s)." -ForegroundColor DarkGray

    foreach ($account in $accounts) {
        $apiVersion = '2024-10-01'
        $deploymentsUri = "/subscriptions/$($sub.Id)/resourceGroups/$($account.ResourceGroupName)/providers/Microsoft.CognitiveServices/accounts/$($account.Name)/deployments?api-version=$apiVersion"

        try {
            $resp = Invoke-AzRestMethod -Path $deploymentsUri -Method GET
        } catch {
            Write-Warning "Failed to query deployments for $($account.Name): $($_.Exception.Message)"
            continue
        }

        if ($resp.StatusCode -ge 300) {
            Write-Warning "Non-success status $($resp.StatusCode) for $($account.Name)"
            continue
        }

        $deployments = @(($resp.Content | ConvertFrom-Json).value)
        Write-Host "    $($account.Name) ($($account.Location)): $($deployments.Count) deployment(s)" -ForegroundColor DarkGray
        if (-not $deployments -or $deployments.Count -eq 0) { continue }

        foreach ($dep in $deployments) {
            $model = $dep.properties.model.name
            $modelVersion = $dep.properties.model.version
            $skuName = if ($dep.sku -and $dep.sku.name) { $dep.sku.name } else { $dep.properties.sku.name }
            $capacity = if ($dep.sku -and $dep.sku.capacity) { $dep.sku.capacity } else { $dep.properties.sku.capacity }

            # Always record the inventory row, regardless of retirement match.
            $inventory.Add([pscustomobject]@{
                subscription      = $sub.Id
                subscription_name = $sub.Name
                resource_group    = $account.ResourceGroupName
                account_name      = $account.Name
                account_kind      = $account.Kind
                region            = $account.Location
                deployment_name   = $dep.name
                current_model     = $model
                current_version   = $modelVersion
                sku               = $skuName
                capacity          = $capacity
                deployment_type   = Get-DeploymentType -SkuName $skuName
            }) | Out-Null

            $retire = Get-RetirementInfo -Table $retirementTable -Model $model -Version $modelVersion

            $retirementDate = $null
            $replacement = ''
            $notes = ''
            if ($retire) {
                $retirementDate = [DateTime]::Parse($retire.retirement_date).Date
                $replacement = $retire.replacement
                $notes = $retire.notes
            }

            $daysToRetire = $null
            if ($retirementDate) {
                $daysToRetire = [int]($retirementDate - $today).TotalDays
            }

            # Filter by DaysAhead window (0 = include everything).
            if ($DaysAhead -gt 0 -and $retirementDate) {
                if ($daysToRetire -gt $DaysAhead) { continue }
            }

            # Only emit rows that are actually retiring (have a retirement date).
            if (-not $retirementDate) { continue }

            $row = [pscustomobject]@{
                deployment_name         = $dep.name
                current_model           = $model
                current_version         = $modelVersion
                recommended_replacement = $replacement
                retirement_date         = $retirementDate.ToString('yyyy-MM-dd')
                days_to_retire          = $daysToRetire
                urgency                 = Get-UrgencyBucket -DaysToRetire $daysToRetire
                deployment_type         = Get-DeploymentType -SkuName $skuName
                sku                     = $skuName
                capacity                = $capacity
                region                  = $account.Location
                subscription            = $sub.Id
                subscription_name       = $sub.Name
                resource_group          = $account.ResourceGroupName
                account_name            = $account.Name
                environment             = Get-EnvironmentTag -Tags $account.Tags
                notes                   = $notes
            }
            $results.Add($row) | Out-Null
        }
    }
}

#------------------------------------------------------------------------------
# 5. Output
#------------------------------------------------------------------------------

$outDir = Split-Path -Parent $OutputPath
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

# Always write the full inventory (every AOAI/AIServices deployment we saw).
if ($inventory.Count -gt 0) {
    $invPath = Join-Path -Path $outDir -ChildPath ('aoai-inventory' + [System.IO.Path]::GetExtension($OutputPath))
    $inventory | Sort-Object subscription_name, account_name, deployment_name |
        Export-Csv -LiteralPath $invPath -NoTypeInformation -Encoding UTF8
    Write-Host ""
    Write-Host "Inventory: $($inventory.Count) deployment(s) across $($targetSubs.Count) subscription(s) -> $invPath" -ForegroundColor Green
    $inventory |
        Group-Object current_model |
        Select-Object @{n='model';e={$_.Name}}, @{n='count';e={$_.Count}} |
        Sort-Object count -Descending |
        Format-Table -AutoSize | Out-String | Write-Host
} else {
    Write-Host ""
    Write-Host "Inventory: no OpenAI / AIServices deployments found in the scanned subscription(s)." -ForegroundColor Yellow
}

if ($results.Count -eq 0) {
    Write-Host "No retiring deployments matched the lifecycle table." -ForegroundColor Green
    return
}

$results | Sort-Object days_to_retire, urgency, deployment_name |
    Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host "Wrote $($results.Count) rows to $OutputPath" -ForegroundColor Green

if ($AsJson) {
    $jsonPath = [System.IO.Path]::ChangeExtension($OutputPath, '.json')
    $results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    Write-Host "Wrote $jsonPath" -ForegroundColor Green
}

# Summary table on stdout
$summary = $results | Group-Object urgency | Select-Object Name, Count | Sort-Object Name
Write-Host ""
Write-Host "Urgency summary:" -ForegroundColor Cyan
$summary | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "Feed the CSV into the Model Upgrade Analyzer:" -ForegroundColor Cyan
Write-Host "  model-upgrade-analyzer --repo <repo-path> --modeliq `"$OutputPath`"" -ForegroundColor Gray
