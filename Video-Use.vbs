' Everyday launcher for video-use — double-click, no terminal window.
' Starts the backend hidden (pythonw = no console) and opens the editor
' in the default browser once it's had a moment to come up.
'
' First time on a new machine, run Video-Use-Setup.bat once instead —
' it installs dependencies and builds the frontend, both required before
' this script has anything to serve.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir

videosDir = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\Videos\video-use"
If Not fso.FolderExists(videosDir) Then
    fso.CreateFolder(videosDir)
End If

backendScript = scriptDir & "\webapp\backend\main.py"

If Not fso.FileExists(backendScript) Then
    MsgBox "Nao encontrei webapp\backend\main.py nesta pasta." & vbCrLf & _
           "Confirma que este atalho esta na raiz do repositorio video-use.", _
           vbExclamation, "video-use"
    WScript.Quit 1
End If

' 0 = hidden window, False = don't wait for it to exit (it keeps running)
shell.Run "pythonw """ & backendScript & """ --videos-dir """ & videosDir & """", 0, False

' Give the server a moment to start listening before opening the browser.
WScript.Sleep 2500

shell.Run "http://127.0.0.1:8756"
