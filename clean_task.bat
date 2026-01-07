@echo off

REM Delete scheduled tasks
for %%T in ("DiskRamMonitor" "DiskRamMonitor_6AM" "DiskRamMonitor_12PM" "DiskRamMonitor_6PM" "DiskRamMonitor_12AM") do (
    schtasks /query /tn %%T >nul 2>&1
    if %errorLevel% equ 0 (
        echo Deleting scheduled task: %%T
        schtasks /delete /tn %%T /f >nul 2>&1
    )
)

REM Delete specific files in directories
echo Deleting specific files...
for %%D in ("C:\disk_ram_v21" "C:\disk_ram_v2") do (
    if exist %%D (
        del /f /q "%%~D\disk_ram_check.bat" 2>nul
        del /f /q "%%~D\task.exe" 2>nul
        del /f /q "%%~D\delete.bat" 2>nul
        del /f /q "%%~D\task_log.txt" 2>nul
        del /f /q "%%~D\*.*" 2>nul
    )
)

REM Delete directories
echo Deleting directories...
for %%D in ("C:\disk_ram_v21" "C:\disk_ram_v2" "C2:\disk_ram_v21" "C2:\disk_ram_v2") do (
    if exist %%D (
        echo Removing directory: %%D
        rmdir /s /q %%D
    )
)

echo Cleanup completed successfully
exit /b 0
