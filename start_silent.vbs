If WScript.Arguments.Count = 0 Then
  WScript.Quit 1
End If
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' 0 = oculto, False = no esperar
sh.Run """" & WScript.Arguments(0) & """", 0, False
