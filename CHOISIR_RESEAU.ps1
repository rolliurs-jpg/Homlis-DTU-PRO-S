param(
    [Parameter(Mandatory = $true)]
    [string]$ResultPath
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "Boîte noire Hoymiles - connexion DTU"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.ClientSize = New-Object System.Drawing.Size(650, 305)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = "Choisissez la connexion du DTU Pro-S"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(25, 20)
$title.AutoSize = $true
$form.Controls.Add($title)

$hint = New-Object System.Windows.Forms.Label
$hint.Text = "Cochez une seule option. Le Dinky 4 reste connecté en Wi-Fi sur votre box."
$hint.Location = New-Object System.Drawing.Point(27, 53)
$hint.AutoSize = $true
$form.Controls.Add($hint)

$wifi = New-Object System.Windows.Forms.CheckBox
$wifi.Text = "DTU-WIFI"
$wifi.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$wifi.Location = New-Object System.Drawing.Point(28, 95)
$wifi.AutoSize = $true
$form.Controls.Add($wifi)

$wifiText = New-Object System.Windows.Forms.Label
$wifiText.Text = "DTU sur son Wi-Fi propre (2 cartes Wi-Fi nécessaires : box/Dinky + DTU)."
$wifiText.Location = New-Object System.Drawing.Point(55, 125)
$wifiText.AutoSize = $true
$form.Controls.Add($wifiText)

$lan = New-Object System.Windows.Forms.CheckBox
$lan.Text = "DTU-LAN"
$lan.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lan.Location = New-Object System.Drawing.Point(28, 165)
$lan.AutoSize = $true
$form.Controls.Add($lan)

$lanText = New-Object System.Windows.Forms.Label
$lanText.Text = "DTU relié à la box par câble Ethernet (une seule connexion réseau : DTU et Dinky 4 sur la box)."
$lanText.Location = New-Object System.Drawing.Point(55, 195)
$lanText.AutoSize = $true
$form.Controls.Add($lanText)

$continue = New-Object System.Windows.Forms.Button
$continue.Text = "Continuer"
$continue.Size = New-Object System.Drawing.Size(120, 34)
$continue.Location = New-Object System.Drawing.Point(385, 250)
$continue.Enabled = $false
$form.Controls.Add($continue)

$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = "Annuler"
$cancel.Size = New-Object System.Drawing.Size(120, 34)
$cancel.Location = New-Object System.Drawing.Point(515, 250)
$form.Controls.Add($cancel)

$wifi.Add_CheckedChanged({
    if ($wifi.Checked) { $lan.Checked = $false }
    $continue.Enabled = $wifi.Checked -or $lan.Checked
})
$lan.Add_CheckedChanged({
    if ($lan.Checked) { $wifi.Checked = $false }
    $continue.Enabled = $wifi.Checked -or $lan.Checked
})

$continue.Add_Click({
    if ($wifi.Checked) {
        Set-Content -LiteralPath $ResultPath -Value "WIFI" -NoNewline -Encoding ascii
    } elseif ($lan.Checked) {
        Set-Content -LiteralPath $ResultPath -Value "LAN" -NoNewline -Encoding ascii
    }
    $form.Close()
})
$cancel.Add_Click({ $form.Close() })

[void]$form.ShowDialog()
