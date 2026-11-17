@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
if not defined PY (
  echo Python nao encontrado. Rode INICIAR.bat para instrucoes.
  pause
  exit /b 1
)
echo.
echo   Instalando o extra opcional "pypdf" (le os PDFs oficiais de empregadores do AIP)...
echo.
%PY% -m pip install --user --upgrade pypdf
echo.
pause
