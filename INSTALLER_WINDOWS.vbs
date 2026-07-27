Option Explicit

Dim shell, fso, folder, appData, backup, configFile, choice
Dim dtuHost, dinkyHost, json, outputFile, shortcut, desktop, result, q

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
q = Chr(34)
folder = fso.GetParentFolderName(WScript.ScriptFullName)
appData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\BoiteNoireHoymiles"
backup = appData & "\sauvegarde_avant_mise_a_jour"
configFile = appData & "\config_v5.json"

choice = MsgBox("Installer ou mettre a jour Boite noire Hoymiles 7.0.1 ?" & vbCrLf & vbCrLf & "Les historiques et les reglages deja presents seront conserves.", vbOKCancel + vbQuestion, "Confirmer l'installation")
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

If Not fso.FileExists(configFile) Then
    choice = MsgBox("Choisissez le reseau du DTU." & vbCrLf & vbCrLf & "Oui : Wi-Fi dedie du DTU (10.10.100.254, deux Wi-Fi)." & vbCrLf & "Non : DTU relie a la Livebox en Ethernet ; Dinky et PC sur le Wi-Fi de la Livebox.", vbYesNoCancel + vbQuestion, "Boite noire Hoymiles - connexion")
    If choice = vbCancel Then WScript.Quit 0
    If choice = vbYes Then
        dtuHost = "10.10.100.254"
    Else
        dtuHost = Trim(InputBox("Adresse IP du DTU indiquee par la Livebox :", "DTU sur Livebox"))
        If dtuHost = "" Then
            MsgBox "Installation annulee : l'adresse IP du DTU est necessaire.", vbExclamation, "Boite noire Hoymiles"
            WScript.Quit 1
        End If
    End If
    dinkyHost = Trim(InputBox("Adresse IP du Dinky :", "Dinky sur Livebox", "192.168.1.126"))
    If dinkyHost = "" Then dinkyHost = "192.168.1.126"
    json = "{" & q & "dtu_host" & q & ":" & q & dtuHost & q & "," & _
           q & "linky" & q & ":{" & q & "enabled" & q & ":true," & _
           q & "mode" & q & ":" & q & "dinky_http" & q & "," & _
           q & "host" & q & ":" & q & dinkyHost & q & "," & _
           q & "port" & q & ":80," & q & "timeout_s" & q & ":2," & _
           q & "path" & q & ":" & q & "Status 8" & q & "}," & _
           q & "tarifs_edf" & q & ":{" & q & "hp_eur_kwh" & q & ":0.0," & _
           q & "hc_eur_kwh" & q & ":0.0," & q & "abonnement_mensuel_eur" & q & ":0.0," & _
           q & "abonnement_journalier_eur" & q & ":0.63," & q & "plages_hc" & q & ":" & q & q & "," & _
           q & "ddsu_import_positif" & q & ":true}," & _
           q & "dtu_wifi_recovery" & q & ":{" & q & "enabled" & q & ":false," & _
           q & "interface" & q & ":" & q & q & "," & q & "profile" & q & ":" & q & q & "," & _
           q & "after_minutes" & q & ":30}," & q & "releves_edf" & q & ":{}}"
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
