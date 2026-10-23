<#
.SYNOPSIS
  ahkgen.ps1 - generate channel-based, Sleep-free AutoHotkey v1 toggle macros from JSON.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File ahkgen.ps1 config.json
  powershell -ExecutionPolicy Bypass -File ahkgen.ps1 config.json -Output out.ahk

  Works on Windows PowerShell 5.1 (built into Windows 10/11) and PowerShell 7+.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Config,
    [Parameter(Position = 1)][string]$Output
)

$ErrorActionPreference = 'Stop'

function Fail($msg) { [Console]::Error.WriteLine("error: $msg"); exit 1 }

function Has($obj, $name) {
    return ($null -ne $obj) -and ($obj.PSObject.Properties.Name -contains $name)
}

function Get-Opt($obj, $name, $default) {
    if (Has $obj $name) { return $obj.$name } else { return $default }
}

# ---------------------------------------------------------------- helpers
function Esc-Send([string]$s) {
    # Escape characters that are special in the AHK v1 legacy Send command.
    return $s.Replace('`', '``').Replace('%', '`%').Replace(',', '`,').Replace(';', '`;')
}

function Key-Token([string]$key, [string]$suffix = '') {
    $inner = $key
    if ($suffix) { $inner = "$key $suffix" }
    return Esc-Send ('{' + $inner + '}')
}

function Ms-Value($v, [string]$where) {
    $isNum = ($v -is [int]) -or ($v -is [long]) -or ($v -is [double]) -or ($v -is [decimal])
    if (-not $isNum -or $v -lt 0) { Fail "${where}: expected a non-negative number of ms, got '$v'" }
    return [int][math]::Truncate([double]$v)
}

# ---------------------------------------------------------------- compile
function Compile-Steps($steps, [string]$where, $jitterDefault) {
    $steps = @($steps)
    if ($steps.Count -eq 0 -or $null -eq $steps[0]) { Fail "${where}: 'steps' must be a non-empty list" }

    # Expand sugar into primitive ops: @{op; key; ms; jitter}
    $ops = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $steps.Count; $i++) {
        $st = $steps[$i]
        $w = "$where, step $($i + 1)"
        if ($st -isnot [System.Management.Automation.PSCustomObject]) { Fail "${w}: each step must be an object" }
        $jit = Get-Opt $st 'jitter' $jitterDefault
        $again = $false
        if (Has $st 'should_press_again_on_stop') {
            if (-not (Has $st 'tap')) {
                $kind = @('hold', 'wait', 'down', 'up', 'send') | Where-Object { Has $st $_ } | Select-Object -First 1
                Fail "${w}: 'should_press_again_on_stop' goes on the tap step itself (the key to press again), not on a '$kind' step"
            }
            if ($st.should_press_again_on_stop -isnot [bool]) { Fail "${w}: 'should_press_again_on_stop' must be true or false" }
            $again = $st.should_press_again_on_stop
        }

        if (Has $st 'tap') {
            $k = [string]$st.tap
            [void]$ops.Add(@{ op = 'tap'; key = $k; again = $again })
            $times = [int](Get-Opt $st 'times' 1)
            for ($t = 1; $t -lt $times; $t++) {
                [void]$ops.Add(@{ op = 'wait'; ms = (Ms-Value (Get-Opt $st 'gap' 50) $w); jitter = 0 })
                [void]$ops.Add(@{ op = 'tap'; key = $k; again = $again })
            }
        } elseif (Has $st 'down') {
            [void]$ops.Add(@{ op = 'down'; key = [string]$st.down })
        } elseif (Has $st 'up') {
            [void]$ops.Add(@{ op = 'up'; key = [string]$st.up })
        } elseif (Has $st 'send') {
            [void]$ops.Add(@{ op = 'send'; key = [string]$st.send })
        } elseif (Has $st 'hold') {
            $k = [string]$st.hold
            [void]$ops.Add(@{ op = 'down'; key = $k })
            [void]$ops.Add(@{ op = 'wait'; ms = (Ms-Value (Get-Opt $st 'ms' $null) $w); jitter = (Ms-Value $jit $w) })
            [void]$ops.Add(@{ op = 'up'; key = $k })
        } elseif (Has $st 'wait') {
            [void]$ops.Add(@{ op = 'wait'; ms = (Ms-Value $st.wait $w); jitter = (Ms-Value $jit $w) })
        } else {
            $json = ($st | ConvertTo-Json -Compress)
            Fail "${w}: unknown step $json. Use one of: tap, down, up, hold, wait, send"
        }
    }

    # Group into phases: actions..., then one wait
    $phases = New-Object System.Collections.ArrayList
    $cur = New-Object System.Collections.ArrayList
    foreach ($op in $ops) {
        if ($op.op -eq 'wait') {
            [void]$phases.Add(@{ actions = @($cur); ms = $op.ms; jitter = $op.jitter })
            $cur = New-Object System.Collections.ArrayList
        } else {
            [void]$cur.Add($op)
        }
    }
    if ($cur.Count -gt 0) { [void]$phases.Add(@{ actions = @($cur); ms = 0; jitter = 0 }) }

    # Sanity check: simulate held keys through one cycle
    $held = New-Object System.Collections.Generic.List[string]
    $ever = New-Object System.Collections.Generic.List[string]
    foreach ($ph in $phases) {
        foreach ($a in $ph.actions) {
            if ($a.op -eq 'down') {
                if (-not $held.Contains($a.key)) { $held.Add($a.key) }
                if (-not $ever.Contains($a.key)) { $ever.Add($a.key) }
            } elseif ($a.op -eq 'up') {
                [void]$held.Remove($a.key)
            }
        }
    }
    if ($held.Count -gt 0) {
        [Console]::Error.WriteLine("warning: ${where}: cycle ends with key(s) still held: $($held -join ', ')")
    }
    $againKeys = New-Object System.Collections.Generic.List[string]
    foreach ($op in $ops) {
        if ($op.op -eq 'tap' -and $op.again -and -not $againKeys.Contains($op.key)) { $againKeys.Add($op.key) }
    }
    return @{ phases = @($phases); ever = @($ever); again = @($againKeys) }
}

