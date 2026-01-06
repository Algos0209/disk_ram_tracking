@echo off
if exist "C:\disk_ram_v2\" (
    echo Folder C:\disk_ram_v2 exists
) else (
    echo Folder C:\disk_ram_v2 does not exist
    echo Creating folder...
    mkdir "C:\disk_ram_v2"
    echo Folder created successfully
    echo Setting permissions for Everyone to Full Control...
    icacls "C:\disk_ram_v2" /grant Everyone:F
    echo Permissions set successfully
)

for /f %%i in ('powershell -NoProfile -Command "(hostname).ToLower()"') do set hostname=%%i
set username=%hostname:css=uss%
set toolnumber=%hostname:css01sth=%
set toolnumber=%toolnumber:ts01=%
set password=sth@TS%toolnumber%

echo username: %username%
echo toolnumber: %toolnumber%
echo password: %password%

net use B: \\{source} /user:%username% %password%
robocopy B:\ C:\disk_ram_v2 disk_ram_check.bat
net use B: /delete

schtasks /create /tn "DiskRamMonitor" /sc hourly /mo 6 /st 00:00 /tr "C:\disk_ram_v2\disk_ram_check.bat" /ru %username% /f