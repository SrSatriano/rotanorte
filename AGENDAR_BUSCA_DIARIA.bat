@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   Isto cria uma tarefa no Windows para buscar vagas todo dia as 08:00.
echo   (O computador precisa estar ligado nesse horario.)
echo.
schtasks /Create /SC DAILY /ST 08:00 /TN "RotaNorte - busca diaria" /TR "\"%~dp0COLETAR.bat\"" /F
if errorlevel 1 (
  echo.
  echo   Nao consegui criar a tarefa. Tente clicar com o botao direito neste arquivo
  echo   e escolher "Executar como administrador".
) else (
  echo.
  echo   Pronto! Para remover depois: schtasks /Delete /TN "RotaNorte - busca diaria" /F
)
echo.
pause
