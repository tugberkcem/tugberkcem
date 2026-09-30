@echo off
REM =====================================================================
REM  tugberkcem | animated profile  |  Windows tek tiklamalik kurulum
REM  Bu dosyaya cift tikla; gerisini setup.py halleder.
REM
REM  Python'u bulmak icin sirayla sunlari dener:
REM    1. py -3        (py launcher, en guvenilir yontem)
REM    2. python       (PATH uzerinde)
REM    3. Bilinen kurulum yollari (LocalAppData, Program Files)
REM =====================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON_EXE="

echo.
echo   Python araniyor...
echo.

REM ---- 1) py launcher ----------------------------------------------------
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    echo   [OK] 'py' launcher bulundu.
    goto :found
)

REM ---- 2) PATH uzerindeki python -----------------------------------------
python --version >nul 2>nul
if not errorlevel 1 (
    REM Microsoft Store stub'i kontrol et: 'python' calisinca magaza aciliyorsa
    REM gercek bir Python yok demektir.
    python -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
        echo   [OK] 'python' komutu bulundu.
        goto :found
    )
)

REM ---- 3) Bilinen kurulum yollari ----------------------------------------
for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        echo   [OK] Python bulundu: !PYTHON_EXE!
        goto :found
    )
    if exist "C:\Program Files\Python%%V\python.exe" (
        set "PYTHON_EXE=C:\Program Files\Python%%V\python.exe"
        echo   [OK] Python bulundu: !PYTHON_EXE!
        goto :found
    )
)

REM ---- Bulunamadi --------------------------------------------------------
echo.
echo   [X] Python bulunamadi.
echo.
echo   Cozum 1 - En hizli yol (PowerShell veya CMD):
echo       winget install Python.Python.3.12
echo.
echo   Cozum 2 - Elle kurulum:
echo       https://www.python.org/downloads/  adresinden indir ve
echo       kurulum ekraninda "Add python.exe to PATH" kutusunu ISARETLE.
echo.
echo   ONEMLI: Kurulumdan sonra bu pencereyi KAPAT ve
echo           run_setup.bat dosyasina yeniden cift tikla.
echo           (PATH degisikligi sadece yeni pencerelerde gecerli olur.)
echo.
pause
exit /b 1

:found
echo.
%PYTHON_EXE% scripts\setup.py

echo.
echo   Bitti. Bu pencereyi kapatabilirsin.
pause
endlocal
