<#
One-train-per-process launcher.

Each vehicle process owns exactly one Train instance selected by --vehicle-id.
ZMQ topics are still shared: driver_input, ato_command, ma_state, comm_state,
power_state, track_info, and train_state. Each process filters messages by
vehicle_id internally; this script does not create per-vehicle topics.

Examples:
  .\scripts\run_vehicle_processes.ps1 -Count 3
  .\scripts\run_vehicle_processes.ps1 -Count 2 -Spacing 500
  .\scripts\run_vehicle_processes.ps1 -Count 2 -NoZmq -Steps 1
#>

param(
    [int]$Count = 3,
    [double]$Spacing = 300.0,
    [double]$Dt = 0.1,
    [switch]$NoZmq,
    [int]$Steps = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Count -lt 1) {
    throw "Count must be at least 1."
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"

$RootVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendVenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (Test-Path $RootVenvPython) {
    $PythonExe = (Resolve-Path $RootVenvPython).Path
} elseif (Test-Path $BackendVenvPython) {
    $PythonExe = (Resolve-Path $BackendVenvPython).Path
} else {
    $PythonExe = "python"
}

function Format-VehicleId {
    param([int]$Index)
    return "TRAIN-{0:D3}" -f $Index
}

function Format-CommandLine {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )
    $quotedArgs = $Arguments | ForEach-Object {
        if ($_ -match "\s") {
            return '"' + $_ + '"'
        }
        return $_
    }
    return "$Executable $($quotedArgs -join ' ')"
}

Write-Host "Starting one-train vehicle processes"
Write-Host "project_root=$ProjectRoot"
Write-Host "backend_dir=$BackendDir"
Write-Host "python=$PythonExe"
Write-Host "count=$Count spacing=$Spacing dt=$Dt no_zmq=$($NoZmq.IsPresent) steps=$Steps"

$processes = @()

for ($i = 1; $i -le $Count; $i++) {
    $VehicleId = Format-VehicleId -Index $i
    $TrainIndex = $i
    $InitialPosition = ($i - 1) * $Spacing

    $Arguments = @(
        "-m", "app.vehicle_sim.main_integrated",
        "--vehicle-id", $VehicleId,
        "--train-index", "$TrainIndex",
        "--initial-position", "$InitialPosition",
        "--dt", "$Dt"
    )

    if ($NoZmq.IsPresent) {
        $Arguments += "--no-zmq"
    }

    if ($Steps -gt 0) {
        $Arguments += @("--steps", "$Steps")
    }

    Write-Host ""
    Write-Host "Launching $VehicleId"
    Write-Host (Format-CommandLine -Executable $PythonExe -Arguments $Arguments)

    $startParams = @{
        FilePath = $PythonExe
        ArgumentList = $Arguments
        WorkingDirectory = $BackendDir
        PassThru = $true
    }

    if ($Steps -gt 0) {
        $startParams.NoNewWindow = $true
    }

    $processes += Start-Process @startParams
}

if ($Steps -gt 0) {
    Write-Host ""
    Write-Host "Waiting for finite-step vehicle processes to exit..."
    foreach ($process in $processes) {
        if (-not $process.HasExited) {
            Wait-Process -Id $process.Id
        }
        Write-Host "process_id=$($process.Id) exited"
    }
}

Write-Host ""
Write-Host "Vehicle process launch complete."
