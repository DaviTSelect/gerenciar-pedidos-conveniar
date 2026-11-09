@echo off
echo ============================================
echo  Build - Gerenciar Pedidos Conveniar
echo ============================================

echo.
echo [1/3] Instalando dependencias de build...
pip install -r requirements-build.txt
if %ERRORLEVEL% neq 0 ( echo ERRO ao instalar dependencias & pause & exit /b 1 )

echo.
echo [2/3] Executando testes...
set PYTHONPATH=src
python -m pytest tests -q
if %ERRORLEVEL% neq 0 ( echo ERRO nos testes & pause & exit /b 1 )

echo.
echo [3/3] Gerando executavel...
if exist dist rmdir /s /q dist
pyinstaller GerenciarPedidos.spec --noconfirm
if %ERRORLEVEL% neq 0 ( echo ERRO no PyInstaller & pause & exit /b 1 )

if not exist "dist\GerenciarPedidos.exe" (
    echo ERRO: dist\GerenciarPedidos.exe nao encontrado
    pause & exit /b 1
)

echo.
echo ============================================
echo  Build concluido: dist\GerenciarPedidos.exe
echo ============================================
pause