# ---------------------------------------------------------------- load
if (-not (Test-Path -LiteralPath $Config)) { Fail "config file not found: $Config" }
try {
    $raw = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Config).Path)
    $cfg = $raw | ConvertFrom-Json
} catch {
    Fail "invalid JSON: $($_.Exception.Message)"
}

$s = Get-Opt $cfg 'settings' $null
$tickMs      = Get-Opt $s 'tick_ms' 10
$sounds      = Get-Opt $s 'sounds' ([pscustomobject]@{ on = @(1000, 100); off = @(500, 100) })
$window      = Get-Opt $s 'window' $null
$panicHotkey = Get-Opt $s 'panic_hotkey' $null
$jitterDef   = Get-Opt $s 'jitter_default' 0

function Get-Beeps($snd) {
    if ($null -eq $snd -or $snd -eq $false) { return @($null, $null) }
    return @("SoundBeep, $($snd.on[0]), $($snd.on[1])", "SoundBeep, $($snd.off[0]), $($snd.off[1])")
}
$globalOff = (Get-Beeps $sounds)[1]

$macroList = @(Get-Opt $cfg 'macros' @())
if ($macroList.Count -eq 0 -or $null -eq $macroList[0]) { Fail "config needs a non-empty 'macros' list" }

$macros = New-Object System.Collections.ArrayList
$seenHotkeys = @{}
$idx = 0
foreach ($m in $macroList) {
    $idx++
    $name = Get-Opt $m 'name' $null
    if (-not $name) { $name = Get-Opt $m 'hotkey' "macro$idx" }
    $where = "macro '$name'"
    $hk = Get-Opt $m 'hotkey' $null
    if (-not $hk -or $hk -isnot [string]) { Fail "${where}: missing 'hotkey'" }
    if ($seenHotkeys.ContainsKey($hk)) { Fail "${where}: hotkey '$hk' used twice" }
    $seenHotkeys[$hk] = $true
    $hasSteps = Has $m 'steps'; $hasTracks = Has $m 'tracks'
    if ($hasSteps -eq $hasTracks) { Fail "${where}: use either 'steps' or 'tracks' (exactly one)" }
    if ($hasSteps) {
        $trackDefs = @([pscustomobject]@{ steps = $m.steps })
    } else {
        $trackDefs = @($m.tracks)
        if ($trackDefs.Count -eq 0 -or $null -eq $trackDefs[0]) { Fail "${where}: 'tracks' must be a non-empty list" }
    }
    $tracks = New-Object System.Collections.ArrayList
    $held = New-Object System.Collections.Generic.List[string]
    for ($t = 0; $t -lt $trackDefs.Count; $t++) {
        $td = $trackDefs[$t]
        if ($td -isnot [System.Management.Automation.PSCustomObject]) { Fail "${where}, track $($t + 1): each track must be an object with 'steps'" }
        $tname = Get-Opt $td 'name' $null
        if (-not $tname) { $tname = "track $($t + 1)" }
        $tw = $where; if (-not $hasSteps) { $tw = "$where, $tname" }
        $c = Compile-Steps (Get-Opt $td 'steps' $null) $tw $jitterDef
        foreach ($k in $c.ever) { if (-not $held.Contains($k)) { $held.Add($k) } }
        [void]$tracks.Add(@{ name = [string]$tname; phases = $c.phases; again = $c.again })
    }
    $snd = Get-Opt $m 'sounds' $sounds
    if ($snd -eq $true) { $snd = $sounds }
    $b = Get-Beeps $snd
    [void]$macros.Add(@{
        id          = "M$idx"
        name        = [string]$name
        hotkey      = $hk
        channel     = [string](Get-Opt $m 'channel' "__solo_$idx")
        loop        = [bool](Get-Opt $m 'loop' $true)
        takeover    = [bool](Get-Opt $m 'takeover' $false)
        description = [string](Get-Opt $m 'description' '')
        onBeep      = $b[0]
        offBeep     = $b[1]
        tracks      = @($tracks)
        held        = @($held)
    })
}

