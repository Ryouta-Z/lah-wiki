$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [Windows.Forms.Application]::EnableVisualStyles()
    $form = New-Object Windows.Forms.Form
    $form.Text = 'Live A Hero · 下载内容'
    $form.ClientSize = New-Object Drawing.Size(480, 220)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $font = New-Object Drawing.Font('Microsoft YaHei UI', 10)
    $form.Font = $font
    $heading = New-Object Windows.Forms.Label
    $heading.Text = '请选择要下载的内容'
    $heading.Location = New-Object Drawing.Point(24, 20)
    $heading.Size = New-Object Drawing.Size(430, 28)
    $form.Controls.Add($heading)
    $wiki = New-Object Windows.Forms.CheckBox
    $wiki.Text = 'Wiki：角色、技能、标签和头像（约 13 MB）'
    $wiki.Checked = $true
    $wiki.Location = New-Object Drawing.Point(24, 60)
    $wiki.Size = New-Object Drawing.Size(430, 32)
    $form.Controls.Add($wiki)
    $note = New-Object Windows.Forms.Label
    $note.Text = '下载后可离线使用。签名、收藏卡、立绘等补充素材暂不提供。'
    $note.Location = New-Object Drawing.Point(24, 105)
    $note.Size = New-Object Drawing.Size(430, 44)
    $form.Controls.Add($note)
    $download = New-Object Windows.Forms.Button
    $download.Text = '下载并打开'
    $download.Location = New-Object Drawing.Point(232, 165)
    $download.Size = New-Object Drawing.Size(110, 34)
    $download.DialogResult = [Windows.Forms.DialogResult]::OK
    $form.Controls.Add($download)
    $cancel = New-Object Windows.Forms.Button
    $cancel.Text = '取消'
    $cancel.Location = New-Object Drawing.Point(354, 165)
    $cancel.Size = New-Object Drawing.Size(100, 34)
    $cancel.DialogResult = [Windows.Forms.DialogResult]::Cancel
    $form.Controls.Add($cancel)
    $form.AcceptButton = $download
    $form.CancelButton = $cancel
    $wiki.Add_CheckedChanged({ $download.Enabled = $wiki.Checked })
    $choice = $form.ShowDialog()
    $form.Dispose()
    $font.Dispose()
    if ($choice -ne [Windows.Forms.DialogResult]::OK) { exit 0 }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    . (Join-Path $PSScriptRoot 'update-wiki.ps1') -LibraryOnly
    Invoke-WikiUpdate $PSScriptRoot | Out-Null
    Start-Process (Join-Path $PSScriptRoot 'index.html')
} catch {
    Write-Host ('下载未完成：' + $_.Exception.Message)
    if ('Windows.Forms.MessageBox' -as [type]) { [Windows.Forms.MessageBox]::Show('下载未完成，请检查网络后重试。' + [Environment]::NewLine + $_.Exception.Message, 'Live A Hero Wiki') | Out-Null }
    exit 1
}
