param([switch]$LibraryOnly)

$ErrorActionPreference = 'Stop'

function Read-WikiJson([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-WikiHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Resolve-WikiPath([string]$Root, [string]$Relative) {
    if ($Relative -notmatch '^(index\.html|(update|install)-wiki\.ps1|(打开|更新|下载)Wiki\.cmd|使用说明\.txt|assets/(images/icon|official-ui)/[A-Za-z0-9_.-]+\.(png|gif))$' -or
        $Relative.Split('/') -contains '..' -or $Relative -match '//') {
        throw "更新文件路径不合法：$Relative"
    }
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $target = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $target.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) { throw '更新文件越出 Wiki 目录' }
    $current = $target
    while ($current -and $current.Length -ge $rootPath.TrimEnd('\', '/').Length) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Wiki 目录包含链接，请移到普通目录后更新' }
        }
        $current = Split-Path -Parent $current
    }
    return $target
}

function Download-WikiFile([string]$Url, [string]$Destination) {
    $request = [Net.WebRequest]::Create($Url)
    $request.Timeout = 45000
    $request.ReadWriteTimeout = 45000
    $request.UserAgent = 'LAH-Portable-Wiki'
    $response = $request.GetResponse()
    try {
        $inputStream = $response.GetResponseStream()
        $outputStream = [IO.File]::Create($Destination)
        try { $inputStream.CopyTo($outputStream) }
        finally { $outputStream.Dispose(); $inputStream.Dispose() }
    } finally { $response.Dispose() }
}

function Clear-WikiTransaction([string]$Root) {
    $transaction = Join-Path ([IO.Path]::GetFullPath($Root)) '.wiki-update'
    if (Test-Path -LiteralPath $transaction) {
        # Never recursively remove a linked directory.
        $items = @(Get-Item -LiteralPath $transaction -Force) + @(Get-ChildItem -LiteralPath $transaction -Recurse -Force)
        if ($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw '更新临时目录包含链接' }
        Remove-Item -LiteralPath $transaction -Recurse -Force
    }
}

