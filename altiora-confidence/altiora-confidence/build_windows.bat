@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Altiora Confidence - creation de l'installateur
set "LOG=%~dp0build\build.log"
if not exist build mkdir build
echo. > "%LOG%"

echo.
echo  =====================================================
echo    Altiora Confidence  -  creation de l'installateur
echo  =====================================================
echo.
echo  Internet est necessaire pendant cette etape (environ 5 a 10 minutes).
echo  Le detail technique est enregistre dans build\build.log
echo.

rem ---------- 1. Python ----------
rem The AI libraries exist ready-made only for 64-bit Python 3.10 to 3.14.
set "CHECK=import sys,struct; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,14) and struct.calcsize('P')==8 else 1)"
set "PY="
for %%V in (3.13 3.12 3.11 3.14 3.10) do (
  if not defined PY (
    py -%%V -c "%CHECK%" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "%CHECK%" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo  [X] Aucune version compatible de Python n'a ete trouvee.
  echo      Installez Python 3.13 64 bits depuis https://www.python.org/downloads/
  echo      en cochant "Add Python to PATH", puis relancez ce fichier.
  goto :fail
)
for /f "tokens=2" %%i in ('%PY% --version 2^>^&1') do set "PYVER=%%i"
echo  [1/5] Preparation de l'environnement (Python %PYVER%)...
rem Rebuild the environment if it was made with an unsuitable Python
if exist ".build-venv\Scripts\python.exe" (
  ".build-venv\Scripts\python.exe" -c "%CHECK%" >nul 2>nul || rmdir /s /q .build-venv
)
if not exist ".build-venv\Scripts\python.exe" (
  %PY% -m venv .build-venv >>"%LOG%" 2>&1 || goto :fail_log
)
set "VPY=%~dp0.build-venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip >>"%LOG%" 2>&1
rem --only-binary: never try to compile the AI libraries (that needs Visual Studio and fails)
"%VPY%" -m pip install --prefer-binary --only-binary=spacy,thinc,blis,numpy,cymem,preshed,murmurhash,srsly,pymupdf -r requirements.txt >>"%LOG%" 2>&1 || goto :fail_log

rem ---------- 2. AI models + OCR languages ----------
echo  [2/5] Telechargement du modele IA et des langues de lecture des scans...
"%VPY%" packaging\prepare_resources.py >>"%LOG%" 2>&1 || goto :fail_log

rem ---------- 3. Build the program ----------
echo  [3/5] Construction du programme (quelques minutes)...
if exist "dist\Altiora Confidence" rmdir /s /q "dist\Altiora Confidence"
"%VPY%" -m PyInstaller --noconfirm --clean --distpath dist --workpath build\work packaging\altiora_confidence.spec >>"%LOG%" 2>&1 || goto :fail_log

rem ---------- 4. Self-test ----------
echo  [4/5] Verification automatique du programme...
if exist build\selftest rmdir /s /q build\selftest
start "" /wait "dist\Altiora Confidence\Altiora Confidence.exe" --selftest "%~dp0exemple_contrat.pdf" "%~dp0build\selftest"
findstr /c:"RESULT=OK" build\selftest\selftest.txt >nul 2>nul
if errorlevel 1 (
  echo  [X] La verification a echoue. Details :
  type build\selftest\selftest.txt 2>nul
  goto :fail
)
echo        OK : modele IA charge, lecture des scans disponible, document test anonymise.

rem ---------- 5. Installer ----------
echo  [5/5] Creation de l'installateur...
call :find_iscc
if not defined ISCC (
  echo        Installation de l'outil gratuit Inno Setup...
  winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements >>"%LOG%" 2>&1
  call :find_iscc
)
if not exist output mkdir output
if defined ISCC (
  "%ISCC%" /Q packaging\installer.iss >>"%LOG%" 2>&1 || goto :fail_log
  echo.
  echo  =====================================================
  echo    Termine !  output\Setup_Altiora_Confidence_1.0.exe
  echo  =====================================================
  echo.
  echo  Envoyez ce fichier a l'equipe : double-clic, Suivant, Installer.
  echo  Aucun droit administrateur ni connexion internet n'est necessaire.
) else (
  echo        Inno Setup indisponible : creation d'une version portable a la place.
  powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\Altiora Confidence' -DestinationPath 'output\Altiora_Confidence_portable.zip'" >>"%LOG%" 2>&1 || goto :fail_log
  echo.
  echo  =====================================================
  echo    Termine !  output\Altiora_Confidence_portable.zip
  echo  =====================================================
  echo.
  echo  A decompresser, puis lancer "Altiora Confidence.exe".
)
if not defined CI explorer output
echo.
if not defined CI pause
exit /b 0

:find_iscc
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
exit /b 0

:fail_log
echo.
echo  [X] Une etape a echoue. Dernieres lignes du journal :
echo  -----------------------------------------------------
powershell -NoProfile -Command "Get-Content -Tail 25 '%LOG%'"
echo  -----------------------------------------------------
echo  Journal complet : build\build.log
:fail
echo.
if not defined CI pause
exit /b 1
