"""Leitura da planilha e processamento sequencial dos pedidos no Conveniar."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable

import pandas as pd
from openpyxl import load_workbook
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .config import (
    CHROME_BINARY,
    CHROMEDRIVER_PATH,
    FINAL_ACTIONS,
    LOADING_XPATH,
    LOGIN_URL,
    ORDER_COLUMN,
    ORDER_SELECTORS,
    WAIT_SECONDS,
    FinalAction,
    PageSelectors,
)

ProgressCallback = Callable[[str], None]

_ID_PLANO_TRABALHO = (
    "ctl00_ContentPlaceHolder1_ControleFinanceiroUserControl2"
    "_gvwLancamento_ctl02_lbtPlanoTrabalho"
)
_COLUNA_RESULTADO = "Item PT"
_COLUNA_STATUS = "Status"
_SEM_REGISTROS_XPATH = "//td[@colspan='15' and normalize-space(.)='Nenhum registro encontrado.']"


@dataclass(frozen=True)
class ProcessingSummary:
    total: int
    completed: int
    failed: tuple[str, ...]
    cancelled: bool
    output_file: str = ""


def carregar_pedidos(planilha: str | Path) -> list[tuple[int, str]]:
    """Retorna (linha_excel, numero_pedido) ignorando linhas com Status='ok'."""
    frame = pd.read_excel(planilha, dtype={ORDER_COLUMN: "string"})
    if ORDER_COLUMN not in frame.columns:
        colunas = ", ".join(str(c) for c in frame.columns)
        raise ValueError(
            f"A planilha precisa ter a coluna '{ORDER_COLUMN}'. "
            f"Colunas encontradas: {colunas or '(nenhuma)'}."
        )
    has_status = _COLUNA_STATUS in frame.columns
    pares: list[tuple[int, str]] = []
    for idx, val in frame[ORDER_COLUMN].items():
        texto = str(val).strip() if pd.notna(val) else ""
        if not texto:
            continue
        if has_status and pd.notna(frame.at[idx, _COLUNA_STATUS]):
            if str(frame.at[idx, _COLUNA_STATUS]).strip().lower() == "ok":
                continue
        pares.append((int(idx) + 2, texto))  # +1 índice 0-based→1-based, +1 linha do cabeçalho
    if not pares:
        raise ValueError(f"Nenhum pedido pendente encontrado em '{ORDER_COLUMN}'.")
    return pares


def validar_configuracao(action: FinalAction) -> None:
    if not action.selector.strip():
        raise ValueError(f"Seletor do botão '{action.label}' não configurado em config.py.")
    if not action.reason_selector.strip() or not action.submit_selector.strip():
        raise ValueError(f"Seletores do dialog de '{action.label}' não configurados em config.py.")


def _criar_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    if CHROME_BINARY.is_file():
        options.binary_location = str(CHROME_BINARY)
    # CREATE_NO_WINDOW evita que o processo chromedriver.exe abra janela de console
    _CREATE_NO_WINDOW = 0x08000000
    service = (
        Service(executable_path=str(CHROMEDRIVER_PATH), creationflags=_CREATE_NO_WINDOW)
        if CHROMEDRIVER_PATH.is_file()
        else Service(creationflags=_CREATE_NO_WINDOW)
    )
    return webdriver.Chrome(service=service, options=options)


def _aguardar(wait: WebDriverWait) -> None:
    wait.until(EC.invisibility_of_element_located((By.XPATH, LOADING_XPATH)))


def _clicar_js(driver, xpath: str) -> None:
    driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, xpath))


def _preencher_js(driver, xpath: str, texto: str) -> None:
    driver.execute_script(
        "arguments[0].value = arguments[1];",
        driver.find_element(By.XPATH, xpath),
        texto,
    )


def _buscar_link_resultado(
    driver,
    wait: WebDriverWait,
    order_id: str,
    action: FinalAction,
    selectors: PageSelectors,
) -> WebElement | None:
    if action == FINAL_ACTIONS[0] and driver.find_elements(By.XPATH, _SEM_REGISTROS_XPATH):
        return None

    try:
        return wait.until(EC.presence_of_element_located((By.XPATH, selectors.search_result)))
    except TimeoutException as exc:
        raise RuntimeError(
            f"Pedido {order_id}: nenhum link de edição apareceu em até "
            f"{WAIT_SECONDS} segundos após a pesquisa."
        ) from exc


def _fazer_login(driver, username: str, password: str, selectors: PageSelectors) -> None:
    wait = WebDriverWait(driver, WAIT_SECONDS)
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.username))).send_keys(username)
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.password))).send_keys(password)
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.login_button))).click()
    _aguardar(wait)


def _buscar_plano_trabalho(driver, wait: WebDriverWait, progress: ProgressCallback | None = None) -> str | None:
    """Clica no link do Plano de Trabalho, lê o item com situação 'confirmar' e fecha o painel."""
    def _log(msg: str) -> None:
        print(msg, flush=True)
        if progress:
            progress(msg)

    try:
        _log("PT: aguardando link do Plano de Trabalho...")
        elemento = wait.until(EC.element_to_be_clickable((By.ID, _ID_PLANO_TRABALHO)))
        driver.execute_script("arguments[0].click();", elemento)
        _aguardar(wait)
        _log("PT: link clicado, aguardando linhas da grid...")

        wait.until(lambda d: d.find_elements(
            By.XPATH,
            "//tr[@data-grupo-rubrica='23' and (@class='gridRow' or @class='gridAlternateRow')]",
        ))

        linhas = driver.find_elements(
            By.XPATH,
            "//tr[@data-grupo-rubrica='23' and (@class='gridRow' or @class='gridAlternateRow')]",
        )
        _log(f"PT: {len(linhas)} linha(s) encontradas na grid.")
        texto = None
        for linha in linhas:
            if linha.find_elements(
                By.XPATH,
                ".//span[contains(@class,'tema') and contains(@class,'confirmar')]",
            ):
                celulas = linha.find_elements(By.TAG_NAME, "td")
                if len(celulas) > 5:
                    texto = celulas[5].text.strip()
                _log(f"PT: item encontrado: {texto!r}")
                break

        # Clica no pai do ícone (o <button> que carrega o handler jQuery UI)
        _log("PT: tentando fechar o painel...")
        try:
            botao_fechar = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//span[contains(@class,'ui-icon-closethick')]/parent::*",
            )))
            driver.execute_script("arguments[0].click();", botao_fechar)
            # Aguarda o painel sumir do DOM e o loader terminar
            wait.until(EC.invisibility_of_element_located((
                By.XPATH,
                "//span[contains(@class,'ui-icon-closethick')]",
            )))
            _aguardar(wait)
            _log("PT: painel fechado.")
        except TimeoutException:
            _log("PT: AVISO — botão de fechar não encontrado ou painel não fechou no tempo limite.")

        return texto or None
    except (TimeoutException, NoSuchElementException) as exc:
        print(f"PT: exceção ao buscar plano de trabalho — {exc}", flush=True)
        return None


def _salvar_celula(planilha: str | Path, linha: int, coluna_nome: str, valor: str) -> None:
    """Grava um único valor na planilha original, criando a coluna se necessário."""
    wb = load_workbook(planilha)
    ws = wb.worksheets[0]
    cabecalhos = {
        str(ws.cell(1, c).value).strip(): c
        for c in range(1, ws.max_column + 1)
        if ws.cell(1, c).value is not None
    }
    col = cabecalhos.get(coluna_nome)
    if col is None:
        col = ws.max_column + 1
        ws.cell(1, col, coluna_nome)
    ws.cell(linha, col, valor)
    wb.save(planilha)
    wb.close()


def _processar_pedido(
    driver, order_id: str, action: FinalAction, selectors: PageSelectors,
    progress: ProgressCallback | None = None,
    on_pt_found: Callable[[str], None] | None = None,
) -> bool:
    """Processa um pedido e indica se ele já estava reaberto."""
    def _log(msg: str) -> None:
        print(msg, flush=True)
        if progress:
            progress(msg)

    wait = WebDriverWait(driver, WAIT_SECONDS)

    # Garante os três checkboxes de tipo marcados
    _log(f"[{order_id}] verificando checkboxes...")
    for xpath in (selectors.checkbox_bolsas, selectors.checkbox_pessoa_fisica, selectors.checkbox_diaria):
        cb = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", cb)
        if not cb.is_selected():
            cb.click()

    # Preenche número do pedido
    _log(f"[{order_id}] preenchendo número do pedido...")
    campo = wait.until(EC.presence_of_element_located((By.XPATH, selectors.order_number)))
    campo.clear()
    campo.send_keys(order_id)

    # Limpa campos de data
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.date_start))).clear()
    for xpath in (selectors.date_end_1, selectors.date_end_2):
        driver.execute_script(
            "arguments[0].value = '';",
            wait.until(EC.presence_of_element_located((By.XPATH, xpath))),
        )

    # Filtra por status "Enviado" (valor 17)
    _log(f"[{order_id}] selecionando status 'Enviado'...")
    Select(
        wait.until(EC.presence_of_element_located((By.XPATH, selectors.status_select)))
    ).select_by_value("17")

    # Pesquisa
    _log(f"[{order_id}] clicando em pesquisar...")
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.search_button))).click()
    _aguardar(wait)

    # Abre o primeiro resultado
    _log(f"[{order_id}] buscando link de edição nos resultados...")
    link = _buscar_link_resultado(driver, wait, order_id, action, selectors)
    if link is None:
        _log(
            f"[{order_id}] nenhum registro encontrado; considerando o pedido já "
            "reaberto e marcando como ok."
        )
        return True
    _log(f"[{order_id}] abrindo pedido...")
    driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", link)
    driver.execute_script("arguments[0].click();", link)
    _aguardar(wait)
    _log(f"[{order_id}] alternando para nova aba ({len(driver.window_handles)} janela(s))...")
    driver.switch_to.window(driver.window_handles[-1])
    _aguardar(wait)

    # Vai para a aba do pedido
    _log(f"[{order_id}] clicando na aba do pedido...")
    wait.until(EC.presence_of_element_located((By.XPATH, selectors.order_tab))).click()
    _aguardar(wait)

    # --- Plano de Trabalho: lê e salva o item antes de executar as ações ---
    _log(f"[{order_id}] buscando item do Plano de Trabalho...")
    plano_texto = _buscar_plano_trabalho(driver, wait, progress)
    if plano_texto and on_pt_found:
        on_pt_found(plano_texto)
    _log(f"[{order_id}] item PT: {plano_texto!r}. Iniciando estornos...")

    # --- Estornar lançamentos ---
    _log(f"[{order_id}] abrindo seção de estornos...")
    _clicar_js(driver, selectors.cancel_refunds)
    _aguardar(wait)
    _aguardar(wait)

    tabela_estorno = wait.until(EC.presence_of_element_located((By.XPATH, selectors.refund_empty_message)))
    linhas_estorno = tabela_estorno.find_elements(
        By.XPATH, ".//tr[@class='gridRow' or @class='gridAlternateRow']"
    )
    _log(f"[{order_id}] estornos: {len(linhas_estorno)} lançamento(s) encontrado(s).")
    if not linhas_estorno:
        _log(f"[{order_id}] estornos: nenhum lançamento, fechando diálogo...")
        _clicar_js(driver, selectors.refund_collapse)
        _aguardar(wait)
        wait.until(EC.invisibility_of_element_located((By.ID, "DialogoEstornarLancamento")))
    else:
        _log(f"[{order_id}] estornos: processando {len(linhas_estorno)} lançamento(s)...")
        _clicar_js(driver, selectors.refund_select)
        _aguardar(wait)
        _preencher_js(driver, selectors.refund_reason, "erro")
        _aguardar(wait)
        _clicar_js(driver, selectors.refund_submit)
        _aguardar(wait)
        try:
            driver.find_element(By.XPATH, selectors.refund_confirm).click()
        except NoSuchElementException:
            pass
        wait.until(EC.invisibility_of_element_located((By.ID, "DialogoEstornarLancamento")))
        _aguardar(wait)
        _log(f"[{order_id}] estornos: concluído.")

    # --- Cancelar lançamentos ---
    _log(f"[{order_id}] abrindo seção de cancelamento de lançamentos...")
    _clicar_js(driver, selectors.cancel_entries)
    _aguardar(wait)
    _aguardar(wait)

    tabela_lancamentos = wait.until(EC.presence_of_element_located((By.XPATH, selectors.entries_empty_message)))
    linhas_lancamentos = tabela_lancamentos.find_elements(
        By.XPATH, ".//tr[@class='gridRow' or @class='gridAlternateRow']"
    )
    _log(f"[{order_id}] lançamentos: {len(linhas_lancamentos)} linha(s) encontrada(s).")
    if not linhas_lancamentos:
        _log(f"[{order_id}] lançamentos: nenhum registro, fechando diálogo...")
        _clicar_js(driver, selectors.entries_collapse)
        _aguardar(wait)
        wait.until(EC.invisibility_of_element_located((By.ID, "DialogoCancelaLancamento")))
    else:
        _log(f"[{order_id}] lançamentos: processando {len(linhas_lancamentos)} linha(s)...")
        _clicar_js(driver, selectors.entries_select)
        _aguardar(wait)
        _preencher_js(driver, selectors.entries_reason, "erro")
        _aguardar(wait)
        _clicar_js(driver, selectors.entries_submit)
        _aguardar(wait)
        wait.until(EC.invisibility_of_element_located((By.ID, "DialogoCancelaLancamento")))
        _aguardar(wait)
        _log(f"[{order_id}] lançamentos: concluído.")

    # --- Ação final (Reabrir / Cancelar / Encerrar) ---
    _log(f"[{order_id}] executando ação final: {action.label}...")
    _clicar_js(driver, action.selector)
    _aguardar(wait)
    _aguardar(wait)
    _log(f"[{order_id}] aguardando campo de justificativa...")
    reason_selector = action.reason_selector
    submit_selector = action.submit_selector
    campo_final = wait.until(EC.visibility_of_element_located((By.XPATH, reason_selector)))
    driver.execute_script("arguments[0].value = arguments[1];", campo_final, "erro")
    _aguardar(wait)
    _log(f"[{order_id}] submetendo ação final...")
    botao_final = wait.until(EC.element_to_be_clickable((By.XPATH, submit_selector)))
    driver.execute_script("arguments[0].click();", botao_final)
    _aguardar(wait)
    wait.until(EC.invisibility_of_element_located((By.XPATH, submit_selector)))
    _aguardar(wait)
    _log(f"[{order_id}] ação final concluída.")

    # Fecha a aba do pedido e retorna à janela principal
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    return False


def processar_pedidos(
    planilha: str | Path,
    action_index: int,
    username: str,
    password: str,
    progress: ProgressCallback,
    cancel_event: Event | None = None,
) -> ProcessingSummary:
    """Faz login uma vez e processa cada linha da planilha em sequência."""
    if not 0 <= action_index < len(FINAL_ACTIONS):
        raise ValueError("Selecione uma das três opções disponíveis.")
    if not username.strip() or not password:
        raise ValueError("Informe o usuário e a senha no painel.")

    action = FINAL_ACTIONS[action_index]
    validar_configuracao(action)
    pares = carregar_pedidos(planilha)
    progress(f"Planilha carregada: {len(pares)} pedido(s).")

    driver = _criar_driver()
    completed = 0
    failed: list[str] = []
    cancelled = False
    try:
        progress("Acessando o Conveniar e realizando login...")
        _fazer_login(driver, username, password, ORDER_SELECTORS)
        progress("Login realizado. Iniciando o processamento dos pedidos.")

        for index, (linha_excel, order_id) in enumerate(pares, start=1):
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break

            progress(f"Pedido {index}/{len(pares)}: {order_id}")
            print(f"--- Pedido {index}/{len(pares)}: {order_id} ---", flush=True)

            def _salvar_pt(texto: str, _linha: int = linha_excel, _id: str = order_id) -> None:
                try:
                    _salvar_celula(planilha, _linha, _COLUNA_RESULTADO, texto)
                    progress(f"[{_id}] Item PT '{texto}' salvo na planilha.")
                    print(f"[{_id}] Item PT '{texto}' salvo.", flush=True)
                except Exception as exc:
                    progress(f"[{_id}] aviso: não foi possível salvar Item PT — {exc}")
                    print(f"[{_id}] aviso salvar PT: {exc}", flush=True)

            try:
                _processar_pedido(driver, order_id, action, ORDER_SELECTORS, progress, _salvar_pt)
                completed += 1
                try:
                    _salvar_celula(planilha, linha_excel, _COLUNA_STATUS, "ok")
                    progress(f"Pedido {order_id}: concluído — Status 'ok' salvo.")
                    print(f"[{order_id}] Status 'ok' salvo.", flush=True)
                except Exception as exc:
                    progress(f"Pedido {order_id}: aviso ao salvar status — {exc}")
            except (TimeoutException, WebDriverException, RuntimeError, NoSuchElementException) as exc:
                failed.append(f"{order_id}: {exc}")
                print(f"[{order_id}] FALHOU — {exc}", flush=True)
                progress(f"Pedido {order_id}: falhou — {exc}")
                try:
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.switch_to.window(handles[-1])
                        driver.close()
                    if driver.window_handles:
                        driver.switch_to.window(driver.window_handles[0])
                except (WebDriverException, IndexError):
                    pass
    finally:
        driver.quit()

    return ProcessingSummary(
        total=len(pares),
        completed=completed,
        failed=tuple(failed),
        cancelled=cancelled,
        output_file=str(planilha),
    )
