@echo off
if exist "C:\disk_ram_v21\" (
    echo Folder C:\disk_ram_v21 exists
) else (
    echo Folder C:\disk_ram_v21 does not exist
    echo Creating folder...
    mkdir "C:\disk_ram_v21"
    echo Folder created successfully
    echo Setting permissions for Everyone to Full Control...
    icacls "C:\disk_ram_v21" /grant Everyone:F
    echo Permissions set successfully
)
