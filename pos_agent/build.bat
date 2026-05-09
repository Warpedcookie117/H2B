@echo off
echo Instalando dependencias...
pip install -r requirements.txt

echo.
echo Compilando pos_agent.exe...
pyinstaller --onefile --windowed --name pos_agent print_server.py

echo.
echo ============================================
echo  Listo!
echo  Copia  dist\pos_agent.exe  a cada compu.
echo  Ejecuta instalar_inicio.bat para que
echo  arranque solo al prender la computadora.
echo ============================================
pause
