import os
import win32com.client

shell = win32com.client.Dispatch('WScript.Shell')
desktop = shell.SpecialFolders('Desktop')
shortcut_path = os.path.join(desktop, 'ERP Bot iGP.lnk')

# Create a VBS script to run python silently
vbs_path = os.path.abspath('run_silent.vbs')
with open(vbs_path, 'w', encoding='utf-8') as f:
    f.write('Set WshShell = CreateObject("WScript.Shell")\n')
    f.write(f'WshShell.CurrentDirectory = "{os.path.abspath(".")}"\n')
    f.write('WshShell.Run "python app_gui.py", 0, False\n')


shortcut = shell.CreateShortCut(shortcut_path)
shortcut.TargetPath = 'wscript.exe'
shortcut.Arguments = f'"{vbs_path}"'
shortcut.WorkingDirectory = os.path.abspath('.')
shortcut.IconLocation = os.path.abspath('app_icon.ico') + ', 0'
shortcut.Description = 'ERP Bot (Auto-Update Version)'
shortcut.save()
print('Đã tạo shortcut thành công')
