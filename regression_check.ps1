param(
    [string]$OldPath,
    [string]$NewPath
)

$oldLines = Get-Content -LiteralPath $OldPath
$newLines = Get-Content -LiteralPath $NewPath

function Split-Functions($lines) {
    $funcs = @{}
    $currentName = $null
    $buffer = New-Object System.Collections.Generic.List[string]
    $sigPattern = '^[A-Za-z_][A-Za-z0-9_ \*]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*$'

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $isSig = $false
        if ($line -match $sigPattern) {
            # look ahead up to 3 lines for an opening brace (skipping blank lines)
            for ($j = $i + 1; $j -lt [Math]::Min($i + 4, $lines.Count); $j++) {
                $t = $lines[$j].Trim()
                if ($t -eq '') { continue }
                if ($t.StartsWith('{')) { $isSig = $true }
                break
            }
        }
        if ($isSig) {
            if ($currentName) {
                $funcs[$currentName] = $buffer -join "`n"
            }
            $currentName = $matches[1]
            $buffer = New-Object System.Collections.Generic.List[string]
        }
        $buffer.Add($line)
    }
    if ($currentName) {
        $funcs[$currentName] = $buffer -join "`n"
    }
    return $funcs
}

Write-Host "Splitting old file..."
$oldFuncs = Split-Functions $oldLines
Write-Host "Splitting new file..."
$newFuncs = Split-Functions $newLines

Write-Host "Old function count: $($oldFuncs.Count)"
Write-Host "New function count: $($newFuncs.Count)"

$signals = @(
    'WARNING',
    'unaff_',
    'in_stack_',
    'extraout_',
    'in_R',
    'halt_baddata',
    'Could not recover jumptable',
    'unknown_',
    'CONCAT',
    'SUB84',
    'SUB42',
    'SUB21',
    'undefined4',
    'undefined8'
)

function Count-Signals($text) {
    $counts = @{}
    foreach ($s in $signals) {
        $m = [regex]::Matches($text, [regex]::Escape($s))
        $counts[$s] = $m.Count
    }
    return $counts
}

$results = New-Object System.Collections.Generic.List[object]
$onlyInOld = New-Object System.Collections.Generic.List[string]
$onlyInNew = New-Object System.Collections.Generic.List[string]
$changedCount = 0

foreach ($name in $oldFuncs.Keys) {
    if (-not $newFuncs.ContainsKey($name)) { $onlyInOld.Add($name) }
}
foreach ($name in $newFuncs.Keys) {
    if (-not $oldFuncs.ContainsKey($name)) { $onlyInNew.Add($name) }
}

foreach ($name in $newFuncs.Keys) {
    if (-not $oldFuncs.ContainsKey($name)) { continue }
    $oldBody = $oldFuncs[$name]
    $newBody = $newFuncs[$name]
    if ($oldBody -eq $newBody) { continue }
    $changedCount++

    $oldCounts = Count-Signals $oldBody
    $newCounts = Count-Signals $newBody

    $increased = @()
    foreach ($s in $signals) {
        if ($newCounts[$s] -gt $oldCounts[$s]) {
            $increased += "$s`: $($oldCounts[$s]) -> $($newCounts[$s])"
        }
    }

    if ($increased.Count -gt 0) {
        $results.Add([PSCustomObject]@{
            Function = $name
            Increased = ($increased -join '; ')
        })
    }
}

Write-Host "`nFunctions changed (text differs): $changedCount"
Write-Host "Functions only in OLD (renamed away / removed): $($onlyInOld.Count)"
Write-Host "Functions only in NEW (newly named): $($onlyInNew.Count)"

Write-Host "`n=== Functions with NEW/INCREASED warning signals ==="
Write-Host "Count: $($results.Count)`n"
foreach ($r in $results) {
    Write-Host "$($r.Function): $($r.Increased)"
}

$results | Export-Csv -Path "$PSScriptRoot\regression_candidates.csv" -NoTypeInformation
$onlyInOld | Set-Content -Path "$PSScriptRoot\only_in_old.txt"
$onlyInNew | Set-Content -Path "$PSScriptRoot\only_in_new.txt"
Write-Host "`nWritten to $PSScriptRoot\regression_candidates.csv, only_in_old.txt, only_in_new.txt"

# --- extra pass: identify spacebase-warning function ---
$spaceOld = @()
$spaceNew = @()
foreach ($name in $oldFuncs.Keys) { if ($oldFuncs[$name] -match 'Unable to track spacebase') { $spaceOld += $name } }
foreach ($name in $newFuncs.Keys) { if ($newFuncs[$name] -match 'Unable to track spacebase') { $spaceNew += $name } }
$newlySpace = $spaceNew | Where-Object { $spaceOld -notcontains $_ }
$goneSpace = $spaceOld | Where-Object { $spaceNew -notcontains $_ }
Write-Host "`nNewly spacebase-warned: $($newlySpace -join ', ')"
Write-Host "No longer spacebase-warned: $($goneSpace -join ', ')"

Write-Host "`n=== Removing unreachable block delta by function ==="
foreach ($name in $newFuncs.Keys) {
    if (-not $oldFuncs.ContainsKey($name)) { continue }
    $o = ([regex]::Matches($oldFuncs[$name], 'Removing unreachable block')).Count
    $n = ([regex]::Matches($newFuncs[$name], 'Removing unreachable block')).Count
    if ($n -gt $o) { Write-Host "$name : $o -> $n" }
}
