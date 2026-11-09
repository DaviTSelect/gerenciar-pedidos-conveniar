@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  Release - Gerenciar Pedidos Conveniar
echo ============================================

:: Lê a versão atual de version.py
for /f "tokens=2 delims=='\"" %%v in ('findstr /r "VERSION *= *\"" src\pedidos\version.py') do set VERSION=%%v
if "%VERSION%"=="" (
    echo ERRO: nao foi possivel ler VERSION de src\pedidos\version.py
    pause & exit /b 1
)
set TAG=v%VERSION%
echo Versao detectada: %TAG%
echo.

:: Verifica se a tag ja existe remotamente
git fetch --tags -q
git rev-parse "%TAG%" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ERRO: tag %TAG% ja existe. Incremente VERSION em src\pedidos\version.py antes de fazer release.
    pause & exit /b 1
)

:: Instala dependencias de build
echo [1/5] Instalando dependencias de build...
pip install -r requirements-build.txt -q
if %ERRORLEVEL% neq 0 ( echo ERRO ao instalar dependencias & pause & exit /b 1 )

:: Roda testes
echo [2/5] Executando testes...
set PYTHONPATH=src
python -m pytest tests -q
if %ERRORLEVEL% neq 0 ( echo ERRO nos testes & pause & exit /b 1 )

:: Compila o executavel
echo [3/5] Compilando executavel...
if exist dist rmdir /s /q dist
pyinstaller GerenciarPedidos.spec --noconfirm
if %ERRORLEVEL% neq 0 ( echo ERRO no PyInstaller & pause & exit /b 1 )
if not exist "dist\GerenciarPedidos.exe" (
    echo ERRO: dist\GerenciarPedidos.exe nao encontrado
    pause & exit /b 1
)

:: Calcula SHA-256
echo [4/5] Calculando SHA-256...
for /f "usebackq" %%h in (`powershell -NoProfile -Command "(Get-FileHash 'dist\GerenciarPedidos.exe' -Algorithm SHA256).Hash.ToLower()"`) do set SHA256=%%h
echo %SHA256%  GerenciarPedidos.exe > dist\GerenciarPedidos.exe.sha256
echo SHA-256: %SHA256%

:: Cria tag, envia e cria release com os arquivos
echo [5/5] Criando tag %TAG% e publicando release no GitHub...
git tag %TAG%
git push origin %TAG%
if %ERRORLEVEL% neq 0 (
    git tag -d %TAG%
    echo ERRO ao enviar tag para o GitHub
    pause & exit /b 1
)

gh release create %TAG% ^
    dist\GerenciarPedidos.exe ^
    dist\GerenciarPedidos.exe.sha256 ^
    --title "Gerenciar Pedidos Conveniar %TAG%" ^
    --notes "## Instalacao

1. Baixe GerenciarPedidos.exe
2. Coloque na pasta desejada
3. Crie um arquivo .env na mesma pasta:
   CONVENIAR_USERNAME=seu_usuario
   CONVENIAR_PASSWORD=sua_senha
4. Execute GerenciarPedidos.exe

**SHA-256:** %SHA256%"

if %ERRORLEVEL% neq 0 (
    echo ERRO ao criar release no GitHub
    pause & exit /b 1
)

echo.
echo ============================================
echo  Release %TAG% publicada com sucesso!
echo  https://github.com/DaviTSelect/gerenciar-pedidos-conveniar/releases/tag/%TAG%
echo ============================================
pause
