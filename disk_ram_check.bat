@echo off

for /f %%i in ('hostname') do set hostname=%%i
set username=%hostname:css=uss%
set toolnumber=%hostname:css01sth=%
set toolnumber=%toolnumber:ts01=%
set password=sth@TS%toolnumber%

net use B: \\ssfile1\spe_shared /user:uss\%username% %password%
robocopy "B:\" "C:\disk_ram_v2\" /E /R:3 /W:5
net use B: /delete

cd /d C:\disk_ram_v2
call delete.bat
task.exe