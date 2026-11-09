"""URLs, limites e seletores XPath conhecidos do Conveniar."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _carregar_env() -> None:
    """Carrega .env sem dependência externa. Variáveis já definidas não são sobrescritas."""
    if getattr(sys, "frozen", False):
        env_path = Path(sys.executable).parent / ".env"
    else:
        env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        if chave and chave not in os.environ:
            os.environ[chave] = valor.strip()


_carregar_env()

CONVENIAR_USERNAME: str = os.environ.get("CONVENIAR_USERNAME", "")
CONVENIAR_PASSWORD: str = os.environ.get("CONVENIAR_PASSWORD", "")

LOGIN_URL = (
    "https://facto.conveniar.com.br/Fundacao/Forms/Convenio/"
    "ConsultaPedidoPagamento.aspx"
)
ORDERS_URL = LOGIN_URL
ORDER_COLUMN = "Nº Pedido"
WAIT_SECONDS = 20
LOADING_XPATH = "/html/body/div[3]/form/div[4]/div[1]/div/div[2]/div[1]/img"

PASTA_USUARIO = Path.home()
CHROME_BINARY = PASTA_USUARIO / "Chrome" / "GoogleChrome" / "App" / "Chrome-bin" / "chrome.exe"
CHROMEDRIVER_PATH = PASTA_USUARIO / "Chrome" / "chromedriver.exe"


@dataclass(frozen=True)
class FinalAction:
    label: str
    selector: str
    reason_selector: str = ""
    submit_selector: str = ""


@dataclass(frozen=True)
class PageSelectors:
    username: str
    password: str
    login_button: str
    # Checkboxes de tipo
    checkbox_bolsas: str
    checkbox_pessoa_fisica: str
    checkbox_diaria: str
    # Campos de pesquisa
    order_number: str
    date_start: str
    date_end_1: str
    date_end_2: str
    status_select: str
    search_button: str
    search_result: str
    # Aba do pedido
    order_tab: str
    # Estorno de lançamentos
    cancel_refunds: str
    refund_empty_message: str
    refund_collapse: str
    refund_select: str
    refund_reason: str
    refund_submit: str
    refund_confirm: str
    # Cancelar lançamentos
    cancel_entries: str
    entries_empty_message: str
    entries_collapse: str
    entries_select: str
    entries_reason: str
    entries_submit: str


SELECTORS = PageSelectors(
    username="//*[@id='ctl00_ContentPlaceHolder1_ObjWucLoginCaptcha_lgUsuario_UserName']",
    password="//*[@id='ctl00_ContentPlaceHolder1_ObjWucLoginCaptcha_lgUsuario_Password']",
    login_button="//*[@id='ctl00_ContentPlaceHolder1_ObjWucLoginCaptcha_lgUsuario_btnLogin']",
    checkbox_bolsas="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[2]/table/tbody/tr[1]/td[1]/span/input",
    checkbox_pessoa_fisica="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[2]/table/tbody/tr[3]/td[1]/span/input",
    checkbox_diaria="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[2]/table/tbody/tr[2]/td[2]/span/input",
    order_number="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[3]/input",
    date_start="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[8]/input[1]",
    date_end_1="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[9]/input[1]",
    date_end_2="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[9]/input[2]",
    status_select="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[14]/select",
    search_button="/html/body/div[3]/form/div[5]/div/div/div[2]/div/div[1]/fieldset/div/div/ul/li[15]/input[1]",
    search_result="//a[@title='Editar registro']",
    order_tab="/html/body/div[3]/form/div[5]/div/div/div[3]/div[1]/div[2]/div/div/div[1]/div[1]/ul/li[2]/a/span[2]",
    cancel_refunds="//*[@id='ctl00_ContentPlaceHolder1_btnEstornarLanc']",
    refund_empty_message="//table[@id='ctl00_ContentPlaceHolder1_EstornarLancamentoConvenioUserControl1_gvPrincipal']",
    refund_collapse="//div[@aria-labelledby='ui-dialog-title-DialogoEstornarLancamento']//a[contains(@class,'ui-dialog-titlebar-close')]",
    refund_select="//*[@id='ctl00_ContentPlaceHolder1_EstornarLancamentoConvenioUserControl1_gvPrincipal_ctl01_ckhHeader']",
    refund_reason="//*[@id='ctl00_ContentPlaceHolder1_EstornarLancamentoConvenioUserControl1_txtJustificativaEstornar']",
    refund_submit="//*[@id='ctl00_ContentPlaceHolder1_EstornarLancamentoConvenioUserControl1_btnEstornar']",
    refund_confirm="/html/body/div[9]/div[3]/div/button[1]/span",
    cancel_entries="//*[@id='ctl00_ContentPlaceHolder1_btnCancelHistorico']",
    entries_empty_message="//table[@id='ctl00_ContentPlaceHolder1_CancelarLancamentoConvenioUserControl1_gvPrincipal']",
    entries_collapse="//div[@aria-labelledby='ui-dialog-title-DialogoCancelaLancamento']//a[contains(@class,'ui-dialog-titlebar-close')]",
    entries_select="//*[@id='ctl00_ContentPlaceHolder1_CancelarLancamentoConvenioUserControl1_gvPrincipal_ctl01_chkHeader']",
    entries_reason="//*[@id='ctl00_ContentPlaceHolder1_CancelarLancamentoConvenioUserControl1_txtJustificativaCancel']",
    entries_submit="//*[@id='ctl00_ContentPlaceHolder1_CancelarLancamentoConvenioUserControl1_btnCancelar']",
)

ORDER_SELECTORS = SELECTORS

FINAL_ACTIONS = (
    FinalAction(
        label="Reabrir pedido",
        selector="//*[@id='ctl00_ContentPlaceHolder1_btnReabrirPedidoOriginal']",
        reason_selector="//*[@id='ctl00_ContentPlaceHolder1_txtJustificativaReabrirPedido']",
        submit_selector="//*[@id='ctl00_ContentPlaceHolder1_btnConfirmarReabrirPedido']",
    ),
    FinalAction(
        label="Cancelar pedido",
        selector="//*[@id='ctl00_ContentPlaceHolder1_btnCancelarPedido']",
        reason_selector="//*[@id='ctl00_ContentPlaceHolder1_txtJustificativaCancelarPedido']",
        submit_selector="//*[@id='ctl00_ContentPlaceHolder1_btnConfirmarCancelarPedido']",
    ),
    FinalAction(
        label="Encerrar pedido",
        selector="//*[@id='ctl00_ContentPlaceHolder1_btnEncerrarPedido']",
        reason_selector="//*[@id='ctl00_ContentPlaceHolder1_txtJustificativaEncerrarPedido']",
        submit_selector="//*[@id='ctl00_ContentPlaceHolder1_btnConfirmarEncerrarPedido']",
    ),
)
