@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_python.bat"
if not defined PY (
  echo Python nao encontrado. Rode INICIAR.bat para instrucoes.
  exit /b 1
)
if not exist dados mkdir dados
echo ===== %date% %time% ===== >> dados\coleta.log
%PY% rotanorte.py coletar >> dados\coleta.log 2>&1
