@echo off
echo Configurando inicio automatico con Windows...
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
copy /y "%~dp0pos_agent.exe" "%STARTUP%\pos_agent.exe"
echo.
echo Listo! pos_agent.exe iniciara automaticamente al encender la computadora.
pause
