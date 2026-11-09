"""Atualizador automático para aplicações Windows/PyInstaller --onefile via GitHub Releases públicos.

COMO USAR:
1. Copiar este arquivo para o pacote como ``auto_update.py``
2. Preencher REPO_GITHUB e NOME_EXE com os valores do projeto
3. Chamar ``verificar_e_instalar(versao_atual)`` na thread de atualização da GUI

Referência de implementação: ``Extrair dados de passagem`` → ``src/passagem/auto_update.py``
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

# ─── CONFIGURAR POR PROJETO ──────────────────────────────────────────────────
REPO_GITHUB = "DaviTSelect/gerenciar-pedidos-conveniar"
NOME_EXE    = "GerenciarPedidos.exe"
# ─────────────────────────────────────────────────────────────────────────────

_USER_AGENT = f"{NOME_EXE.replace('.exe', '')}-updater/1.0"

# Script PowerShell embutido: aguarda o processo fechar, troca o EXE e reinicia.
# Executado em background depois que o app encerra — o Windows não permite
# substituir um executável em uso.
_SCRIPT_TROCA = '''param([string]$Origem, [string]$Destino, [int]$PIDAntigo)
$ErrorActionPreference = 'Stop'
try { Wait-Process -Id $PIDAntigo -ErrorAction SilentlyContinue } catch {}
$Backup = "$Destino.bak"
if (Test-Path -LiteralPath $Backup) {
    if (-not (Test-Path -LiteralPath $Destino)) {
        Move-Item -LiteralPath $Backup -Destination $Destino
    }
    throw "Backup preexistente; atualização cancelada para preservar a recuperação."
}
for ($tentativa = 0; $tentativa -lt 60; $tentativa++) {
    $NovoNoDestino = $false
    try {
        if (Test-Path -LiteralPath $Destino) { Move-Item -LiteralPath $Destino -Destination $Backup }
        Move-Item -LiteralPath $Origem -Destination $Destino
        $NovoNoDestino = $true
        $ProcessoNovo = Start-Process -FilePath $Destino -WindowStyle Normal -PassThru
        Start-Sleep -Seconds 3
        $ProcessoNovo.Refresh()
        if ($ProcessoNovo.HasExited) { throw "Novo executável encerrou durante a verificação inicial." }
        if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue }
        exit 0
    } catch {
        if ($NovoNoDestino -and (Test-Path -LiteralPath $Destino)) {
            Remove-Item -LiteralPath $Destino -Force
        }
        if (-not (Test-Path -LiteralPath $Destino) -and (Test-Path -LiteralPath $Backup)) {
            Move-Item -LiteralPath $Backup -Destination $Destino
        }
        Start-Sleep -Seconds 1
    }
}
if (-not (Test-Path -LiteralPath $Destino) -and (Test-Path -LiteralPath $Backup)) {
    Move-Item -LiteralPath $Backup -Destination $Destino
}
if (Test-Path -LiteralPath $Destino) { Start-Process -FilePath $Destino -WindowStyle Normal }
exit 1
'''


def _versao(tag: str) -> tuple[int, ...]:
    """Converte ``v1.2.3`` em ``(1, 2, 3)`` para comparação numérica."""
    v = tag.removeprefix("v")
    if not v or any(not p.isdigit() for p in v.split(".")):
        raise ValueError(f"Versão inválida: {tag!r}. Use formato numérico, ex.: v1.2.3")
    return tuple(int(p) for p in v.split("."))


def pode_instalar() -> bool:
    """Retorna True apenas quando rodando como executável PyInstaller no Windows."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def buscar_release(repo: str = REPO_GITHUB) -> dict:
    """Consulta a última release publicada no GitHub. Lança exceção em caso de falha."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=12) as resposta:
        return json.load(resposta)


def tem_versao_nova(release: dict, versao_atual: str) -> bool:
    """Retorna True se a release publicada for mais recente que ``versao_atual``."""
    return _versao(release["tag_name"]) > _versao(versao_atual)


def instalar(release: dict, nome_exe: str = NOME_EXE) -> None:
    """Baixa o EXE, verifica SHA-256 via arquivo .sha256 e agenda a troca via PowerShell."""
    asset = next((a for a in release.get("assets", []) if a["name"] == nome_exe), None)
    if asset is None:
        raise RuntimeError(f"Release não contém o asset '{nome_exe}'")

    # Lê o hash do arquivo .sha256 (asset separado publicado pelo release.bat).
    # A API do GitHub não fornece campo 'digest' para assets — precisamos do arquivo.
    nome_sha = nome_exe + ".sha256"
    sha_asset = next((a for a in release.get("assets", []) if a["name"] == nome_sha), None)
    if sha_asset is None:
        raise RuntimeError(f"Release não contém '{nome_sha}'; atualização cancelada")
    req_sha = urllib.request.Request(
        sha_asset["browser_download_url"], headers={"User-Agent": _USER_AGENT}
    )
    with urllib.request.urlopen(req_sha, timeout=12) as resp:
        conteudo_sha = resp.read().decode("utf-8").strip()
    # Suporta tanto "abc123..." (hash puro) quanto "abc123...  filename" (formato shasum)
    hash_esperado = conteudo_sha.split()[0].lower()
    if len(hash_esperado) != 64 or not all(c in "0123456789abcdef" for c in hash_esperado):
        raise RuntimeError(f"Hash inválido no arquivo '{nome_sha}'")

    exe_atual = Path(sys.executable).resolve()
    if exe_atual.name.lower() != nome_exe.lower():
        raise RuntimeError(f"Executável instalado deve se chamar '{nome_exe}'")
    pasta = Path(tempfile.mkdtemp(prefix="app_update_"))
    baixado = pasta / nome_exe
    _baixar_exe(asset["browser_download_url"], baixado, hash_esperado)
    _agendar_troca(pasta, baixado, exe_atual)


def _baixar_exe(url: str, destino: Path, hash_esperado: str) -> None:
    """Baixa o EXE, valida o SHA-256 obrigatório e remove o arquivo em caso de falha."""
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(destino, "wb") as f:
            while bloco := resp.read(1_048_576):
                f.write(bloco)
                h.update(bloco)
        if h.hexdigest() != hash_esperado:
            raise RuntimeError("SHA-256 do arquivo baixado não confere — download corrompido")
    except Exception:
        destino.unlink(missing_ok=True)
        raise


def _agendar_troca(pasta: Path, baixado: Path, exe_atual: Path) -> None:
    """Grava o script PowerShell e o executa em background."""
    script = pasta / "trocar.ps1"
    script.write_text(_SCRIPT_TROCA, encoding="utf-8-sig")
    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            "-Origem", str(baixado),
            "-Destino", str(exe_atual),
            "-PIDAntigo", str(os.getpid()),
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
        # Impede que o novo EXE herde variáveis do PyInstaller temporário.
        env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
    )


def verificar_e_instalar(versao_atual: str) -> str:
    """Ponto de entrada principal. Retorna mensagem de status para exibir na GUI.

    Chamar em QThread ou threading.Thread — nunca na thread principal.

    Retornos possíveis:
    - "atualizado"       → app já está na versão mais recente
    - "atualizando"      → download iniciado; app vai fechar para trocar o EXE
    - "sem_conexao"      → falha de rede (não bloquear o usuário)
    - "erro:<mensagem>"  → outro erro inesperado
    """
    try:
        release = buscar_release()
        if not tem_versao_nova(release, versao_atual):
            return "atualizado"
        if pode_instalar():
            instalar(release)
            return "atualizando"
        return f"nova_versao:{release['tag_name']}"
    except OSError:
        return "sem_conexao"
    except Exception as exc:
        return f"erro:{exc}"
