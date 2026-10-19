$WshShell = New-Object -comObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\ERP Bot iGP.lnk")
$Shortcut.TargetPath = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\ERP_Bot_Launcher.bat"
$Shortcut.WorkingDirectory = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
$Shortcut.IconLocation = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\app_icon.ico, 0"
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
$Shortcut.Save()
