# Gerenciar Pedidos Conveniar

Aplicativo Windows para **Reabrir**, **Cancelar** ou **Encerrar** pedidos em lote no sistema Conveniar (facto.conveniar.com.br). Recebe uma planilha `.xlsx` com a coluna `Nº Pedido`, processa cada linha sequencialmente via Selenium e marca o status diretamente na planilha.

---

## Uso (usuário final)

1. Baixe `GerenciarPedidos.exe` na [última release](https://github.com/DaviTSelect/gerenciar-pedidos-conveniar/releases/latest)
2. Coloque o `.exe` na pasta desejada
3. Execute `GerenciarPedidos.exe`
4. Selecione a planilha `.xlsx` (coluna obrigatória: `Nº Pedido`)
5. Informe usuário e senha do Conveniar na interface
6. Escolha a ação (Reabrir / Cancelar / Encerrar) e clique em **Iniciar**

O app atualiza automaticamente ao abrir, quando uma versão nova for publicada.

---

## Planilha esperada

| Nº Pedido | Status |
|-----------|--------|
| 00123     |        |
| 00456     | ok     |

- Linhas com `Status = ok` são ignoradas (retomada automática após interrupção)
- O status é gravado imediatamente após cada pedido processado

---

## Estrutura do projeto

```
reabrir-cancelar-encerrar_pedidos/
├── src/
│   └── pedidos/
│       ├── auto_update.py     # Atualização automática via GitHub Releases
│       ├── automacao.py       # Selenium: login, busca e ações nos pedidos
│       ├── config.py          # URLs, seletores XPath, constantes
│       ├── interface.py       # GUI PySide6 (janela principal)
│       └── version.py         # ← ALTERE AQUI para publicar nova versão
├── tests/
│   ├── test_automacao.py
│   └── test_auto_update.py
├── main.py
├── GerenciarPedidos.spec      # Configuração do PyInstaller
├── requirements.txt
├── requirements-build.txt
├── release.bat                # ← Execute para publicar nova release
└── CHANGELOG.md
```

---

## Publicar nova versão

> **Fluxo completo:** altere `version.py` → commite → rode `release.bat`

### Passo a passo

**1. Atualize a versão**

Edite [src/pedidos/version.py](src/pedidos/version.py):

```python
VERSION = "1.2.0"   # ← novo número
```

**2. Atualize o CHANGELOG**

Adicione as entradas da versão em [CHANGELOG.md](CHANGELOG.md).

**3. Commite e envie**

```bat
git add src\pedidos\version.py CHANGELOG.md
git commit -m "release: v1.2.0"
git push origin main
```

**4. Execute `release.bat`** (duplo clique ou terminal)

```
release.bat
```

O script faz automaticamente:
- Lê a versão do `version.py`
- Verifica se a tag já existe (evita duplicatas)
- Instala dependências de build
- Roda os testes (`pytest`) — interrompe se falhar
- Compila `GerenciarPedidos.exe` via PyInstaller
- Calcula SHA-256 do `.exe`
- Cria a tag `v1.2.0` e envia para o GitHub
- Publica a release com o `.exe` e o `.sha256` anexados

**Resultado:** release disponível para download em ~2 minutos.

### Pré-requisitos (apenas para publicar)

| Ferramenta | Finalidade | Verificar |
|-----------|-----------|-----------|
| Python + `.venv` | Build via PyInstaller | `.venv\Scripts\python.exe --version` |
| PyInstaller | Empacotar o `.exe` | instalado por `requirements-build.txt` |
| GitHub CLI (`gh`) | Publicar a release | `gh --version` |
| Git | Criar/enviar tag | `git --version` |

Instalar `gh` CLI: https://cli.github.com  
Autenticar uma única vez: `gh auth login`

---

## Desenvolvimento

### Setup inicial

```powershell
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\pip.exe install -r requirements-build.txt
```

### Rodar em desenvolvimento

```powershell
.venv\Scripts\python.exe main.py
```

### Rodar testes

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

### Compilar localmente (sem publicar)

```bat
builder.bat
```

O `.exe` gerado fica em `dist\GerenciarPedidos.exe`.

---

## Atualização automática

O app verifica a [última release no GitHub](https://github.com/DaviTSelect/gerenciar-pedidos-conveniar/releases/latest) ao iniciar. Se houver versão nova:
- Baixa o `.exe` e verifica o SHA-256 (via arquivo `.sha256` da release)
- Agenda a troca via PowerShell após o app fechar
- Reinicia automaticamente com a nova versão

O indicador no cabeçalho mostra o status:
- 🟢 Verde — atualizado
- 🟡 Amarelo — nova versão disponível ou atualizando
- ⚫ Cinza — sem conexão ou erro

---

## Repositório

[github.com/DaviTSelect/gerenciar-pedidos-conveniar](https://github.com/DaviTSelect/gerenciar-pedidos-conveniar)
