@echo off
rem (16-nov-2026) Prende el marco de fotos del iPad (puerto 8790, red de la casa) sin ventana y muestra la direccion para abrir en Safari.
rem Fotos: %USERPROFILE%\Pictures\Marco. Para apagarlo: reiniciar la PC o cerrar el pythonw de marco.py desde el Administrador de tareas.
start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0marco.py"
echo.
echo Marco prendido. Abre esta direccion en el Safari del iPad (misma red wifi que la laptop):
echo.
type "%~dp0enlace.txt"
echo.
echo.
pause
