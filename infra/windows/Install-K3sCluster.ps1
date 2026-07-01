<#
.SYNOPSIS
    Sets up a Windows 11 Pro machine as a single-node Kubernetes (k3s) development
    server running inside WSL2 Ubuntu, while keeping the machine usable as a normal
    desktop.

.DESCRIPTION
    This installer is idempotent where practical: it detects existing components and
    skips work that is already done. It runs in ordered stages so it can survive the
    reboot that enabling Windows virtualization features requires:

        Stage 'Prereqs' : enable WSL + Virtual Machine Platform, write .wslconfig,
                          then (if Windows asks for a reboot) register a resume task
                          and stop.
        Stage 'Wsl'     : install/register Ubuntu LTS, restart WSL to apply .wslconfig.
        Stage 'Cluster' : provision Ubuntu (packages, k3s, kubeconfig, manifests) by
                          running provision-wsl.sh inside the distro, wire up Windows
                          kubectl + LAN exposure, and print verification steps.

    Running the script with no -Stage argument executes the full flow starting at
    'Prereqs'. Each stage is safe to re-run.

    Only official installation channels are used:
        * Windows features        -> Enable-WindowsOptionalFeature (in-box)
        * Ubuntu                  -> wsl --install -d Ubuntu (Microsoft/Canonical)
        * k3s                     -> https://get.k3s.io (Rancher/SUSE, inside WSL)
        * kubectl (Windows)       -> winget (Kubernetes.kubectl) or dl.k8s.io binary

.PARAMETER Stage
    Which stage to start from. Defaults to 'Prereqs' (full run). Valid values:
    Prereqs, Wsl, Cluster, All.

.PARAMETER Distro
    WSL distribution name to install/use. Default 'Ubuntu' (latest Ubuntu LTS).

.PARAMETER ClusterUser
    Linux username created inside the distro that owns ~/cluster and the kubeconfig.
    Defaults to the current Windows username, lower-cased and sanitized.

.PARAMETER SkipLanExposure
    Skip the netsh portproxy + firewall rules that publish ports 80/443 from the WSL2
    VM to your LAN. Use this if you only want localhost access.

.EXAMPLE
    # From an elevated PowerShell prompt:
    powershell -ExecutionPolicy Bypass -File .\Install-K3sCluster.ps1

.NOTES
    Target hardware : Ryzen 7 7730U / 16 GB RAM / 512 GB NVMe, Windows 11 Pro.
    Must run elevated (Administrator). A log is written to
    %USERPROFILE%\k3s-setup\install.log.
#>

[CmdletBinding()]
param(
    [ValidateSet('Prereqs', 'Wsl', 'Cluster', 'All')]
    [string]$Stage = 'All',

    [string]$Distro = 'Ubuntu',

    [string]$ClusterUser,

    [switch]$SkipLanExposure
)

# Fail loud: stop on the first unhandled error and treat them as terminating.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Constants and paths
# ---------------------------------------------------------------------------

$ScriptRoot    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProvisionSh   = Join-Path $ScriptRoot 'provision-wsl.sh'
$DeploySh      = Join-Path $ScriptRoot 'deploy-app.sh'
$StateDir      = Join-Path $env:USERPROFILE 'k3s-setup'
$LogFile       = Join-Path $StateDir 'install.log'
$WslConfigPath = Join-Path $env:USERPROFILE '.wslconfig'
$ResumeTask    = 'K3sSetupResume'   # Scheduled Task used to continue after reboot

# Resolve the Linux cluster user once (Windows user, lower-cased, alnum only).
if (-not $ClusterUser) {
    $ClusterUser = ($env:USERNAME.ToLower() -replace '[^a-z0-9]', '')
    if (-not $ClusterUser) { $ClusterUser = 'k3s' }
}

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

# Write-Log mirrors a timestamped, leveled line to both the console and the log
# file so progress is visible live and auditable afterwards.
function Write-Log {
    param(
        [Parameter(Mandatory)] [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'STEP')] [string]$Level = 'INFO'
    )
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line  = "[$stamp] [$Level] $Message"

    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'STEP'  { Write-Host $line -ForegroundColor Cyan }
        default { Write-Host $line -ForegroundColor Gray }
    }
    # Best-effort file logging; never let logging failures abort the install.
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch { }
}

