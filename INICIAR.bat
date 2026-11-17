@echo off
chcp 65001 >nul
title RotaNorte
cd /d "%~dp0"
call "%~dp0_python.bat"
if not defined PY (
  echo.
  echo   O Python 3.9+ nao foi encontrado neste computador.
  echo.
  echo   1. Vai abrir o site oficial do Python. Baixe a versao mais nova para Windows.
  echo   2. Na primeira tela da instalacao MARQUE "Add python.exe to PATH".
  echo   3. Termine a instalacao e de dois cliques em INICIAR.bat de novo.
  echo.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)
rem Abre como aplicativo, sem janela preta. Fechar a janela do RotaNorte encerra tudo.
if defined PYW (
  start "" "%PYW%" "%~dp0rotanorte.py" painel
  exit /b 0
)
%PY% rotanorte.py painel
