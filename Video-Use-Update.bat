@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   video-use - atualizando para a versao mais nova
echo ================================================
echo.
echo   (isso baixa a versao mais nova e reinstala por
echo   cima, sem mexer no seu arquivo .env nem nos seus
echo   videos)
echo.

set REPO_ZIP_URL=https://github.com/eaikarensantos-gif/video-use/archive/refs/heads/claude/video-use-interface-fl5c07.zip
set TMPZIP=%TEMP%\video-use-update.zip
set TMPDIR=%TEMP%\video-use-update-extract

echo [1/4] Baixando a versao mais nova...
if exist "%TMPZIP%" del /q "%TMPZIP%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%REPO_ZIP_URL%' -OutFile '%TMPZIP%'"
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao baixar. Confira sua conexao com a internet.
    pause
    exit /b 1
)

echo.
echo [2/4] Extraindo...
if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%TMPZIP%' -DestinationPath '%TMPDIR%' -Force"
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao extrair o arquivo baixado.
    pause
    exit /b 1
)

echo.
echo   Fechando o video-use, caso esteja aberto (para nao travar
echo   arquivos que precisam ser atualizados)...
taskkill /F /IM pythonw.exe >nul 2>nul

echo.
echo [3/4] Copiando os arquivos atualizados por cima dos antigos...
set EXTRACTED=
for /d %%D in ("%TMPDIR%\*") do set EXTRACTED=%%D
if "%EXTRACTED%"=="" (
    echo.
    echo [ERRO] Nao encontrei a pasta extraida.
    pause
    exit /b 1
)
set COPYLOG=%~dp0video-use-update.log
robocopy "%EXTRACTED%" "%~dp0" /E /R:2 /W:2 /XF ".env" "video-use-backend.log" /LOG:"%COPYLOG%" /NFL /NDL /NJH /NC /NS /NP >nul
if errorlevel 8 (
    echo.
    echo [ERRO] Falha ao copiar os arquivos atualizados.
    echo Detalhes salvos em (abre com o Bloco de Notas^):
    echo %COPYLOG%
    pause
    exit /b 1
)

echo.
echo [4/4] Limpando arquivos temporarios...
del /q "%TMPZIP%" >nul 2>nul
rmdir /s /q "%TMPDIR%" >nul 2>nul

echo.
echo ================================================
echo   Baixado! Agora rodando o Setup pra garantir que
echo   tudo fica instalado certinho...
echo ================================================
echo.
call "%~dp0Video-Use-Setup.bat"