# Fail terminates the run with a clear, actionable message.
function Fail {
    param([Parameter(Mandatory)] [string]$Message)
    Write-Log $Message -Level ERROR
    Write-Log "Setup aborted. See the log at: $LogFile" -Level ERROR
    exit 1
}

# ---------------------------------------------------------------------------
# Environment / precondition checks
# ---------------------------------------------------------------------------

# Assert-Admin ensures the process is elevated; virtualization features and
# netsh/firewall changes require Administrator.
function Assert-Admin {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Fail 'This script must be run from an elevated (Administrator) PowerShell prompt.'
    }
}

# Assert-Windows11 gives a soft warning if we are not on Windows 11 (build >= 22000).
# WSL2 works on Windows 10 too, but the requirements target Win11 Pro.
function Assert-WindowsVersion {
    $build = [int](Get-CimInstance Win32_OperatingSystem).BuildNumber
    if ($build -lt 22000) {
        Write-Log "Detected Windows build $build (< 22000). This script targets Windows 11 Pro; continuing anyway." -Level WARN
    } else {
        Write-Log "Windows build $build detected (Windows 11)." -Level INFO
    }
}

# Invoke-Native runs an external command, echoes it, and throws on non-zero exit
# so callers get fail-loud behaviour without repeating $LASTEXITCODE checks.
function Invoke-Native {
    param(
        [Parameter(Mandatory)] [string]$File,
        [string[]]$Arguments = @(),
        [switch]$AllowFailure
    )
    Write-Log "exec: $File $($Arguments -join ' ')" -Level INFO
    & $File @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        Fail "Command failed (exit $code): $File $($Arguments -join ' ')"
    }
    return $code
}

# ---------------------------------------------------------------------------
# WSL helpers
#
# `wsl.exe` emits UTF-16LE. When we need to parse its output we decode it via a
# temp file to avoid mojibake in the console encoding.
# ---------------------------------------------------------------------------

# Get-WslList returns the registered distro names (quiet list), UTF-16 decoded.
function Get-WslList {
    try {
        $raw = & wsl.exe -l -q 2>$null
        if (-not $raw) { return @() }
        # -l -q output can contain NUL bytes from UTF-16; strip and trim.
        return ($raw -split "`r?`n" | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
    } catch {
        return @()
    }
}

# Test-DistroInstalled reports whether $Distro is registered in WSL.
function Test-DistroInstalled {
    param([string]$Name = $Distro)
    return (Get-WslList) -contains $Name
}

# Invoke-WslRoot runs a bash command inside the distro as root and fails loudly.
function Invoke-WslRoot {
    param(
        [Parameter(Mandatory)] [string]$Command,
        [switch]$AllowFailure
    )
    Write-Log "wsl(root): $Command" -Level INFO
    & wsl.exe -d $Distro -u root -- bash -lc $Command
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        Fail "WSL command failed (exit $code): $Command"
    }
    return $code
}

# ---------------------------------------------------------------------------
# Resume-after-reboot support
#
# Enabling virtualization features usually needs a reboot. We register a
# one-shot Scheduled Task that re-launches this script at the next logon with
# the next stage, then remove it once that stage completes.
# ---------------------------------------------------------------------------