function Restore-WikiTransaction([string]$Root) {
    $transaction = Join-Path $Root '.wiki-update'
    $journalPath = Join-Path $transaction 'journal.json'
    if (-not (Test-Path -LiteralPath $journalPath)) { Clear-WikiTransaction $Root; return }
    $journal = Read-WikiJson $journalPath
    $statePath = Join-Path $Root '.wiki-state.json'
    if (Test-Path -LiteralPath (Join-Path $transaction 'committed')) {
        Clear-WikiTransaction $Root
        return
    }
    foreach ($operation in $journal.operations) {
        $target = Resolve-WikiPath $Root $operation.path
        if ($operation.existed) {
            $backup = Join-Path $transaction ('backup/' + $operation.path)
            if (-not (Test-Path -LiteralPath $backup)) { throw '恢复文件缺失，请保留更新临时目录' }
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath $backup -Destination $target -Force
        } elseif (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    Copy-Item -LiteralPath (Join-Path $transaction 'previous-state.json') -Destination $statePath -Force
    Clear-WikiTransaction $Root
    Write-Host '已恢复上一次中断的更新，继续检查新版。'
}

function Invoke-WikiUpdate([string]$Root) {
    $Root = [IO.Path]::GetFullPath($Root)
    $lock = [IO.File]::Open((Join-Path $Root '.wiki-update.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        # Check the directory itself before recovery or writes.
        Resolve-WikiPath $Root 'index.html' | Out-Null
        Restore-WikiTransaction $Root
        $channel = Read-WikiJson (Join-Path $Root '.wiki-channel.json')
        if ($channel.repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw '更新仓库配置不合法' }
        $base = 'https://github.com/' + $channel.repository + '/releases/'
        if ($channel.manifestUrl -cne ($base + 'latest/download/wiki-manifest.json')) { throw '更新源配置不合法' }
        $transaction = Join-Path $Root '.wiki-update'
        New-Item -ItemType Directory -Path $transaction | Out-Null
        Write-Host '正在检查 Wiki 更新…'
        $manifestPath = Join-Path $transaction 'new-state.json'
        Download-WikiFile $channel.manifestUrl $manifestPath
        $manifest = Read-WikiJson $manifestPath
        if ($manifest.schemaVersion -ne 1 -or $manifest.version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$' -or @($manifest.files).Count -eq 0) { throw '更新清单格式不受支持' }
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        $changed = @()
        foreach ($file in $manifest.files) {
            $target = Resolve-WikiPath $Root $file.path
            if (-not $seen.Add($file.path) -or $file.sha256 -cnotmatch '^[0-9a-f]{64}$' -or
                $file.size -lt 0 -or $file.size -gt 134217728 -or $file.downloadSize -le 0 -or
                $file.url -cne ($base + 'download/' + $manifest.version + '/blob-' + $file.sha256 + '.gz')) { throw '更新清单含有无效文件' }
            if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or (Get-WikiHash $target) -cne $file.sha256) { $changed += $file }
        }
        if (-not $seen.Contains('index.html') -or -not $seen.Contains('update-wiki.ps1')) { throw '更新清单缺少 Wiki 入口' }
        $statePath = Join-Path $Root '.wiki-state.json'
        $previous = Read-WikiJson $statePath
        $removed = @($previous.files | Where-Object { -not $seen.Contains($_.path) })
        foreach ($file in $removed) { Resolve-WikiPath $Root $file.path | Out-Null }
        $bytes = ($changed | Measure-Object -Property downloadSize -Sum).Sum
        Write-Host ("版本 {0}；需下载 {1} 个文件，约 {2:N2} MB。" -f $manifest.version, $changed.Count, ($bytes / 1000000))
        $archive = $null
        try {
            if (@($previous.files).Count -eq 0 -and $changed.Count -gt 0) {
                Write-Host '首次下载 Wiki 完整内容；以后的更新只下载变更文件。'
                $archivePath = Join-Path $transaction 'initial.zip'
                Download-WikiFile ($base + 'download/' + $manifest.version + '/Live-A-Hero-Wiki.zip') $archivePath
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
            }
            $done = 0
            foreach ($file in $changed) {
                $done++
                Write-Progress -Activity '下载 Wiki 更新' -Status "$done / $($changed.Count)" -PercentComplete (100 * $done / $changed.Count)
                $staged = Join-Path $transaction ('new/' + $file.path)
                New-Item -ItemType Directory -Path (Split-Path -Parent $staged) -Force | Out-Null
                $compressedStream = $null
                if ($archive) {
                    $entry = $archive.GetEntry('Live-A-Hero-Wiki/' + $file.path)
                    if (-not $entry) { throw "完整包缺少文件：$($file.path)" }
                    $inputStream = $entry.Open()
                } else {
                    $compressed = Join-Path $transaction 'download.gz'
                    Download-WikiFile $file.url $compressed
                    if ((Get-Item -LiteralPath $compressed).Length -ne $file.downloadSize) { throw "下载不完整：$($file.path)" }
                    $compressedStream = [IO.File]::OpenRead($compressed)
                    $inputStream = New-Object IO.Compression.GZipStream($compressedStream, [IO.Compression.CompressionMode]::Decompress)
                }
                try {
                    $outputStream = [IO.File]::Create($staged)
                    try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose() }
                } finally {
                    $inputStream.Dispose()
                    if ($compressedStream) { $compressedStream.Dispose() }
                }
                if ((Get-Item -LiteralPath $staged).Length -ne $file.size -or (Get-WikiHash $staged) -cne $file.sha256) { throw "文件校验失败：$($file.path)" }
            }
        } finally { if ($archive) { $archive.Dispose() } }
        Write-Progress -Activity '下载 Wiki 更新' -Completed
        $operations = @()
        foreach ($file in @($changed) + @($removed)) {
            $target = Resolve-WikiPath $Root $file.path
            $existed = Test-Path -LiteralPath $target -PathType Leaf
            if ($existed) {
                $backup = Join-Path $transaction ('backup/' + $file.path)
                New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
                Copy-Item -LiteralPath $target -Destination $backup
            }
            $operations += @{path=$file.path; existed=$existed}
        }
        Copy-Item -LiteralPath $statePath -Destination (Join-Path $transaction 'previous-state.json')
        $journal = @{operations=$operations}
        $journal | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $transaction 'journal.pending') -Encoding UTF8
        Move-Item -LiteralPath (Join-Path $transaction 'journal.pending') -Destination (Join-Path $transaction 'journal.json')
        foreach ($file in $changed) {
            $target = Resolve-WikiPath $Root $file.path
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $transaction ('new/' + $file.path)) -Destination $target -Force
        }
        foreach ($file in $removed) {
            $target = Resolve-WikiPath $Root $file.path
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
        }
        # Atomic replacement of the version record is the transaction commit.
        [IO.File]::Replace($manifestPath, $statePath, (Join-Path $transaction 'committed-previous-state.json'))
        [IO.File]::WriteAllText((Join-Path $transaction 'committed'), 'complete')
        Clear-WikiTransaction $Root
        Write-Host 'Wiki 已是最新版本。请刷新已打开的网页。'
        return @{version=$manifest.version; downloaded=$changed.Count; downloadBytes=$bytes; removed=$removed.Count}
    } catch {
        Restore-WikiTransaction $Root
        throw
    } finally {
        $lock.Dispose()
    }
}

if (-not $LibraryOnly) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding
    try { Invoke-WikiUpdate $PSScriptRoot | Out-Null }
    catch { Write-Host ("更新未完成：" + $_.Exception.Message); exit 1 }
}
