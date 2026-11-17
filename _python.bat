@echo off
rem Descobre o Python instalado e guarda em %PY% (e o pythonw, sem janela, em %PYW%)
set "PY="
set "PYW="
where py >nul 2>nul && set "PY=py -3"
if defined PY (
  %PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul || set "PY="
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if defined PY (
  %PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul || set "PY="
)
if defined PY (
  for /f "usebackq delims=" %%i in (`%PY% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"`) do set "PYW=%%i"
)
if defined PYW (
  if not exist "%PYW%" set "PYW="
)
