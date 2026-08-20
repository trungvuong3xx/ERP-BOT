Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\ERP Bot iGP.lnk")

targetExe = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\dist\ERP Bot iGP\ERP Bot iGP.exe"
workDir = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\dist\ERP Bot iGP"

oShellLink.TargetPath = targetExe
oShellLink.WorkingDirectory = workDir
oShellLink.IconLocation = targetExe & ",0"
oShellLink.WindowStyle = 1
oShellLink.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
oShellLink.Save
