Option Explicit

Dim shell, fso, folder, appData, backup, configFile, choice
Dim dtuHost, dinkyHost, json, stream, shortcut, desktop, result

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
appData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\BoiteNoireHoymiles"
backup = appData & "\sauvegarde_avant_mise_a_jour"
configFile = appData & "\config_v5.json"

choice = MsgBox( _
    "Installer ou mettre a jour Boite noire Hoymiles 7.0 ?" & vbCrLf & vbCrLf & _
    "Les historiques et les reglages deja presents seront conserves.", _
    vbOKCancel + vbQuestion, "Confirmer l'installation")
If choice <> vbOK Then WScript.Quit 0

' Les dependances sont installees en arriere-plan : aucune console ne s'affiche.
result = shell.Run("py.exe -3 -m pip install -r """ & folder & "\requirements.txt"""", 0, True)
If result <> 0 Then
    MsgBox "Python ou les dependances sont introuvables." & vbCrLf & _
           "Installez Python 3.10 ou plus depuis python.org, puis relancez cet installateur.", _
           vbExclamation, "Boite noire Hoymiles"
    WScript.Quit 1
End If

If Not fso.FolderExists(appData) Then fso.CreateFolder(appData)
If Not fso.FolderExists(backup) Then fso.CreateFolder(backup)

' Copie de sauvegarde uniquement : les fichiers actifs ne sont jamais effaces.
If fso.FileExists(configFile) Then fso.CopyFile configFile, backup & "\config_v5.json", True
If fso.FileExists(appData & "\hoymiles_log.csv") Then fso.CopyFile appData & "\hoymiles_log.csv", backup & "\hoymiles_log.csv", True
If fso.FileExists(appData & "\linky_index_log.csv") Then fso.CopyFile appData & "\linky_index_log.csv", backup & "\linky_index_log.csv", True

If Not fso.FileExists(configFile) Then
    choice = MsgBox( _
        "Choisissez le reseau du DTU." & vbCrLf & vbCrLf & _
        "Oui : Wi-Fi dedie du DTU (10.10.100.254, deux Wi-Fi)." & vbCrLf & _
        "Non : DTU et Dinky sur la Livebox (Ethernet ou Wi-Fi Livebox).", _
        vbYesNoCancel + vbQuestion, "Boite noire Hoymiles - connexion")
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

    json = "{""dtu_host"":""" & dtuHost & """," & _
           """linky"":{""enabled"":true,""mode"":""dinky_http"",""host"":""" & dinkyHost & """,""port"":80,""timeout_s"":2,""path"":""Status 8""}," & _
           """tarifs_edf"":{""hp_eur_kwh"":0.0,""hc_eur_kwh"":0.0,""abonnement_mensuel_eur"":0.0,""abonnement_journalier_eur"":0.63,""plages_hc"":""",""ddsu_import_positif"":true}," & _
           """dtu_wifi_recovery"":{""enabled"":false,""interface"":""",""profile"":""",""after_minutes"":30},""releves_edf"":{}}"
    Set stream = fso.CreateTextFile(configFile, True, False)
    stream.Write json
    stream.Close
End If

fso.CopyFile folder & "\boite_noire_hoymiles.py", appData & "\boite_noire_hoymiles.py", True
fso.CopyFile folder & "\fond_solaire.png", appData & "\fond_solaire.png", True
fso.CopyFile folder & "\icone_panneau_solaire.ico", appData & "\icone_panneau_solaire.ico", True
fso.CopyFile folder & "\LANCER.vbs", appData & "\LANCER.vbs", True

desktop = shell.SpecialFolders("Desktop")
Set shortcut = shell.CreateShortcut(desktop & "\Boite noire Hoymiles.lnk")
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
shortcut.Arguments = """" & appData & "\LANCER.vbs""""
shortcut.WorkingDirectory = appData
shortcut.IconLocation = appData & "\icone_panneau_solaire.ico,0"
shortcut.Save

MsgBox "Installation terminee." & vbCrLf & _
       "Un raccourci Boite noire Hoymiles a ete cree sur le Bureau." & vbCrLf & vbCrLf & _
       "Les historiques et reglages existants sont conserves.", _
       vbInformation, "Boite noire Hoymiles"