function Register-ResumeTask {
    param([Parameter(Mandatory)][ValidateSet('Wsl', 'Cluster')] [string]$NextStage)

    $ps      = (Get-Command powershell.exe).Source
    $selfArg = "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`" -Stage $NextStage -Distro `"$Distro`" -ClusterUser `"$ClusterUser`""
    if ($SkipLanExposure) { $selfArg += ' -SkipLanExposure' }

    $action    = New-ScheduledTaskAction -Execute $ps -Argument $selfArg
    $trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Unregister-ResumeTask   # ensure no stale copy
    Register-ScheduledTask -TaskName $ResumeTask -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
    Write-Log "Registered resume task '$ResumeTask' to continue at stage '$NextStage' after reboot." -Level INFO
}

function Unregister-ResumeTask {
    if (Get-ScheduledTask -TaskName $ResumeTask -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $ResumeTask -Confirm:$false
        Write-Log "Removed resume task '$ResumeTask'." -Level INFO
    }
}

# Request-Reboot prompts the operator to reboot (resume is already registered).
function Request-Reboot {
    param([string]$NextStage)
    Write-Log 'A reboot is required to finish enabling Windows virtualization features.' -Level WARN
    Write-Log "After you log back in, setup will AUTOMATICALLY resume at stage '$NextStage'." -Level WARN
    $answer = Read-Host 'Reboot now? [y/N]'
    if ($answer -match '^(y|yes)$') {
        Write-Log 'Rebooting now...' -Level STEP
        Restart-Computer -Force
    } else {
        Write-Log 'Reboot skipped. Please reboot manually; setup will resume on next logon.' -Level WARN
        exit 0
    }
}

# ===========================================================================
# STAGE 1 - Prereqs: Windows features + .wslconfig
# ===========================================================================

function Enable-Feature {
    param([Parameter(Mandatory)] [string]$FeatureName)

    $feature = Get-WindowsOptionalFeature -Online -FeatureName $FeatureName -ErrorAction Stop
    if ($feature.State -eq 'Enabled') {
        Write-Log "Feature '$FeatureName' already enabled." -Level INFO
        return $false   # no change, no reboot contribution
    }

    Write-Log "Enabling Windows feature '$FeatureName'..." -Level STEP
    # -NoRestart: we control reboots centrally and detect RestartNeeded ourselves.
    $result = Enable-WindowsOptionalFeature -Online -FeatureName $FeatureName -All -NoRestart -ErrorAction Stop
    return [bool]$result.RestartNeeded
}

function Write-WslConfig {
    # Desktop-friendly caps for a 16 GB machine: leave ~10 GB for Windows + 4K
    # video playback, give the k3s VM 6 GB / 6 vCPUs / 4 GB swap.
    $desired = @'
# Managed by Install-K3sCluster.ps1
# Tuned for a 16 GB Ryzen 7 7730U desktop that also does normal Windows work.
[wsl2]
memory=6GB
processors=6
swap=4GB
localhostForwarding=true
'@

    $needsWrite = $true
    if (Test-Path $WslConfigPath) {
        $current = Get-Content $WslConfigPath -Raw
        # Normalise line endings before comparing so we do not rewrite needlessly.
        if (($current -replace "`r`n", "`n").Trim() -eq ($desired -replace "`r`n", "`n").Trim()) {
            $needsWrite = $false
        } else {
            $backup = "$WslConfigPath.bak-$((Get-Date).ToString('yyyyMMddHHmmss'))"
            Copy-Item $WslConfigPath $backup -Force
            Write-Log "Existing .wslconfig backed up to $backup." -Level INFO
        }
    }

    if ($needsWrite) {
        Set-Content -Path $WslConfigPath -Value $desired -Encoding ASCII
        Write-Log "Wrote $WslConfigPath (memory=6GB, processors=6, swap=4GB, localhostForwarding=true)." -Level STEP
        return $true    # config changed -> WSL should be restarted later
    }
    Write-Log '.wslconfig already up to date.' -Level INFO
    return $false
}

function Invoke-StagePrereqs {
    Write-Log '=== STAGE: Prereqs (Windows features + .wslconfig) ===' -Level STEP

    $rebootNeeded = $false
    $rebootNeeded = (Enable-Feature 'Microsoft-Windows-Subsystem-Linux') -or $rebootNeeded
    $rebootNeeded = (Enable-Feature 'VirtualMachinePlatform')            -or $rebootNeeded

    Write-WslConfig | Out-Null

    if ($rebootNeeded) {
        Register-ResumeTask -NextStage 'Wsl'
        Request-Reboot -NextStage 'Wsl'
        # Request-Reboot either reboots or exits; we never fall through when true.
    }

    Write-Log 'Prereqs complete; no reboot required.' -Level INFO
}

# ===========================================================================
# STAGE 2 - Wsl: install Ubuntu LTS + apply .wslconfig
# ===========================================================================

function Invoke-StageWsl {
    Write-Log '=== STAGE: Wsl (Ubuntu LTS install) ===' -Level STEP

    # Keep the WSL kernel current via the official Microsoft updater.
    Invoke-Native -File 'wsl.exe' -Arguments @('--update') -AllowFailure | Out-Null
    Invoke-Native -File 'wsl.exe' -Arguments @('--set-default-version', '2') -AllowFailure | Out-Null

    if (Test-DistroInstalled) {
        Write-Log "Distro '$Distro' already registered; skipping install." -Level INFO
    } else {
        Write-Log "Installing '$Distro' via 'wsl --install' (official Canonical image, no launch)..." -Level STEP
        # --no-launch registers the distro without the interactive first-run user
        # prompt; we provision non-interactively as root in the next stage.
        $code = Invoke-Native -File 'wsl.exe' -Arguments @('--install', '-d', $Distro, '--no-launch') -AllowFailure
        if ($code -ne 0) {
            # Some Windows builds require a reboot after the very first distro
            # registration. Register a resume and reboot rather than failing.
            Write-Log "'wsl --install' reported a non-zero exit; a reboot is likely required." -Level WARN
            Register-ResumeTask -NextStage 'Wsl'
            Request-Reboot -NextStage 'Wsl'
        }

        # Initialise the distro (first `wsl -d` run completes registration).
        Invoke-Native -File 'wsl.exe' -Arguments @('-d', $Distro, '-u', 'root', '--', 'true') -AllowFailure | Out-Null

        if (-not (Test-DistroInstalled)) {
            Fail "Ubuntu did not register. Try running 'wsl --install -d $Distro' manually, then re-run: -Stage Wsl."
        }
        Write-Log "Distro '$Distro' installed." -Level INFO
    }

    # Apply the new .wslconfig by terminating the running VM; it restarts on next use.
    Write-Log 'Restarting WSL to apply .wslconfig...' -Level STEP
    Invoke-Native -File 'wsl.exe' -Arguments @('--shutdown') -AllowFailure | Out-Null
    Start-Sleep -Seconds 8
    # Warm the distro back up and confirm it responds.
    Invoke-WslRoot 'echo WSL-online' | Out-Null
    Write-Log 'WSL restarted and responding.' -Level INFO
}

# ===========================================================================
# STAGE 3 - Cluster: provision Ubuntu, wire kubectl + LAN, verify
# ===========================================================================

# Copy-ProvisionScript pushes provision-wsl.sh into the distro with LF endings.
function Copy-ProvisionScript {
    if (-not (Test-Path $ProvisionSh)) {
        Fail "Helper script not found: $ProvisionSh (it must sit next to this installer)."
    }
    # Translate the Windows path to a /mnt/... path and copy inside the distro so
    # ownership/line-endings are clean regardless of the Windows checkout.
    $wslSource = (& wsl.exe -d $Distro -u root -- wslpath -a "$ProvisionSh").Trim()
    Invoke-WslRoot "install -m 0755 '$wslSource' /usr/local/sbin/provision-wsl.sh"
    Write-Log 'Copied provision-wsl.sh into the distro.' -Level INFO
}

function Invoke-StageCluster {
    Write-Log '=== STAGE: Cluster (packages, k3s, manifests) ===' -Level STEP

    if (-not (Test-DistroInstalled)) {
        Fail "Distro '$Distro' is not installed. Run: -Stage Wsl first."
    }

    Copy-ProvisionScript

    # Run the heavy lifting inside Ubuntu. The bash script is idempotent and does:
    # apt packages, k3s install, health checks, kubeconfig, ~/cluster + manifests.
    Write-Log 'Provisioning Ubuntu (apt, k3s, manifests)... this can take several minutes.' -Level STEP
    Invoke-WslRoot "CLUSTER_USER='$ClusterUser' /usr/local/sbin/provision-wsl.sh"

    Copy-DeployHelper
    Set-WindowsKubeconfig
    Install-WindowsKubectl
    if (-not $SkipLanExposure) { Set-LanExposure }

    Show-Summary
    Unregister-ResumeTask   # success: remove the resume hook if present
}

# Copy-DeployHelper drops deploy-app.sh into the user's ~/cluster so the build →
# containerd-import → rollout workflow (see DEPLOY.md) is available in-place.
function Copy-DeployHelper {
    if (-not (Test-Path $DeploySh)) {
        Write-Log 'deploy-app.sh not found next to installer; skipping (optional helper).' -Level WARN
        return
    }
    $userHome = (& wsl.exe -d $Distro -u root -- bash -lc "getent passwd '$ClusterUser' | cut -d: -f6").Trim()
    if (-not $userHome) { $userHome = "/home/$ClusterUser" }
    $src = (& wsl.exe -d $Distro -u root -- wslpath -a "$DeploySh").Trim()
    Invoke-WslRoot "install -m 0755 -o '$ClusterUser' -g '$ClusterUser' '$src' '$userHome/cluster/deploy-app.sh'"
    Write-Log "Installed deploy-app.sh to $userHome/cluster/deploy-app.sh." -Level INFO
}

# Set-WindowsKubeconfig copies the k3s kubeconfig out to Windows. Because
# localhostForwarding=true, the embedded https://127.0.0.1:6443 works from Windows.
function Set-WindowsKubeconfig {
    $kubeDir  = Join-Path $env:USERPROFILE '.kube'
    $kubeCfg  = Join-Path $kubeDir 'config'
    New-Item -ItemType Directory -Force -Path $kubeDir | Out-Null

    $yaml = & wsl.exe -d $Distro -u root -- cat /etc/rancher/k3s/k3s.yaml
    if ($LASTEXITCODE -ne 0 -or -not $yaml) {
        Fail 'Could not read /etc/rancher/k3s/k3s.yaml from the distro.'
    }
    # k3s already binds 127.0.0.1; keep as-is for localhost forwarding from Windows.
    Set-Content -Path $kubeCfg -Value $yaml -Encoding ASCII
    Write-Log "Wrote Windows kubeconfig to $kubeCfg." -Level STEP

    # Persist KUBECONFIG for the user so `kubectl` just works in new shells.
    [Environment]::SetEnvironmentVariable('KUBECONFIG', $kubeCfg, 'User')
    $env:KUBECONFIG = $kubeCfg
    Write-Log "Set user KUBECONFIG=$kubeCfg." -Level INFO
}

# Install-WindowsKubectl installs kubectl on Windows via winget (official) with a
# fallback to the official dl.k8s.io binary. Skipped if kubectl already resolves.
function Install-WindowsKubectl {
    if (Get-Command kubectl -ErrorAction SilentlyContinue) {
        Write-Log 'kubectl already present on Windows PATH; skipping install.' -Level INFO
        return
    }

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Log 'Installing kubectl via winget (Kubernetes.kubectl)...' -Level STEP
        $code = Invoke-Native -File 'winget' -Arguments @(
            'install', '--id', 'Kubernetes.kubectl', '-e', '--silent',
            '--accept-package-agreements', '--accept-source-agreements'
        ) -AllowFailure
        if ($code -eq 0) { return }
        Write-Log 'winget install failed; falling back to official dl.k8s.io binary.' -Level WARN
    }

    # Official Kubernetes release binary.
    $binDir = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'   # already on PATH
    if (-not (Test-Path $binDir)) { $binDir = $StateDir }
    $stable = (Invoke-RestMethod -Uri 'https://dl.k8s.io/release/stable.txt').Trim()
    $url    = "https://dl.k8s.io/release/$stable/bin/windows/amd64/kubectl.exe"
    $dest   = Join-Path $binDir 'kubectl.exe'
    Write-Log "Downloading kubectl $stable from $url ..." -Level STEP
    Invoke-WebRequest -Uri $url -OutFile $dest
    Write-Log "Installed kubectl to $dest." -Level INFO
}

# Set-LanExposure publishes the WSL2 VM's ports 80/443 to the LAN via netsh
# portproxy plus firewall rules, so Traefik ingress is reachable from other hosts.
# WSL2 is NAT'd, so this proxy is required and must be refreshed if the WSL IP changes.
function Set-LanExposure {
    Write-Log 'Configuring LAN exposure (portproxy + firewall for 80/443)...' -Level STEP

    $wslIp = (& wsl.exe -d $Distro -u root -- bash -lc "hostname -I | awk '{print `$1}'").Trim()
    if (-not $wslIp) {
        Write-Log 'Could not determine WSL IP; skipping LAN exposure.' -Level WARN
        return
    }
    Write-Log "WSL2 VM IP: $wslIp" -Level INFO

    foreach ($port in 80, 443) {
        # Reset any stale mapping, then point the port at the current WSL IP.
        Invoke-Native -File 'netsh' -Arguments @(
            'interface', 'portproxy', 'delete', 'v4tov4',
            "listenport=$port", 'listenaddress=0.0.0.0'
        ) -AllowFailure | Out-Null
        Invoke-Native -File 'netsh' -Arguments @(
            'interface', 'portproxy', 'add', 'v4tov4',
            "listenport=$port", 'listenaddress=0.0.0.0',
            "connectport=$port", "connectaddress=$wslIp"
        ) | Out-Null

        $ruleName = "k3s WSL ingress $port"
        if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
                -Protocol TCP -LocalPort $port | Out-Null
            Write-Log "Opened firewall for TCP $port." -Level INFO
        }
    }

    # The WSL IP changes across reboots. Install a lightweight logon task that
    # re-points the portproxy so LAN access keeps working without a full re-run.
    Install-LanRefreshTask
    Write-Log 'LAN exposure configured.' -Level INFO
}

