"""Testes para auto_update.py

Cobre:
- Parsing e comparação de versão
- Busca de release (HTTP mockado)
- Leitura do SHA-256 a partir do arquivo .sha256 (não do campo 'digest' da API do GitHub)
- Branches de erro do instalar()
- Todos os códigos de retorno do verificar_e_instalar()
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pedidos.auto_update import (
    NOME_EXE,
    _versao,
    buscar_release,
    instalar,
    pode_instalar,
    tem_versao_nova,
    verificar_e_instalar,
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _mock_resp(data: bytes) -> MagicMock:
    """Cria um mock de urllib.request.urlopen para leitura única."""
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = data
    return resp


def _mock_exe_resp(data: bytes) -> MagicMock:
    """Mock para download do EXE: retorna data na primeira leitura, EOF na segunda."""
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.side_effect = [data, b""]
    return resp


def _release(tag: str, com_sha: bool = True) -> dict:
    assets = [
        {
            "name": NOME_EXE,
            "browser_download_url": "https://example.com/GerenciarPedidos.exe",
        }
    ]
    if com_sha:
        assets.append(
            {
                "name": NOME_EXE + ".sha256",
                "browser_download_url": "https://example.com/GerenciarPedidos.exe.sha256",
            }
        )
    return {"tag_name": tag, "assets": assets}


# ─── _versao ────────────────────────────────────────────────────────────────

class VersaoParsingTests(unittest.TestCase):
    def test_sem_prefixo(self):
        self.assertEqual(_versao("1.2.3"), (1, 2, 3))

    def test_com_prefixo_v(self):
        self.assertEqual(_versao("v2.0.1"), (2, 0, 1))

    def test_patch_zero(self):
        self.assertEqual(_versao("v1.0.0"), (1, 0, 0))

    def test_letras_levantam_value_error(self):
        with self.assertRaises(ValueError):
            _versao("v1.2.beta")

    def test_vazio_levanta_value_error(self):
        with self.assertRaises(ValueError):
            _versao("")

    def test_string_sem_pontos_levanta_value_error(self):
        with self.assertRaises(ValueError):
            _versao("abc")


# ─── tem_versao_nova ────────────────────────────────────────────────────────

class TemVersaoNovaTests(unittest.TestCase):
    def test_release_mais_nova(self):
        self.assertTrue(tem_versao_nova(_release("v1.2.0"), "1.1.3"))

    def test_mesma_versao(self):
        self.assertFalse(tem_versao_nova(_release("v1.1.3"), "1.1.3"))

    def test_release_mais_antiga(self):
        self.assertFalse(tem_versao_nova(_release("v1.0.0"), "1.1.3"))

    def test_patch_mais_novo(self):
        self.assertTrue(tem_versao_nova(_release("v1.1.4"), "1.1.3"))

    def test_major_mais_novo(self):
        self.assertTrue(tem_versao_nova(_release("v2.0.0"), "1.9.9"))


# ─── pode_instalar ──────────────────────────────────────────────────────────

class PodeInstalarTests(unittest.TestCase):
    def test_false_sem_frozen(self):
        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "frozen", False, create=True):
            self.assertFalse(pode_instalar())

    def test_true_quando_frozen_no_windows(self):
        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "frozen", True, create=True):
            self.assertTrue(pode_instalar())

    def test_false_no_linux_mesmo_frozen(self):
        with patch.object(sys, "platform", "linux"), \
             patch.object(sys, "frozen", True, create=True):
            self.assertFalse(pode_instalar())


# ─── buscar_release ─────────────────────────────────────────────────────────

class BuscarReleaseTests(unittest.TestCase):
    def test_retorna_dict_parseado(self):
        payload = {"tag_name": "v1.2.0", "assets": []}
        with patch("urllib.request.urlopen", return_value=_mock_resp(json.dumps(payload).encode())):
            result = buscar_release()
        self.assertEqual(result["tag_name"], "v1.2.0")
        self.assertIsInstance(result["assets"], list)

    def test_lanca_oserror_em_falha_de_rede(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            with self.assertRaises(OSError):
                buscar_release()


# ─── instalar ───────────────────────────────────────────────────────────────

class InstalarTests(unittest.TestCase):
    def test_lanca_runtime_sem_asset_exe(self):
        release = {"tag_name": "v1.2.0", "assets": []}
        with self.assertRaisesRegex(RuntimeError, NOME_EXE):
            instalar(release)

    def test_lanca_runtime_sem_asset_sha256(self):
        """Sem o arquivo .sha256 na release, deve falhar — sem fallback para 'digest'."""
        release = _release("v1.2.0", com_sha=False)
        with self.assertRaisesRegex(RuntimeError, r"\.sha256"):
            instalar(release)

    def test_lanca_runtime_com_hash_invalido_no_arquivo(self):
        release = _release("v1.2.0")
        with patch("urllib.request.urlopen", return_value=_mock_resp(b"nao-e-um-hash")):
            with self.assertRaisesRegex(RuntimeError, "Hash inválido"):
                instalar(release)

    def test_le_hash_do_arquivo_sha256_nao_do_digest(self):
        """Bug corrigido: SHA-256 vem do .sha256 asset, não do campo 'digest' da API do GitHub."""
        conteudo_exe = b"conteudo do executavel"
        hash_real = hashlib.sha256(conteudo_exe).hexdigest()
        release = _release("v1.2.0")
        # Remove qualquer campo 'digest' para simular API real do GitHub
        for a in release["assets"]:
            a.pop("digest", None)

        respostas = [_mock_resp(hash_real.encode()), _mock_exe_resp(conteudo_exe)]
        call_n = 0

        def urlopen_side(req, timeout=None):
            nonlocal call_n
            r = respostas[call_n]
            call_n += 1
            return r

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / NOME_EXE
            fake_exe.write_bytes(b"")
            with patch("urllib.request.urlopen", side_effect=urlopen_side), \
                 patch("pedidos.auto_update._agendar_troca"), \
                 patch.object(sys, "executable", str(fake_exe)):
                instalar(release)  # não deve levantar

    def test_hash_em_formato_shasum_com_nome_arquivo(self):
        """Formato 'hash  filename' (saída padrão do sha256sum no Linux) também é aceito."""
        conteudo_exe = b"dados do exe"
        hash_real = hashlib.sha256(conteudo_exe).hexdigest()
        conteudo_sha = f"{hash_real}  {NOME_EXE}\n"
        release = _release("v1.2.0")

        respostas = [_mock_resp(conteudo_sha.encode()), _mock_exe_resp(conteudo_exe)]
        call_n = 0

        def urlopen_side(req, timeout=None):
            nonlocal call_n
            r = respostas[call_n]
            call_n += 1
            return r

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / NOME_EXE
            fake_exe.write_bytes(b"")
            with patch("urllib.request.urlopen", side_effect=urlopen_side), \
                 patch("pedidos.auto_update._agendar_troca"), \
                 patch.object(sys, "executable", str(fake_exe)):
                instalar(release)

    def test_lanca_runtime_com_hash_errado(self):
        """Hash no .sha256 não bate com o EXE baixado → RuntimeError."""
        hash_errado = "b" * 64
        conteudo_exe = b"exe de verdade"
        release = _release("v1.2.0")

        respostas = [_mock_resp(hash_errado.encode()), _mock_exe_resp(conteudo_exe)]
        call_n = 0

        def urlopen_side(req, timeout=None):
            nonlocal call_n
            r = respostas[call_n]
            call_n += 1
            return r

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / NOME_EXE
            fake_exe.write_bytes(b"")
            with patch("urllib.request.urlopen", side_effect=urlopen_side), \
                 patch.object(sys, "executable", str(fake_exe)):
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    instalar(release)


# ─── verificar_e_instalar ───────────────────────────────────────────────────

class VerificarEInstalarTests(unittest.TestCase):
    def test_retorna_atualizado(self):
        with patch("pedidos.auto_update.buscar_release", return_value=_release("v1.1.3")):
            self.assertEqual(verificar_e_instalar("1.1.3"), "atualizado")

    def test_retorna_sem_conexao_em_oserror(self):
        with patch("pedidos.auto_update.buscar_release", side_effect=OSError("timeout")):
            self.assertEqual(verificar_e_instalar("1.1.3"), "sem_conexao")

    def test_retorna_erro_em_excecao_generica(self):
        with patch("pedidos.auto_update.buscar_release", side_effect=RuntimeError("oops")):
            result = verificar_e_instalar("1.1.3")
        self.assertTrue(result.startswith("erro:"), f"Esperado 'erro:...', obtido: {result!r}")

    def test_retorna_nova_versao_quando_nao_frozen(self):
        with patch("pedidos.auto_update.buscar_release", return_value=_release("v1.2.0")), \
             patch("pedidos.auto_update.pode_instalar", return_value=False):
            self.assertEqual(verificar_e_instalar("1.1.3"), "nova_versao:v1.2.0")

    def test_retorna_atualizando_quando_frozen(self):
        with patch("pedidos.auto_update.buscar_release", return_value=_release("v1.2.0")), \
             patch("pedidos.auto_update.pode_instalar", return_value=True), \
             patch("pedidos.auto_update.instalar"):
            self.assertEqual(verificar_e_instalar("1.1.3"), "atualizando")

    def test_erro_sem_arquivo_sha256_nao_vira_sem_conexao(self):
        """Garantia de que RuntimeError do .sha256 ausente retorna 'erro:', não 'sem_conexao'."""
        release_sem_sha = _release("v1.2.0", com_sha=False)
        with patch("pedidos.auto_update.buscar_release", return_value=release_sem_sha), \
             patch("pedidos.auto_update.pode_instalar", return_value=True):
            result = verificar_e_instalar("1.1.3")
        self.assertTrue(result.startswith("erro:"), f"Esperado 'erro:...', obtido: {result!r}")


if __name__ == "__main__":
    unittest.main()
