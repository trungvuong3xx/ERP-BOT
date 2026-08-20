Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
WshShell.Run "python app_gui.py", 0, False
