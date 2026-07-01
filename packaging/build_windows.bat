@echo off
REM Construit l'executable Windows de l'assistant de synthese de reunions.
REM A lancer depuis la racine du projet, dans une invite de commandes Windows :
REM     packaging\build_windows.bat

setlocal
echo === Creation de l'environnement de build ===
python -m venv .venv-build || goto :error
call .venv-build\Scripts\activate.bat || goto :error

echo === Installation des dependances ===
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt pyinstaller || goto :error
REM Decommentez la ligne suivante pour embarquer aussi la diarisation :
REM python -m pip install "pyannote.audio>=3.1" || goto :error

echo === Construction (PyInstaller) ===
pyinstaller packaging\pmo-notes.spec --noconfirm --clean || goto :error

echo.
echo === Termine ===
echo L'application se trouve dans : dist\PMONotes\PMONotes.exe
goto :eof

:error
echo.
echo *** La construction a echoue. Voir les messages ci-dessus. ***
exit /b 1
