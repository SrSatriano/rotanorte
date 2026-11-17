@echo off
chcp 65001 >nul
title RotaNorte - modo com log
cd /d "%~dp0"
call "%~dp0_python.bat"
if not defined PY (
  echo Python nao encontrado. Rode INICIAR.bat para instrucoes.
  pause
  exit /b 1
)
echo.
echo   Modo com log: use se o RotaNorte nao abrir pelo INICIAR.bat.
echo   As mensagens aparecem aqui. Feche a janela do RotaNorte para encerrar.
echo.
%PY% rotanorte.py painel
pause
