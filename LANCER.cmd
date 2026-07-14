@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (start "" pyw -3 "%~dp0boite_noire_hoymiles.py" & exit /b)
where pythonw >nul 2>nul
if %errorlevel%==0 (start "" pythonw "%~dp0boite_noire_hoymiles.py" & exit /b)
echo Python est introuvable. Installez Python puis relancez ce fichier.
pause
