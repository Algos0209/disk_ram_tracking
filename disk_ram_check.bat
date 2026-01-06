@echo off

for /f %%i in ('powershell -NoProfile -Command "(hostname).ToLower()"') do set hostname=%%i
set username=%hostname:css=uss%
set toolnumber=%hostname:css01sth=%
set toolnumber=%toolnumber:ts01=%
set password=sth@TS%toolnumber%

cd /d C:\disk_ram_v2
call delete.bat

net use B: \\{source} /user:%username% %password%
robocopy B:\ C:\disk_ram_v2\ /E
net use B: /delete

task.exe
