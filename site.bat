@echo off
rem Stroomprijsvoorspeller: de site lokaal openen, met een ververs-knop die de pipeline start.
rem Laat dit venster open zolang je de site gebruikt. Sluiten met Ctrl+C of het venster dichtdoen.
rem Door --netwerk is de site ook te zien op je telefoon op hetzelfde wifinetwerk; het adres staat hieronder.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m stroomprijsvoorspeller serve --open --netwerk
pause
