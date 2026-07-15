@echo off
setlocal
set "APP=%LOCALAPPDATA%\BoiteNoireHoymiles"
set "BACKUP=%APP%\sauvegarde_avant_mise_a_jour"

echo.
echo === Installation Boite noire Hoymiles ===
echo Les historiques et la configuration existante seront conserves.
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python est introuvable.
    echo Installez Python 3.10 ou plus, cochez "Add Python to PATH", puis relancez cet installateur.
    pause
    exit /b 1
)

echo Installation des dependances Python...
py -3 -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo Installation des dependances impossible. Verifiez votre connexion Internet puis recommencez.
    pause
    exit /b 1
)

if not exist "%APP%" mkdir "%APP%"
if not exist "%BACKUP%" mkdir "%BACKUP%"
if exist "%APP%\config_v5.json" copy /Y "%APP%\config_v5.json" "%BACKUP%\" >nul
if exist "%APP%\hoymiles_log.csv" copy /Y "%APP%\hoymiles_log.csv" "%BACKUP%\" >nul
if exist "%APP%\linky_index_log.csv" copy /Y "%APP%\linky_index_log.csv" "%BACKUP%\" >nul

copy /Y "%~dp0boite_noire_hoymiles.py" "%APP%\boite_noire_hoymiles.py" >nul
copy /Y "%~dp0fond_solaire.png" "%APP%\fond_solaire.png" >nul
copy /Y "%~dp0icone_panneau_solaire.ico" "%APP%\icone_panneau_solaire.ico" >nul
copy /Y "%~dp0LANCER.cmd" "%APP%\LANCER.cmd" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop');$s=(New-Object -COM WScript.Shell).CreateShortcut($desktop+'\Boite noire Hoymiles.lnk');$s.TargetPath=$env:LOCALAPPDATA+'\BoiteNoireHoymiles\LANCER.cmd';$s.WorkingDirectory=$env:LOCALAPPDATA+'\BoiteNoireHoymiles';$s.IconLocation=$env:LOCALAPPDATA+'\BoiteNoireHoymiles\icone_panneau_solaire.ico,0';$s.Save()"

echo.
echo Installation terminee.
echo Lancez le raccourci "Boite noire Hoymiles" cree sur le Bureau.
echo Au premier lancement, renseignez les IP du DTU et du Dinky dans le fichier de configuration indique dans le README.
pause
