Option Explicit
' Arranque sin consola (Inicio de Windows / acceso directo).
' Preferencia: .venv\Scripts\pythonw.exe → pythonw → pyw → python (oculto).
Dim sh, fso, dir, launcher, venvW, venvC, cmd, q
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
q = Chr(34)
launcher = dir & "\launcher.py"
If Not fso.FileExists(launcher) Then WScript.Quit 1

venvW = dir & "\.venv\Scripts\pythonw.exe"
venvC = dir & "\.venv\Scripts\python.exe"

If fso.FileExists(venvW) Then
  cmd = q & venvW & q & " " & q & launcher & q
  sh.Run cmd, 0, False
  WScript.Quit 0
End If

' pythonw en PATH
On Error Resume Next
Dim which
which = sh.ExpandEnvironmentStrings("%SystemRoot%\py.exe")
' Probar pythonw
cmd = "pythonw " & q & launcher & q
Err.Clear
sh.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0
Err.Clear

cmd = "pyw -3 " & q & launcher & q
sh.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0
Err.Clear

If fso.FileExists(venvC) Then
  cmd = q & venvC & q & " " & q & launcher & q
  sh.Run cmd, 0, False
  WScript.Quit 0
End If

cmd = "py -3 " & q & launcher & q
sh.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0

' Último recurso: mostrar mensaje (solo si nada funcionó)
MsgBox "Fajos Central: no se encontró Python." & vbCrLf & _
       "Ejecuta setup_windows.ps1 una vez.", vbExclamation, "Fajos Central"
WScript.Quit 1
