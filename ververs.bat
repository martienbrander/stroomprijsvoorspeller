@echo off
rem Stroomprijsvoorspeller: nieuwe voorspelling maken (besluit 49).
rem Haalt prijzen en weer op, haalt gemiste dagen in, traint zo nodig het model, voorspelt en schrijft de site-JSON.
rem Duurt een paar minuten. Daarna de pagina opnieuw laden (site.bat start de pagina).
cd /d "%~dp0"
echo Stroomprijsvoorspeller: voorspelling verversen...
".venv\Scripts\python.exe" -m stroomprijsvoorspeller daily --type auto
if errorlevel 1 (
  echo.
  echo Er ging iets mis. Zie de melding hierboven.
  pause
)
