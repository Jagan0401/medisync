@echo off
title MediSynC AI Healthcare Platform
color 0A

echo.
echo ========================================================
echo       MediSynC AI Healthcare Platform - Startup
echo ========================================================
echo.

cd /d "%~dp0backend"

echo [1/5] Activating virtual environment...
call "%~dp0.venv\Scripts\activate.bat"

echo.
echo [2/5] Starting ngrok tunnel (port 8000)...
echo --------------------------------------------------------
REM Kill any existing ngrok to avoid port conflicts
taskkill /F /IM ngrok.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start "ngrok" /min cmd /c "ngrok http 8000"
echo Waiting for ngrok to initialize...
timeout /t 3 /nobreak >nul

REM Fetch the ngrok public URL and display it
echo import urllib.request,json > "%TEMP%\get_ngrok.py"
echo data=json.load(urllib.request.urlopen("http://localhost:4040/api/tunnels")) >> "%TEMP%\get_ngrok.py"
echo print(data["tunnels"][0]["public_url"]) >> "%TEMP%\get_ngrok.py"
for /f "delims=" %%u in ('python "%TEMP%\get_ngrok.py" 2^>nul') do set NGROK_URL=%%u
del "%TEMP%\get_ngrok.py" >nul 2>&1
if defined NGROK_URL (
    echo   ngrok URL: %NGROK_URL%
    echo   Webhook:   %NGROK_URL%/api/outreach/webhook/whatsapp/
    echo.
    echo   ** Set this webhook URL in Twilio Sandbox config **
) else (
    echo   [!] Could not detect ngrok URL. Check http://localhost:4040
)
echo --------------------------------------------------------
echo.

echo [3/5] Starting Django server on port 8000 (background)...
echo --------------------------------------------------------
start "Django - MediSynC" /min cmd /c "cd /d %~dp0backend && python manage.py runserver 0.0.0.0:8000"
echo Waiting for Django to initialize...
timeout /t 3 /nobreak >nul

REM Verify Django is running
echo import urllib.request > "%TEMP%\check_django.py"
echo urllib.request.urlopen("http://localhost:8000/api/outreach/webhook/whatsapp/test/") >> "%TEMP%\check_django.py"
python "%TEMP%\check_django.py" >nul 2>&1
del "%TEMP%\check_django.py" >nul 2>&1
if %errorlevel%==0 (
    echo   Django server is running on http://127.0.0.1:8000/
) else (
    echo   [!] Django may not have started yet. Check the Django window.
)
echo --------------------------------------------------------
echo.

echo [4/5] Running AI Pipeline (5 new patients + risk analysis + WhatsApp)...
echo --------------------------------------------------------
python manage.py run_pipeline --count 5
echo --------------------------------------------------------
echo.

echo [5/5] All services running!
echo ========================================================
echo   Django  : http://127.0.0.1:8000/  (minimized window)
echo   ngrok   : %NGROK_URL%  (minimized window)
echo   Webhook : %NGROK_URL%/api/outreach/webhook/whatsapp/
echo   ngrok UI: http://localhost:4040
echo ========================================================
echo.
echo   WhatsApp replies will work as long as this stays open.
echo   Press any key to STOP all services and exit.
echo.
pause

echo.
echo Shutting down...
taskkill /F /IM ngrok.exe >nul 2>&1
REM Django runs in a separate cmd window; closing it
taskkill /FI "WINDOWTITLE eq Django - MediSynC*" >nul 2>&1
echo Done. Goodbye!
timeout /t 2 /nobreak >nul
