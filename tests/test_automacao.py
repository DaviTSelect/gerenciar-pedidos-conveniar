from pathlib import Path
import tempfile
import unittest

import pandas as pd

from pedidos.automacao import carregar_pedidos, validar_configuracao
from pedidos.config import FINAL_ACTIONS


class CarregarPedidosTests(unittest.TestCase):
    def test_retorna_linha_e_numero_ignorando_vazios(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({"Nº Pedido": ["00123", None, "  ", "00456"]}).to_excel(
                path, index=False
            )
            resultado = carregar_pedidos(path)
            numeros = [n for _, n in resultado]
            self.assertEqual(numeros, ["00123", "00456"])

    def test_linha_excel_comeca_em_2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({"Nº Pedido": ["00123"]}).to_excel(path, index=False)
            resultado = carregar_pedidos(path)
            self.assertEqual(resultado[0][0], 2)

    def test_ignora_linhas_com_status_ok(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({
                "Nº Pedido": ["00123", "00456"],
                "Status": ["ok", None],
            }).to_excel(path, index=False)
            resultado = carregar_pedidos(path)
            self.assertEqual(len(resultado), 1)
            self.assertEqual(resultado[0][1], "00456")

    def test_informa_quando_coluna_nao_existe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({"Outro campo": ["123"]}).to_excel(path, index=False)
            with self.assertRaisesRegex(ValueError, "Nº Pedido"):
                carregar_pedidos(path)

    def test_informa_quando_sem_pedidos_pendentes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({
                "Nº Pedido": ["00123"],
                "Status": ["ok"],
            }).to_excel(path, index=False)
            with self.assertRaises(ValueError):
                carregar_pedidos(path)


class ValidarConfiguracaoTests(unittest.TestCase):
    def test_acoes_padrao_sao_validas(self):
        for action in FINAL_ACTIONS:
            validar_configuracao(action)

    def test_falha_sem_seletor_principal(self):
        from pedidos.config import FinalAction
        action = FinalAction(
            label="Teste",
            selector="",
            reason_selector="//*[@id='txt']",
            submit_selector="//*[@id='btn']",
        )
        with self.assertRaises(ValueError):
            validar_configuracao(action)

    def test_falha_sem_reason_selector(self):
        from pedidos.config import FinalAction
        action = FinalAction(
            label="Teste",
            selector="//*[@id='btn']",
            reason_selector="",
            submit_selector="//*[@id='btn']",
        )
        with self.assertRaises(ValueError):
            validar_configuracao(action)


class SelectoresReabrirTests(unittest.TestCase):
    def test_seletores_de_reabrir(self):
        action = FINAL_ACTIONS[0]
        self.assertIn("txtJustificativaReabrirPedido", action.reason_selector)
        self.assertIn("btnConfirmarReabrirPedido", action.submit_selector)

    def test_seletores_de_cancelar(self):
        action = FINAL_ACTIONS[1]
        self.assertIn("txtJustificativaCancelarPedido", action.reason_selector)
        self.assertIn("btnConfirmarCancelarPedido", action.submit_selector)

    def test_seletores_de_encerrar(self):
        action = FINAL_ACTIONS[2]
        self.assertIn("txtJustificativaEncerrarPedido", action.reason_selector)
        self.assertIn("btnConfirmarEncerrarPedido", action.submit_selector)


if __name__ == "__main__":
    unittest.main()
