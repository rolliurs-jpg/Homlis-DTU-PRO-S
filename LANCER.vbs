Option Explicit

Dim shell, fso, folder, scriptPath, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = folder & "\boite_noire_hoymiles.py"

If Not fso.FileExists(scriptPath) Then
    MsgBox "Le fichier du logiciel est introuvable.", vbExclamation, "Boite noire Hoymiles"
    WScript.Quit 1
End If

' pyw lance Python sans fenêtre de terminal.
command = "pyw.exe -3 """ & scriptPath & """"
shell.Run command, 0, False