# Install-LanRefreshTask writes and schedules a tiny helper that re-syncs the
# portproxy mappings to the current WSL IP at each logon.
function Install-LanRefreshTask {
    $helper = Join-Path $StateDir 'refresh-portproxy.ps1'
    $body = @"
# Auto-generated by Install-K3sCluster.ps1 - re-points WSL portproxy to the
# current WSL2 IP so LAN ingress survives reboots (WSL IPs are dynamic).
`$ip = (& wsl.exe -d $Distro -u root -- bash -lc "hostname -I | awk '{print `$1}'").Trim()
if (`$ip) {
    foreach (`$p in 80,443) {
        netsh interface portproxy delete v4tov4 listenport=`$p listenaddress=0.0.0.0 2>`$null
        netsh interface portproxy add    v4tov4 listenport=`$p listenaddress=0.0.0.0 connectport=`$p connectaddress=`$ip
    }
}
"@
    Set-Content -Path $helper -Value $body -Encoding UTF8

    $taskName = 'K3sPortProxyRefresh'
    $ps       = (Get-Command powershell.exe).Source
    $action   = New-ScheduledTaskAction -Execute $ps -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$helper`""
    $trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $principal= New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Force | Out-Null
    Write-Log "Installed logon task '$taskName' to keep LAN portproxy current." -Level INFO
}

