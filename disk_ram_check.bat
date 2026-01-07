@echo off
setlocal enabledelayedexpansion

REM Log file for debugging
set LOGFILE=C:\disk_ram_v2\task_log.txt
echo ========================================= >> %LOGFILE%
echo Task started at %date% %time% >> %LOGFILE%

for /f %%i in ('powershell -NoProfile -Command "(hostname).ToLower()"') do set hostname=%%i

set toolnumber=%hostname:css01sth=%
set toolnumber=%toolnumber:ts01=%
set toolnumber=000%toolnumber%
set toolnumber=%toolnumber:~-3%
set username=uss01sth%toolnumber%ts01
set password=sth@TS%toolnumber%

echo Username: %username% >> %LOGFILE%

REM Change to working directory
cd /d C:\disk_ram_v2
echo Changed to directory: %cd% >> %LOGFILE%

REM Call delete.bat if it exists
if exist "C:\disk_ram_v2\delete.bat" (
    echo Calling delete.bat >> %LOGFILE%
    call "C:\disk_ram_v2\delete.bat"
    echo Delete.bat completed with errorlevel: !errorlevel! >> %LOGFILE%
) else (
    echo delete.bat not found, skipping >> %LOGFILE%
)

REM Map network drive with retry
echo Mapping network drive B: >> %LOGFILE%
net use B: /delete /yes >nul 2>&1
timeout /t 2 /nobreak >nul
net use B: \\{source} /user:%username% %password% >> %LOGFILE% 2>&1
if !errorlevel! neq 0 (
    echo Failed to map network drive, errorlevel: !errorlevel! >> %LOGFILE%
    goto cleanup
)
echo Network drive mapped successfully >> %LOGFILE%

REM Perform robocopy
echo Starting robocopy >> %LOGFILE%
robocopy B:\ C:\disk_ram_v2\ /E >> %LOGFILE% 2>&1
set ROBOCOPY_ERROR=!errorlevel!
echo Robocopy completed with exit code: !ROBOCOPY_ERROR! >> %LOGFILE%

REM Disconnect network drive
echo Disconnecting network drive >> %LOGFILE%
net use B: /delete /yes >> %LOGFILE% 2>&1

:cleanup
REM Run task.exe if it exists
if exist "C:\disk_ram_v2\task.exe" (
    echo Running task.exe >> %LOGFILE%
    "C:\disk_ram_v2\task.exe" >> %LOGFILE% 2>&1
    echo task.exe completed with errorlevel: !errorlevel! >> %LOGFILE%
) else (
    echo task.exe not found >> %LOGFILE%
)

echo Task completed at %date% %time% >> %LOGFILE%
echo ========================================= >> %LOGFILE%

endlocal
