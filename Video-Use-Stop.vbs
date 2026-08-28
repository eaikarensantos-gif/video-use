' Stops the video-use backend started by Video-Use.vbs.
'
' Caveat: this closes every hidden Python process (pythonw.exe) on your
' machine, not just this one — fine on a personal PC where video-use is
' the only thing you run that way, but if you use pythonw for something
' else too, close this from Task Manager instead (find "pythonw.exe",
' End Task).

Set shell = CreateObject("WScript.Shell")
shell.Run "taskkill /F /IM pythonw.exe", 0, True
MsgBox "video-use foi encerrado.", vbInformation, "video-use"