# Show-Summary prints the LAN IP and the verification / next-step commands.
function Show-Summary {
    # Prefer a real LAN IPv4 (skip loopback, WSL, and APIPA ranges).
    $lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.InterfaceAlias -notlike '*WSL*' -and
            $_.InterfaceAlias -notlike '*Loopback*'
        } |
        Sort-Object -Property SkipAsSource |
        Select-Object -First 1 -ExpandProperty IPAddress)
    if (-not $lanIp) { $lanIp = '<your-LAN-IP>' }

    $line = ('=' * 72)
    Write-Host ''
    Write-Host $line -ForegroundColor Green
    Write-Host ' k3s single-node cluster is ready.' -ForegroundColor Green
    Write-Host $line -ForegroundColor Green
    Write-Host ''
    Write-Host 'Verify the cluster (from Windows PowerShell or inside WSL):' -ForegroundColor Cyan
    Write-Host '    kubectl get nodes'
    Write-Host '    kubectl get pods -A'
    Write-Host '    kubectl get ingress'
    Write-Host '    kubectl get pvc'
    Write-Host ''
    Write-Host 'Deploy the sample apps (from inside WSL):' -ForegroundColor Cyan
    Write-Host '    wsl -d ' + $Distro
    Write-Host "    kubectl apply -f ~/cluster/manifests/"
    Write-Host ''
    Write-Host 'Reach services from your LAN:' -ForegroundColor Cyan
    Write-Host "    This machine's LAN IP : $lanIp"
    Write-Host '    Traefik ingress is published on TCP 80/443 via portproxy.'
    Write-Host "    Point DNS / hosts entries at $lanIp, e.g. add on a client:"
    Write-Host "        $lanIp  web.local"
    Write-Host '    then browse:  http://web.local/'
    Write-Host ''
    Write-Host "Log file: $LogFile" -ForegroundColor Gray
    Write-Host ''

    Write-Log "Summary printed. LAN IP: $lanIp" -Level INFO
}

# ===========================================================================
# Orchestration
# ===========================================================================

function Main {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    Write-Log "==== k3s setup started (stage: $Stage, distro: $Distro, cluster-user: $ClusterUser) ====" -Level STEP

    Assert-Admin
    Assert-WindowsVersion

    switch ($Stage) {
        'Prereqs' { Invoke-StagePrereqs }
        'Wsl'     { Invoke-StageWsl;     Invoke-StageCluster }
        'Cluster' { Invoke-StageCluster }
        'All'     { Invoke-StagePrereqs; Invoke-StageWsl; Invoke-StageCluster }
    }

    Write-Log '==== k3s setup completed successfully ====' -Level STEP
}

try {
    Main
} catch {
    # Central catch-all so any unexpected terminating error is logged clearly.
    Write-Log $_.Exception.Message -Level ERROR
    Write-Log ($_.ScriptStackTrace) -Level ERROR
    Fail 'Unhandled error during setup (see stack trace above).'
}
