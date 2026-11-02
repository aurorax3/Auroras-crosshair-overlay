# Process-only sampling: no input hooks, injection, timers inside the application,
# or persistent services. GPU counters are optional and remain per-engine.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][int[]]$ProcessIds,
    [int]$GameProcessId = 0,
    [ValidateRange(1, 86400)][int]$DurationSeconds = 120,
    [ValidateRange(0.1, 60)][double]$SampleIntervalSeconds = 1,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$RunId,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$Scenario = 'idle',
    [hashtable]$Conditions = @{},
    [switch]$IncludeGpuCounters
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This capture requires Windows.' }
$selectedIds = @($ProcessIds)
if ($GameProcessId -gt 0) { $selectedIds += $GameProcessId }
$selectedIds = @($selectedIds | Select-Object -Unique)
if (@($selectedIds | Where-Object { $_ -le 0 }).Count -gt 0) {
    throw 'Select positive, explicit process IDs.'
}
[void](New-Item -ItemType Directory -Path $OutputDirectory -Force)
$outputRoot = (Resolve-Path -LiteralPath $OutputDirectory).Path
$processFile = Join-Path $outputRoot "$RunId-process.csv"
$gpuFile = Join-Path $outputRoot "$RunId-gpu.csv"
$metadataFile = Join-Path $outputRoot "$RunId-metadata.json"
foreach ($file in @($processFile, $gpuFile, $metadataFile)) {
    if (Test-Path -LiteralPath $file) { throw "Refusing to overwrite existing run: $file" }
}

function Read-ProcessSnapshot([int]$TargetId) {
    $process = $null
    try {
        $process = Get-Process -Id $TargetId -ErrorAction Stop
        $process.Refresh()
        if ($process.HasExited) { throw "Selected process $TargetId exited." }
        [pscustomobject]@{
            Id = $TargetId
            Name = $process.ProcessName
            StartTicks = $process.StartTime.ToUniversalTime().Ticks
            StartUtc = $process.StartTime.ToUniversalTime().ToString('o')
            CpuSeconds = $process.TotalProcessorTime.TotalSeconds
            WorkingSetBytes = $process.WorkingSet64
            PrivateBytes = $process.PrivateMemorySize64
            HandleCount = $process.HandleCount
        }
    } finally {
        if ($null -ne $process) { $process.Dispose() }
    }
}

$computer = Get-CimInstance Win32_ComputerSystem
$logicalCpus = [int]$computer.NumberOfLogicalProcessors
if ($logicalCpus -lt 1) { throw 'Unable to determine machine logical processor count.' }
$operatingSystem = Get-CimInstance Win32_OperatingSystem
$video = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion,
    CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate)
