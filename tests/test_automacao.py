from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import pandas as pd

from pedidos.automacao import _buscar_link_resultado, carregar_pedidos, validar_configuracao
from pedidos.config import FINAL_ACTIONS, ORDER_SELECTORS


class CarregarPedidosTests(unittest.TestCase):
    def test_preserva_ids_com_zero_a_esquerda_e_ignora_vazios(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({"Nº Pedido": ["00123", None, "  ", "00456"]}).to_excel(
                path, index=False
            )

            self.assertEqual(carregar_pedidos(path), ["00123", "00456"])

    def test_informa_quando_coluna_nao_existe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pedidos.xlsx"
            pd.DataFrame({"Outro campo": ["123"]}).to_excel(path, index=False)

            with self.assertRaisesRegex(ValueError, "Nº Pedido"):
                carregar_pedidos(path)


class ConfiguracaoTests(unittest.TestCase):
    def test_configuracao_incompleta_lista_seletores_necessarios(self):
        with self.assertRaisesRegex(ValueError, "campo do número do pedido"):
            validar_configuracao(ORDER_SELECTORS, FINAL_ACTIONS[0])


class ResultadoPesquisaTests(unittest.TestCase):
    def test_sem_registros_na_reabertura_indica_pedido_ja_reaberto(self):
        driver = Mock()
        driver.find_elements.return_value = [Mock()]
        wait = Mock()

        resultado = _buscar_link_resultado(
            driver, wait, "54376/2026", FINAL_ACTIONS[0], ORDER_SELECTORS
        )

        self.assertIsNone(resultado)
        wait.until.assert_not_called()

    def test_sem_registros_nao_pula_outras_acoes(self):
        driver = Mock()
        driver.find_elements.return_value = [Mock()]
        link = Mock()
        wait = Mock()
        wait.until.return_value = link

        resultado = _buscar_link_resultado(
            driver, wait, "54376/2026", FINAL_ACTIONS[1], ORDER_SELECTORS
        )

        self.assertIs(resultado, link)
        wait.until.assert_called_once()


class ReabrirSelectorsTests(unittest.TestCase):
    def test_usa_os_seletores_da_janela_de_reabertura(self):
        action = FINAL_ACTIONS[0]

        self.assertEqual(
            action.reason_selector,
            "//*[@id='ctl00_ContentPlaceHolder1_txtJustificativaReabrirPedido']",
        )
        self.assertEqual(
            action.submit_selector,
            "//*[@id='ctl00_ContentPlaceHolder1_btnConfirmarReabrirPedido']",
        )


if __name__ == "__main__":
    unittest.main()
