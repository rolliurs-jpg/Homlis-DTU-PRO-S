Option Explicit

Dim shell, fso, folder, scriptPath, classicLauncher, webLauncher, answer
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = folder & "\boite_noire_hoymiles.py"
classicLauncher = folder & "\LANCER.vbs"
webLauncher = folder & "\LANCER_INTERFACE_WEB.vbs"

If Not fso.FileExists(scriptPath) Then
    MsgBox "Le fichier du logiciel est introuvable.", vbExclamation, "Boite noire Hoymiles"
    WScript.Quit 1
End If

answer = MsgBox( _
    "Choisissez l'interface a ouvrir :" & vbCrLf & vbCrLf & _
    "OUI  = Nouvelle interface web" & vbCrLf & _
    "NON = Ancien logiciel avec sa fenetre" & vbCrLf & _
    "ANNULER = Ne rien ouvrir", _
    vbYesNoCancel + vbQuestion, "Boite noire Hoymiles")

If answer = vbYes Then
    If Not MainProgramRunning() Then
        shell.Run "wscript.exe " & Chr(34) & webLauncher & Chr(34), 0, False
        WScript.Sleep 1800
    End If
    shell.Run "http://127.0.0.1:8765", 1, False
ElseIf answer = vbNo Then
    If ClassicProgramRunning() Then
        MsgBox "L'ancien logiciel est deja ouvert.", vbInformation, "Boite noire Hoymiles"
        WScript.Quit 0
    End If
    StopInvisibleProgram
    WScript.Sleep 1200
    shell.Run "wscript.exe " & Chr(34) & classicLauncher & Chr(34), 0, False
End If

Function MainProgramRunning()
    MainProgramRunning = FindProgram(False)
End Function

Function ClassicProgramRunning()
    ClassicProgramRunning = FindProgram(True)
End Function

Function FindProgram(classicOnly)
    Dim service, processes, process, command
    FindProgram = False
    On Error Resume Next
    Set service = GetObject("winmgmts:\\.\root\cimv2")
    Set processes = service.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'")
    For Each process In processes
        If Not IsNull(process.CommandLine) Then
            command = LCase(CStr(process.CommandLine))
            If InStr(command, LCase(scriptPath)) > 0 Then
                If Not classicOnly Or InStr(command, "--web-only") = 0 Then
                    FindProgram = True
                    Exit For
                End If
            End If
        End If
    Next
    On Error GoTo 0
End Function

Sub StopInvisibleProgram()
    Dim service, processes, process, command
    On Error Resume Next
    Set service = GetObject("winmgmts:\\.\root\cimv2")
    Set processes = service.ExecQuery("SELECT * FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'")
    For Each process In processes
        If Not IsNull(process.CommandLine) Then
            command = LCase(CStr(process.CommandLine))
            If InStr(command, LCase(scriptPath)) > 0 And InStr(command, "--web-only") > 0 Then
                process.Terminate
            End If
        End If
    Next
    On Error GoTo 0
End Sub