$metadata = [ordered]@{
    schema_version = 1
    run_id = $RunId
    scenario = $Scenario
    started_utc = [DateTime]::UtcNow.ToString('o')
    requested_duration_seconds = $DurationSeconds
    requested_sample_interval_seconds = $SampleIntervalSeconds
    logical_processors = $logicalCpus
    cpu_names = @(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name)
    os = $operatingSystem.Caption
    os_version = $operatingSystem.Version
    os_build = $operatingSystem.BuildNumber
    total_physical_memory_bytes = $computer.TotalPhysicalMemory
    video_controllers = $video
    conditions = $Conditions
    powershell_version = $PSVersionTable.PSVersion.ToString()
    selected_processes = @()
    gpu_counter_status = 'not_requested'
    outcome = 'capturing'
    definitions = @{
        cpu_percent_one_core = '100 * process CPU delta seconds / wall delta seconds; may exceed 100 for multiple threads'
        cpu_percent_machine = 'cpu_percent_one_core / machine logical processor count'
        memory = 'WorkingSet64 and PrivateMemorySize64, not GPU memory'
        gpu = 'Optional Windows GPU Engine counters, one row per PID/engine; never sum percentages across engines'
    }
    unavailable_metrics = @('game FPS/frame times without separate frame capture', 'reliable input latency')
}
$processRows = [System.Collections.Generic.List[object]]::new()
$gpuRows = [System.Collections.Generic.List[object]]::new()
$previous = @{}
$clock = [System.Diagnostics.Stopwatch]::StartNew()
$failure = $null
try {
    foreach ($targetId in $selectedIds) {
        $snapshot = Read-ProcessSnapshot $targetId
        $previous[$targetId] = @{ Snapshot = $snapshot; Wall = $clock.Elapsed.TotalSeconds }
        $metadata.selected_processes += @{
            process_id = $targetId
            name = $snapshot.Name
            started_utc = $snapshot.StartUtc
            role = $(if ($targetId -eq $GameProcessId) { 'game' } else { 'selected' })
        }
    }
    if ($IncludeGpuCounters) { $metadata.gpu_counter_status = 'pending' }
    $nextSampleAt = $clock.Elapsed.TotalSeconds + $SampleIntervalSeconds
    $captureEndsAt = $clock.Elapsed.TotalSeconds + $DurationSeconds
    while ($clock.Elapsed.TotalSeconds -lt $captureEndsAt) {
        $delayMs = [int][Math]::Ceiling(1000 * ([Math]::Min($nextSampleAt, $captureEndsAt) - $clock.Elapsed.TotalSeconds))
        if ($delayMs -gt 0) { Start-Sleep -Milliseconds $delayMs }
        foreach ($targetId in $selectedIds) {
            $current = Read-ProcessSnapshot $targetId
            $wall = $clock.Elapsed.TotalSeconds
            $last = $previous[$targetId]
            if ($current.StartTicks -ne $last.Snapshot.StartTicks) {
                throw "Selected PID $targetId was reused; this run is invalid."
            }
            $elapsed = $wall - $last.Wall
            $cpuDelta = $current.CpuSeconds - $last.Snapshot.CpuSeconds
            if ($elapsed -le 0 -or $cpuDelta -lt 0) { throw "Invalid CPU delta for PID $targetId." }
            $oneCorePercent = 100 * $cpuDelta / $elapsed
            [void]$processRows.Add([pscustomobject]@{
                run_id = $RunId
                timestamp_utc = [DateTime]::UtcNow.ToString('o')
                elapsed_seconds = $wall
                process_id = $targetId
                process_started_utc = $current.StartUtc
                name = $current.Name
                wall_delta_seconds = $elapsed
                cpu_delta_seconds = $cpuDelta
                cpu_percent_one_core = $oneCorePercent
                cpu_percent_machine = $oneCorePercent / $logicalCpus
                working_set_bytes = $current.WorkingSetBytes
                private_bytes = $current.PrivateBytes
                handle_count = $current.HandleCount
            })
            $previous[$targetId] = @{ Snapshot = $current; Wall = $wall }
        }
        if ($IncludeGpuCounters -and $metadata.gpu_counter_status -notlike 'unavailable*') {
            try {
                # On localized Windows this English counter name can be unavailable.
                # Optional collection can also lengthen sample intervals; actual wall
                # deltas are recorded and CPU calculations use those deltas.
                $counterSet = Get-Counter -Counter '\GPU Engine(*)\Utilization Percentage' -MaxSamples 1 -ErrorAction Stop
                $beforeCount = $gpuRows.Count
                foreach ($counter in $counterSet.CounterSamples) {
                    if ($counter.InstanceName -notmatch '^pid_([0-9]+)_') { continue }
                    $engineProcessId = [int]$Matches[1]
                    if ($selectedIds -notcontains $engineProcessId) { continue }
                    $utilization = [double]$counter.CookedValue
                    if ($counter.Status -ne 0 -or [double]::IsNaN($utilization) -or
                        [double]::IsInfinity($utilization) -or $utilization -lt 0 -or $utilization -gt 100) { continue }
                    [void]$gpuRows.Add([pscustomobject]@{
                        run_id = $RunId
                        timestamp_utc = $counterSet.Timestamp.ToUniversalTime().ToString('o')
                        process_id = $engineProcessId
                        engine_instance = $counter.InstanceName
                        utilization_percent = $utilization
                    })
                }
                if ($gpuRows.Count -eq $beforeCount) {
                    $metadata.gpu_counter_status = 'unavailable: no valid engine counters for selected PIDs'
                } else { $metadata.gpu_counter_status = 'collected_per_engine' }
            } catch {
                $metadata.gpu_counter_status = 'unavailable: ' + $_.Exception.Message
            }
        }
        $nextSampleAt += $SampleIntervalSeconds
        if ($nextSampleAt -lt $clock.Elapsed.TotalSeconds) {
            $nextSampleAt = $clock.Elapsed.TotalSeconds + $SampleIntervalSeconds
        }
    }
    $metadata.outcome = 'completed'
} catch {
    $failure = $_.Exception.Message
    $metadata.outcome = 'failed_process_capture'
    $metadata['failure'] = $failure
} finally {
    $clock.Stop()
    $metadata['finished_utc'] = [DateTime]::UtcNow.ToString('o')
    $metadata['actual_duration_seconds'] = $clock.Elapsed.TotalSeconds
    $metadata['process_sample_count'] = $processRows.Count
    $metadata['gpu_sample_count'] = $gpuRows.Count
    if ($processRows.Count -gt 0) { $processRows | Export-Csv -LiteralPath $processFile -NoTypeInformation -Encoding UTF8 }
    if ($gpuRows.Count -gt 0) { $gpuRows | Export-Csv -LiteralPath $gpuFile -NoTypeInformation -Encoding UTF8 }
    $metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $metadataFile -Encoding UTF8
}
if ($failure) { throw $failure }
Write-Output "Saved $RunId process samples and metadata in $outputRoot"
