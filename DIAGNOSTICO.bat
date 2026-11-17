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
echo   Testando conexao com as fontes oficiais...
echo.
%PY% rotanorte.py diagnostico
echo.
pause
