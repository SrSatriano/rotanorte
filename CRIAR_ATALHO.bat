@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d='%~dp0'; $w=New-Object -ComObject WScript.Shell; $l=$w.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\RotaNorte.lnk'); $l.TargetPath=$d+'INICIAR.bat'; $l.WorkingDirectory=$d; $l.WindowStyle=7; $l.IconLocation=$env:SystemRoot+'\System32\shell32.dll,13'; $l.Description='RotaNorte - vagas com visto'; $l.Save()"
if errorlevel 1 (
  echo   Nao consegui criar o atalho.
) else (
  echo.
  echo   Pronto! O atalho "RotaNorte" esta na sua Area de Trabalho.
)
echo.
pause
