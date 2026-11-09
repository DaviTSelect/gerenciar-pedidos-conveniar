@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  Release - Gerenciar Pedidos Conveniar
echo ============================================

:: Usa o Python/pip/pyinstaller do .venv se existir, senao usa o do PATH
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
    set PIP=.venv\Scripts\pip.exe
    set PYINST=.venv\Scripts\pyinstaller.exe
) else (
    set PY=python
    set PIP=pip
    set PYINST=pyinstaller
)

:: Le a versao via Python (mais seguro que findstr/for /f com aspas)
for /f "usebackq delims=" %%v in (`%PY% -c "import sys; sys.path.insert(0,'src'); from pedidos.version import VERSION; print(VERSION)"`) do set VERSION=%%v
if "%VERSION%"=="" (
    echo ERRO: nao foi possivel ler VERSION de src\pedidos\version.py
    pause & exit /b 1
)
set TAG=v%VERSION%
echo Versao: %TAG%
echo.

:: Verifica se a tag ja existe (evita sobrescrever release publicada)
git fetch --tags -q 2>nul
git rev-parse "%TAG%" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ERRO: tag %TAG% ja existe.
    echo Incremente VERSION em src\pedidos\version.py antes de fazer release.
    pause & exit /b 1
)

:: [1/5] Instala dependencias de build
echo [1/5] Instalando dependencias de build...
%PIP% install -r requirements-build.txt -q
if %ERRORLEVEL% neq 0 ( echo ERRO ao instalar dependencias & pause & exit /b 1 )

:: [2/5] Roda testes
echo [2/5] Executando testes...
set PYTHONPATH=src
%PY% -m pytest tests -q
if %ERRORLEVEL% neq 0 ( echo ERRO nos testes & pause & exit /b 1 )

:: [3/5] Compila o executavel
echo [3/5] Compilando executavel...
if exist dist rmdir /s /q dist
%PYINST% GerenciarPedidos.spec --noconfirm
if %ERRORLEVEL% neq 0 ( echo ERRO no PyInstaller & pause & exit /b 1 )
if not exist "dist\GerenciarPedidos.exe" (
    echo ERRO: dist\GerenciarPedidos.exe nao encontrado
    pause & exit /b 1
)

:: [4/5] Calcula SHA-256
echo [4/5] Calculando SHA-256...
for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "(Get-FileHash 'dist\GerenciarPedidos.exe' -Algorithm SHA256).Hash.ToLower()"`) do set SHA256=%%h
echo %SHA256%  GerenciarPedidos.exe > dist\GerenciarPedidos.exe.sha256
echo SHA-256: %SHA256%

:: [5/5] Cria tag, envia e publica release com EXE e SHA-256
echo [5/5] Publicando release %TAG% no GitHub...
git tag %TAG%
git push origin %TAG%
if %ERRORLEVEL% neq 0 (
    git tag -d %TAG% >nul 2>&1
    echo ERRO ao enviar tag para o GitHub
    pause & exit /b 1
)

:: Escreve notas em arquivo temporario (evita problemas com escaping de multiline)
set NOTES_FILE=%TEMP%\release_notes_%VERSION%.md
(
    echo ## Instalacao
    echo.
    echo 1. Baixe GerenciarPedidos.exe
    echo 2. Coloque na pasta desejada
    echo 3. Execute GerenciarPedidos.exe e informe usuario e senha na interface
    echo.
    echo **SHA-256:** %SHA256%
) > "%NOTES_FILE%"

gh release create %TAG% ^
    "dist\GerenciarPedidos.exe" ^
    "dist\GerenciarPedidos.exe.sha256" ^
    --title "Gerenciar Pedidos Conveniar %TAG%" ^
    --notes-file "%NOTES_FILE%"

if %ERRORLEVEL% neq 0 (
    echo ERRO ao criar release no GitHub
    del "%NOTES_FILE%" >nul 2>&1
    pause & exit /b 1
)
del "%NOTES_FILE%" >nul 2>&1

echo.
echo ============================================
echo  Release %TAG% publicada com sucesso!
echo  https://github.com/DaviTSelect/gerenciar-pedidos-conveniar/releases/tag/%TAG%
echo ============================================
pause