# ---------------------------------------------------------------- emit
$L = New-Object System.Collections.Generic.List[string]
function Add([string]$line) { $L.Add($line) }

$chanNames = New-Object System.Collections.Generic.List[string]
foreach ($m in $macros) { if (-not $chanNames.Contains($m.channel)) { $chanNames.Add($m.channel) } }
$chanId = @{}
for ($i = 0; $i -lt $chanNames.Count; $i++) { $chanId[$chanNames[$i]] = "Ch$($i + 1)" }
foreach ($m in $macros) {
    $m.ch = $chanId[$m.channel]
    # one track keeps the short names (M1_Phase), several get M1_T1_Phase, ...
    $single = ($m.tracks.Count -eq 1)
    for ($t = 0; $t -lt $m.tracks.Count; $t++) {
        if ($single) { $m.tracks[$t].pfx = $m.id } else { $m.tracks[$t].pfx = "$($m.id)_T$($t + 1)" }
    }
}

$bar = ';' + ('#' * 78)
$srcName = Split-Path -Leaf $Config
Add $bar
Add "; GENERATED by ahkgen.ps1 from $srcName - do not edit by hand, regenerate."
Add ';'
Add '; Channel rules: pressing a hotkey'
Add ';   - stops its own macro if it is the one running on the channel'
Add ';   - stops the OTHER macro if a different one occupies the channel (starts nothing)'
Add ';     ...unless the macro has takeover, then it also starts right away'
Add ';   - starts its macro if the channel is free'
Add ';'
Add '; Macros:'
foreach ($m in $macros) {
    $ch = $m.channel; if ($ch.StartsWith('__solo_')) { $ch = '(own channel)' }
    $flags = New-Object System.Collections.Generic.List[string]
    if ($m.loop) { $flags.Add('loop') } else { $flags.Add('once') }
    if ($m.takeover) { $flags.Add('takeover') }
    if ($m.tracks.Count -gt 1) { $flags.Add("$($m.tracks.Count) parallel tracks") }
    $line = ';   {0,-10} {1}  [channel: {2}, {3}]' -f $m.hotkey, $m.name, $ch, ($flags -join ', ')
    if ($m.description) { $line += " - $($m.description)" }
    Add $line
}
Add $bar
Add ''
Add '#Persistent'
Add '#NoEnv'
Add '#SingleInstance, Force'
Add ''
Add '; ---------------- state ----------------'
foreach ($c in $chanNames) { Add ('{0}_Active := ""   ; channel "{1}"' -f $chanId[$c], $c) }
foreach ($m in $macros) {
    $i = $m.id
    Add "${i}_Active := False   ; $($m.name)"
    foreach ($t in $m.tracks) {
        $cmt = ''; if ($m.tracks.Count -gt 1) { $cmt = "   ; $($t.name)" }
        Add "$($t.pfx)_Phase := 0$cmt"
        Add "$($t.pfx)_NextMs := 0"
        if (-not $m.loop) { Add "$($t.pfx)_Done := False" }
        if ($t.again.Count -gt 0) {
            $legend = @(for ($a = 0; $a -lt $t.again.Count; $a++) { "$($a + 1)=$($t.again[$a])" }) -join ', '
            Add "$($t.pfx)_Again := 0   ; last key pressed needs a re-press on stop ($legend)"
        }
    }
    for ($k = 0; $k -lt $m.held.Count; $k++) { Add "${i}_Held$k := False   ; key $($m.held[$k])" }
}
Add ''
Add "SetTimer, MainLoop, $([int]$tickMs)"
Add 'return'
Add ''

