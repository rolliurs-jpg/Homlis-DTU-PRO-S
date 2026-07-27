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

command = "pyw.exe -3 " & Chr(34) & scriptPath & Chr(34)
shell.Run command, 0, False
