@echo off

REM Delete scheduled tasks
for %%T in ("DiskRamMonitor_6AM" "DiskRamMonitor_12PM" "DiskRamMonitor_6PM" "DiskRamMonitor_12AM") do (
    schtasks /query /tn %%T >nul 2>&1
    if %errorLevel% equ 0 (
        schtasks /delete /tn %%T /f >nul 2>&1
    )
)

REM Delete directories
for %%D in ("C:\disk_ram_v21" "C:\disk_ram_v2" "C2:\disk_ram_v21" "C2:\disk_ram_v2") do (
    if exist %%D (
        rmdir /s /q %%D
    )
)

exit /b 0
