@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   video-use - primeira configuracao (1 vez so)
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH.
    echo Instale em https://www.python.org/downloads/
    echo IMPORTANTE: marque a caixa "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Node.js/npm nao foi encontrado no PATH.
    echo Instale em https://nodejs.org/ ^(versao LTS^) e reinicie o PC depois.
    echo.
    pause
    exit /b 1
)

echo [1/4] Instalando dependencias Python...
python -m pip install -e ".[webapp]"
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias Python. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando dependencias do frontend ^(pode demorar um pouco^)...
cd webapp\frontend
call npm install
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias do frontend.
    cd /d "%~dp0"
    pause
    exit /b 1
)

echo.
echo [3/4] Compilando a interface...
call npm run build
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao compilar a interface.
    cd /d "%~dp0"
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [4/5] Preparando a pasta de videos...
if not exist "%USERPROFILE%\Videos\video-use" mkdir "%USERPROFILE%\Videos\video-use"

echo.
echo [5/5] Criando atalho na Area de Trabalho e no Menu Iniciar...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs';" ^
    "foreach ($dir in @([Environment]::GetFolderPath('Desktop'), $startMenu)) {" ^
    "  $s = $ws.CreateShortcut((Join-Path $dir 'video-use.lnk'));" ^
    "  $s.TargetPath = '%~dp0Video-Use.vbs';" ^
    "  $s.WorkingDirectory = '%~dp0';" ^
    "  $s.IconLocation = '%~dp0Video-Use.ico';" ^
    "  $s.Description = 'Editor de video video-use';" ^
    "  $s.Save();" ^
    "}" ^
    "$u = $ws.CreateShortcut((Join-Path $startMenu 'video-use (atualizar).lnk'));" ^
    "$u.TargetPath = '%~dp0Video-Use-Update.bat';" ^
    "$u.WorkingDirectory = '%~dp0';" ^
    "$u.IconLocation = '%~dp0Video-Use.ico';" ^
    "$u.Description = 'Baixar e instalar a versao mais nova do video-use';" ^
    "$u.Save();"
if errorlevel 1 (
    echo   [aviso] Nao consegui criar o atalho automaticamente - sem problema,
    echo   continua dando duplo-clique em "Video-Use.vbs" normalmente.
)

echo.
echo ================================================
echo   Pronto! Pode fechar esta janela.
echo.
echo   De agora em diante, para abrir o editor:
echo     -^> procura "video-use" no Menu Iniciar, ou usa o atalho
echo        que apareceu na sua Area de Trabalho
echo.
echo   Quando tiver uma atualizacao nova:
echo     -^> procura "video-use (atualizar)" no Menu Iniciar
echo        (baixa e instala sozinho, sem mexer no seu .env)
echo.
echo   Seus videos ficam em:
echo     %USERPROFILE%\Videos\video-use
echo ================================================
echo.
pause
