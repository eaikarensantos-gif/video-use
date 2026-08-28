' Everyday launcher for video-use — double-click, no terminal window.
' Starts the backend hidden (pythonw = no console), waits for it to
' actually answer before opening the browser (polls /api/health instead
' of a fixed sleep — first-time startup can take longer than a few
' seconds while Python warms up its import caches).
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

' 0 = hidden window, False = don't wait for it to exit (it keeps running).
' Runs via cmd so stdout/stderr get redirected to a log file — pythonw has
' no console of its own, so without this a crash after startup leaves no
' trace to debug from.
logPath = scriptDir & "\video-use-backend.log"
On Error Resume Next
shell.Run "cmd /c pythonw """ & backendScript & """ --videos-dir """ & videosDir & """ > """ & logPath & """ 2>&1", 0, False
launchFailed = (Err.Number <> 0)
launchError = Err.Description
Err.Clear
On Error Goto 0

If launchFailed Then
    MsgBox "Nao consegui iniciar o video-use." & vbCrLf & _
           "Erro: " & launchError & vbCrLf & vbCrLf & _
           "Tente rodar Video-Use-Setup.bat de novo, ou abra manualmente" & vbCrLf & _
           "no PowerShell para ver a mensagem completa:" & vbCrLf & _
           "python webapp\backend\main.py --videos-dir """ & videosDir & """", _
           vbCritical, "video-use"
    WScript.Quit 1
End If

' Poll until the server actually answers instead of guessing a fixed
' wait — first-time startup (cold Python import caches) can take well
' over a few seconds, and this adapts either way.
healthUrl = "http://127.0.0.1:8756/api/health"
maxWaitSeconds = 45
started = False
Set http = CreateObject("WinHttp.WinHttpRequest.5.1")

For i = 1 To maxWaitSeconds * 2
    WScript.Sleep 500
    On Error Resume Next
    http.Open "GET", healthUrl, False
    http.SetTimeouts 1000, 1000, 1000, 1000
    http.Send
    If Err.Number = 0 And http.Status = 200 Then
        started = True
    End If
    Err.Clear
    On Error Goto 0
    If started Then Exit For
Next

If started Then
    ' Open in Edge's "app mode" (no address bar/tabs) so it looks and feels
    ' like a real installed app rather than a browser tab. Falls back to
    ' the default browser if Edge isn't found at either usual install path.
    edgePaths = Array( _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe")
    edgePath = ""
    For Each p In edgePaths
        If fso.FileExists(p) Then
            edgePath = p
            Exit For
        End If
    Next

    If edgePath <> "" Then
        shell.Run """" & edgePath & """ --app=http://127.0.0.1:8756 --window-size=1440,900", 1, False
    Else
        shell.Run "http://127.0.0.1:8756"
    End If
Else
    MsgBox "O video-use esta demorando mais que o esperado pra iniciar." & vbCrLf & _
           "Abra manualmente no navegador: http://127.0.0.1:8756" & vbCrLf & vbCrLf & _
           "Se essa pagina tambem nao abrir (ou fechar sozinha), o motivo" & vbCrLf & _
           "do erro fica salvo neste arquivo, que da pra abrir com o Bloco" & vbCrLf & _
           "de Notas:" & vbCrLf & logPath, _
           vbExclamation, "video-use"
End If
