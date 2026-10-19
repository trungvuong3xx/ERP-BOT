Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\ERP Bot iGP.lnk")

batScript = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\ERP_Bot_Launcher.bat"
iconFile = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\app_icon.ico"

oShellLink.TargetPath = batScript
oShellLink.WorkingDirectory = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
oShellLink.IconLocation = iconFile & ",0"
oShellLink.WindowStyle = 7
oShellLink.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
oShellLink.Save
