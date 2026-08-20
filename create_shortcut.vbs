Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\ERP Bot iGP.lnk")

pythonwPath = "C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"
mainScript = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\main.py"
iconFile = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\app_icon.ico"

oShellLink.TargetPath = pythonwPath
oShellLink.Arguments = """" & mainScript & """ --gui"
oShellLink.WorkingDirectory = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
oShellLink.IconLocation = iconFile & ",0"
oShellLink.WindowStyle = 1
oShellLink.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
oShellLink.Save
