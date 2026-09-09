Option Explicit
' Arranque sin consola (Inicio de Windows / acceso directo).
Dim sh, fso, dir, launcher, venvW, venvC, cmd, q
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
q = Chr(34)
launcher = dir & "\launcher.py"
If Not fso.FileExists(launcher) Then
  MsgBox "No se encuentra launcher.py en:" & vbCrLf & dir, vbCritical, "Fajos Central"
  WScript.Quit 1
End If

venvW = dir & "\.venv\Scripts\pythonw.exe"
venvC = dir & "\.venv\Scripts\python.exe"

On Error Resume Next

If fso.FileExists(venvW) Then
  cmd = q & venvW & q & " " & q & launcher & q
  sh.Run cmd, 0, False
  If Err.Number = 0 Then WScript.Quit 0
  Err.Clear
End If

cmd = "pythonw " & q & launcher & q
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
  If Err.Number = 0 Then WScript.Quit 0
  Err.Clear
End If

cmd = "py -3 " & q & launcher & q
sh.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0
Err.Clear

MsgBox "Fajos Central: no se encontro Python." & vbCrLf & _
       "Ejecuta setup_windows.ps1 una vez." & vbCrLf & vbCrLf & _
       "Carpeta: " & dir, vbExclamation, "Fajos Central"
WScript.Quit 1