Add '; ---------------- hotkeys ----------------'
if ($window) { Add "#IfWinActive, $window" }
foreach ($m in $macros) { Add "$($m.hotkey)::GoSub, Toggle_$($m.id)   ; $($m.name)" }
if ($panicHotkey) { Add "${panicHotkey}::GoSub, StopAll" }
if ($window) { Add '#IfWinActive' }
Add ''

Add '; ---------------- toggle handlers ----------------'
foreach ($m in $macros) {
    $i = $m.id; $ch = $m.ch
    $others = @($macros | Where-Object { $_.ch -eq $ch -and $_.id -ne $i })
    Add "Toggle_${i}:"
    Add "    if (${ch}_Active = `"$i`") {"
    Add "        GoSub, Stop_$i"
    Add "        ${ch}_Active := `"`""
    if ($m.offBeep) { Add "        $($m.offBeep)" }
    Add '        return'
    Add '    }'
    if ($others.Count -gt 0) {
        Add "    if (${ch}_Active != `"`") {"
        # beep with the stopped macro's own "off" sound
        $offs = @($others | ForEach-Object { [string]$_.offBeep } | Select-Object -Unique)
        if ($offs.Count -gt 1) { Add "        Prev := ${ch}_Active" }
        Add "        GoSub, StopChannel_$ch"
        if ($offs.Count -eq 1) {
            if ($others[0].offBeep) { Add "        $($others[0].offBeep)" }
        } else {
            foreach ($o in $others) {
                if ($o.offBeep) {
                    Add "        if (Prev = `"$($o.id)`")"
                    Add "            $($o.offBeep)"
                }
            }
        }
        if (-not $m.takeover) { Add '        return' }
        Add '    }'
    }
    Add "    ${i}_Active := True"
    foreach ($t in $m.tracks) {
        Add "    $($t.pfx)_Phase := 0"
        Add "    $($t.pfx)_NextMs := A_TickCount"
        if (-not $m.loop) { Add "    $($t.pfx)_Done := False" }
        if ($t.again.Count -gt 0) { Add "    $($t.pfx)_Again := 0" }
    }
    Add "    ${ch}_Active := `"$i`""
    if ($m.onBeep) { Add "    $($m.onBeep)" }
    Add 'return'
    Add ''
}

Add '; ---------------- channel stop helpers ----------------'
foreach ($c in $chanNames) {
    $ch = $chanId[$c]
    Add "StopChannel_${ch}:"
    $first = $true
    foreach ($m in $macros) {
        if ($m.ch -ne $ch) { continue }
        $kw = 'else if'; if ($first) { $kw = 'if' }
        Add "    $kw (${ch}_Active = `"$($m.id)`")"
        Add "        GoSub, Stop_$($m.id)"
        $first = $false
    }
    Add "    ${ch}_Active := `"`""
    Add 'return'
    Add ''
}

Add 'StopAll:'
foreach ($c in $chanNames) { Add "    GoSub, StopChannel_$($chanId[$c])" }
if ($globalOff) { Add "    $globalOff" }
Add 'return'
Add ''

Add '; ---------------- stop handlers (release held keys) ----------------'
foreach ($m in $macros) {
    $i = $m.id
    Add "Stop_${i}:"
    for ($k = 0; $k -lt $m.held.Count; $k++) {
        Add "    if (${i}_Held$k) {"
        Add "        Send, $(Key-Token $m.held[$k] 'up')"
        Add "        ${i}_Held$k := False"
        Add '    }'
    }
    Add "    ${i}_Active := False"
    foreach ($t in $m.tracks) {
        for ($a = 0; $a -lt $t.again.Count; $a++) {
            Add "    if ($($t.pfx)_Again = $($a + 1))"
            Add "        Send, $(Key-Token $t.again[$a])   ; should_press_again_on_stop"
        }
        if ($t.again.Count -gt 0) { Add "    $($t.pfx)_Again := 0" }
    }
    foreach ($t in $m.tracks) { Add "    $($t.pfx)_Phase := 0" }
    Add 'return'
    Add ''
}

Add '; ---------------- main loop - no Sleep, ever ----------------'
Add 'MainLoop:'
Add '    Now := A_TickCount'
foreach ($m in $macros) {
    foreach ($t in $m.tracks) {
        $done = ''; if (-not $m.loop) { $done = " && !$($t.pfx)_Done" }
        Add "    if ($($m.id)_Active$done && Now >= $($t.pfx)_NextMs)"
        Add "        GoSub, Step_$($t.pfx)"
    }
}
Add 'return'
Add ''

foreach ($m in $macros) {
    $i = $m.id; $ch = $m.ch
    $heldIdx = @{}
    for ($k = 0; $k -lt $m.held.Count; $k++) { $heldIdx[$m.held[$k]] = $k }
    foreach ($t in $m.tracks) {
        $pfx = $t.pfx
        $n = $t.phases.Count
        $label = $m.name; if ($m.tracks.Count -gt 1) { $label = "$($m.name) / $($t.name)" }
        Add "; --- $label ---"
        Add "Step_${pfx}:"
        for ($p = 0; $p -lt $n; $p++) {
            $ph = $t.phases[$p]
            $kw = '} else if'; if ($p -eq 0) { $kw = 'if' }
            Add "    $kw (${pfx}_Phase = $p) {"
            foreach ($a in $ph.actions) {
                switch ($a.op) {
                    'tap'  { Add "        Send, $(Key-Token $a.key)" }
                    'down' {
                        Add "        Send, $(Key-Token $a.key 'down')"
                        Add "        ${i}_Held$($heldIdx[$a.key]) := True"
                    }
                    'up'   {
                        Add "        Send, $(Key-Token $a.key 'up')"
                        if ($heldIdx.ContainsKey($a.key)) { Add "        ${i}_Held$($heldIdx[$a.key]) := False" }
                    }
                    'send' { Add "        Send, $(Esc-Send $a.key)" }
                }
            }
            if ($t.again.Count -gt 0 -and $ph.actions.Count -gt 0) {
                $last = $ph.actions[$ph.actions.Count - 1]
                if ($last.op -eq 'tap' -and $last.again) {
                    Add "        ${pfx}_Again := $($t.again.IndexOf($last.key) + 1)"
                } else {
                    Add "        ${pfx}_Again := 0"
                }
            }
            if ($m.loop) { $nxt = ($p + 1) % $n } else { $nxt = $p + 1 }
            Add "        ${pfx}_Phase := $nxt"
            if ($ph.jitter -gt 0) {
                Add "        Random, ${pfx}_J, 0, $($ph.jitter)"
                Add "        ${pfx}_NextMs := A_TickCount + $($ph.ms) + ${pfx}_J"
            } else {
                Add "        ${pfx}_NextMs := A_TickCount + $($ph.ms)"
            }
        }
        if (-not $m.loop) {
            # this track finished its one-shot run; stop once every track is done
            $allDone = ($m.tracks | ForEach-Object { "$($_.pfx)_Done" }) -join ' && '
            Add '    } else {'
            Add "        ${pfx}_Done := True"
            Add "        if ($allDone) {"
            foreach ($tt in $m.tracks) { if ($tt.again.Count -gt 0) { Add "            $($tt.pfx)_Again := 0   ; finished on its own, no re-press" } }
            Add "            GoSub, Stop_$i"
            Add "            ${ch}_Active := `"`""
            if ($m.offBeep) { Add "            $($m.offBeep)" }
            Add '        }'
        }
        Add '    }'
        Add 'return'
        Add ''
    }
}

# ---------------------------------------------------------------- write
$configFull = (Resolve-Path -LiteralPath $Config).ProviderPath
if (-not $Output) {
    # Default: same folder and name as the config, with .ahk
    $outFull = [IO.Path]::ChangeExtension($configFull, '.ahk')
} elseif ([IO.Path]::IsPathRooted($Output)) {
    $outFull = $Output
} else {
    $outFull = Join-Path (Get-Location).ProviderPath $Output
}
$outFull = [IO.Path]::GetFullPath($outFull)
$Output = $outFull
# UTF-8 *with* BOM + CRLF: what AutoHotkey v1 reads most reliably
$text = ($L -join "`r`n") + "`r`n"
[IO.File]::WriteAllText($outFull, $text, (New-Object System.Text.UTF8Encoding($true)))
Write-Host "wrote $Output ($($macros.Count) macros)"
