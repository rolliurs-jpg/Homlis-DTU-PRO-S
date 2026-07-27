Option Explicit

Dim shell, fso, folder, appData, backup, configFile, choice
Dim dtuHost, dinkyHost, json, outputFile, inputFile, shortcut, desktop, result, q, modeFile, dtuMode, chooser, re, existingConfig

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
q = Chr(34)
folder = fso.GetParentFolderName(WScript.ScriptFullName)
appData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\BoiteNoireHoymiles"
backup = appData & "\sauvegarde_avant_mise_a_jour"
configFile = appData & "\config_v5.json"

choice = MsgBox("Installer ou mettre a jour Boite noire Hoymiles 7.0.3 ?" & vbCrLf & vbCrLf & "Les historiques et les reglages deja presents seront conserves.", vbOKCancel + vbQuestion, "Confirmer l'installation")
If choice <> vbOK Then WScript.Quit 0

' Installation des dépendances sans fenêtre de terminal.
result = shell.Run("py.exe -3 -m pip install -r " & Chr(34) & folder & "\requirements.txt" & Chr(34), 0, True)
If result <> 0 Then
    MsgBox "Python ou les dependances sont introuvables." & vbCrLf & "Installez Python 3.10 ou plus depuis python.org, puis relancez cet installateur.", vbExclamation, "Boite noire Hoymiles"
    WScript.Quit 1
End If

If Not fso.FolderExists(appData) Then fso.CreateFolder(appData)
If Not fso.FolderExists(backup) Then fso.CreateFolder(backup)
If fso.FileExists(configFile) Then fso.CopyFile configFile, backup & "\config_v5.json", True
If fso.FileExists(appData & "\hoymiles_log.csv") Then fso.CopyFile appData & "\hoymiles_log.csv", backup & "\hoymiles_log.csv", True
If fso.FileExists(appData & "\linky_index_log.csv") Then fso.CopyFile appData & "\linky_index_log.csv", backup & "\linky_index_log.csv", True

existingConfig = fso.FileExists(configFile)
choice = vbNo
If existingConfig Then
    choice = MsgBox("Les reglages existants sont conserves." & vbCrLf & vbCrLf & "Voulez-vous modifier la connexion du DTU ?", vbYesNoCancel + vbQuestion, "Boite noire Hoymiles - connexion DTU")
    If choice = vbCancel Then WScript.Quit 0
End If

If (Not existingConfig) Or choice = vbYes Then
    chooser = folder & "\CHOISIR_RESEAU.ps1"
    modeFile = shell.ExpandEnvironmentStrings("%TEMP%") & "\BoiteNoireHoymiles_mode_reseau.txt"
    If fso.FileExists(modeFile) Then fso.DeleteFile modeFile, True
    result = shell.Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & q & chooser & q & " -ResultPath " & q & modeFile & q, 0, True)
    If Not fso.FileExists(modeFile) Then WScript.Quit 0

    Set outputFile = fso.OpenTextFile(modeFile, 1, False)
    dtuMode = UCase(Trim(outputFile.ReadAll))
    outputFile.Close
    fso.DeleteFile modeFile, True

    If dtuMode = "WIFI" Then
        dtuHost = "10.10.100.254"
    ElseIf dtuMode = "LAN" Then
        dtuHost = Trim(InputBox("Adresse IP reellement attribuee au DTU par la box :", "Ethernet — DTU-LAN sur la box"))
        If dtuHost = "" Then
            MsgBox "Installation annulee : l'adresse IP du DTU est necessaire.", vbExclamation, "Boite noire Hoymiles"
            WScript.Quit 1
        End If
    Else
        WScript.Quit 0
    End If
    If existingConfig Then
        Set inputFile = fso.OpenTextFile(configFile, 1, False)
        json = inputFile.ReadAll
        inputFile.Close
        Set re = New RegExp
        re.Global = False
        re.Pattern = q & "dtu_host" & q & ":" & q & "[^" & q & "]*" & q
        json = re.Replace(json, q & "dtu_host" & q & ":" & q & dtuHost & q)
    Else
        dinkyHost = Trim(InputBox("Adresse IP du Dinky :", "Dinky sur Livebox", "192.168.1.126"))
        If dinkyHost = "" Then dinkyHost = "192.168.1.126"
        json = "{" & q & "dtu_host" & q & ":" & q & dtuHost & q & "," & _
               q & "linky" & q & ":{" & q & "enabled" & q & ":true," & _
               q & "mode" & q & ":" & q & "dinky_http" & q & "," & _
               q & "host" & q & ":" & q & dinkyHost & q & "," & _
               q & "port" & q & ":80," & q & "timeout_s" & q & ":2," & _
               q & "path" & q & ":" & q & "Status 8" & q & "}," & _
               q & "dtu_lan_limit_pct" & q & ":110.0," & _
               q & "tarifs_edf" & q & ":{" & q & "hp_eur_kwh" & q & ":0.0," & _
               q & "hc_eur_kwh" & q & ":0.0," & q & "abonnement_mensuel_eur" & q & ":0.0," & _
               q & "abonnement_journalier_eur" & q & ":0.63," & q & "plages_hc" & q & ":" & q & q & "," & _
               q & "ddsu_import_positif" & q & ":true}," & _
               q & "dtu_wifi_recovery" & q & ":{" & q & "enabled" & q & ":false," & _
               q & "interface" & q & ":" & q & q & "," & q & "profile" & q & ":" & q & q & "," & _
               q & "after_minutes" & q & ":30}," & q & "releves_edf" & q & ":{}}"
    End If
    Set outputFile = fso.CreateTextFile(configFile, True, False)
    outputFile.Write json
    outputFile.Close
End If

fso.CopyFile folder & "\boite_noire_hoymiles.py", appData & "\boite_noire_hoymiles.py", True
fso.CopyFile folder & "\fond_solaire.png", appData & "\fond_solaire.png", True
fso.CopyFile folder & "\icone_panneau_solaire.ico", appData & "\icone_panneau_solaire.ico", True
fso.CopyFile folder & "\LANCER.vbs", appData & "\LANCER.vbs", True

desktop = shell.SpecialFolders("Desktop")
Set shortcut = shell.CreateShortcut(desktop & "\Boite noire Hoymiles.lnk")
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
shortcut.Arguments = Chr(34) & appData & "\LANCER.vbs" & Chr(34)
shortcut.WorkingDirectory = appData
shortcut.IconLocation = appData & "\icone_panneau_solaire.ico,0"
shortcut.Save
MsgBox "Installation terminee." & vbCrLf & "Un raccourci Boite noire Hoymiles a ete cree sur le Bureau." & vbCrLf & vbCrLf & "Les historiques et reglages existants sont conserves.", vbInformation, "Boite noire Hoymiles"
