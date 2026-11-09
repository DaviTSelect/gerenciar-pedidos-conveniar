"""Interface gráfica PySide6 para gerenciamento de pedidos no Conveniar.

Como a janela está organizada:
- Painel esquerdo: descrição da ação selecionada.
- Cartão direito: seletor de modo (3 abas), etapas, log e rodapé com botões.
- Threading via QThread com sinais; nenhum componente da tela é acessado direto da thread.
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QThread

from .automacao import ProcessingSummary, processar_pedidos
from .auto_update import verificar_e_instalar
from .config import FINAL_ACTIONS
from .version import APP_NAME, NOME_EXE, VERSION

_MUTEX_INSTANCIA = None

BG = "#203447"
TEXT = "#efede5"
ACTION = "#e94c1f"
COR_DIVISOR_ESCURO = "#415364"
COR_ICONE = "#7a8791"
COR_SELECIONADO = "#317458"

UPDATE_OK = "#53b88c"
UPDATE_BUSY = "#e9b44c"
UPDATE_UNKNOWN = "#85929c"

ESTILO_FUNDO_ICONE = "background: #e9eef0; border-radius: 12px;"
ESTILO_FUNDO_ICONE_SELECIONADO = "background: #e5f4ed; border-radius: 12px;"
ESTILO_BOTAO_LINHA = """QPushButton {background:#ffffff; border:1px solid #d9dddc; border-radius:9px;
    color:#344a5b; font-family:"Segoe UI"; font-size:11px; font-weight:600; padding:0 12px;}
    QPushButton:hover {background:#f1f3f1; border-color:#b5bec3;}"""
ESTILO_INICIAR_ATIVO = f"""QPushButton {{background:{ACTION}; color:white; border:none; border-radius:9px;
    font:600 11px "Segoe UI"; padding:0 19px;}}
    QPushButton:hover {{background:#d74118;}}"""
ESTILO_INICIAR_INATIVO = """QPushButton {background:#d8dad9; color:#92999b; border:none;
    border-radius:9px; font:600 11px "Segoe UI"; padding:0 19px;}"""
ESTILO_PARAR = """QPushButton {background:transparent; border:1px solid #d9dddc; border-radius:9px;
    color:#344a5b; font:600 11px "Segoe UI"; padding:0 19px;}
    QPushButton:hover {background:#f5f5f5;}
    QPushButton:disabled {color:#b0b8bd; border-color:#e5e7e6;}"""

MODE_REABRIR = 0
MODE_CANCELAR = 1
MODE_ENCERRAR = 2

MODE_TEXTS = {
    MODE_REABRIR: {
        "eyebrow": "R E A B R I R   P E D I D O S",
        "intro": "Selecione a planilha com os pedidos. O sistema irá reabrir cada um, estornar lançamentos, cancelar entradas e confirmar a reabertura.",
        "title": "Configurar reabertura",
        "subtitle": "Preencha as etapas para continuar",
        "start": "Iniciar reabertura   →",
        "running": "Reabertura em andamento",
        "running_hint": "Aguarde: cada pedido está sendo processado no Conveniar.",
        "done": "Reabertura concluída",
    },
    MODE_CANCELAR: {
        "eyebrow": "C A N C E L A R   P E D I D O S",
        "intro": "Selecione a planilha com os pedidos. O sistema irá cancelar cada um, estornar lançamentos, cancelar entradas e confirmar o cancelamento.",
        "title": "Configurar cancelamento",
        "subtitle": "Preencha as etapas para continuar",
        "start": "Iniciar cancelamento   →",
        "running": "Cancelamento em andamento",
        "running_hint": "Aguarde: cada pedido está sendo processado no Conveniar.",
        "done": "Cancelamento concluído",
    },
    MODE_ENCERRAR: {
        "eyebrow": "E N C E R R A R   P E D I D O S",
        "intro": "Selecione a planilha com os pedidos. O sistema irá encerrar cada um após estornar lançamentos e cancelar entradas.",
        "title": "Configurar encerramento",
        "subtitle": "Preencha as etapas para continuar",
        "start": "Iniciar encerramento   →",
        "running": "Encerramento em andamento",
        "running_hint": "Aguarde: cada pedido está sendo processado no Conveniar.",
        "done": "Encerramento concluído",
    },
}

ICON_FILENAME = "logo.ico"


def _garantir_instancia_unica() -> bool:
    global _MUTEX_INSTANCIA
    if sys.platform != "win32":
        return True
    _MUTEX_INSTANCIA = ctypes.windll.kernel32.CreateMutexW(None, False, "GerenciarPedidosConveniar_Mutex_v1")
    return ctypes.windll.kernel32.GetLastError() != 183


def caminho_recurso(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parents[2]
    return base / filename


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class ProcessingWorker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, spreadsheet: str, action_index: int, username: str,
                 password: str, cancel_event: Event, headless: bool = False) -> None:
        super().__init__()
        self.spreadsheet = spreadsheet
        self.action_index = action_index
        self.username = username
        self.password = password
        self.cancel_event = cancel_event
        self.headless = headless

    def run(self) -> None:
        try:
            result = processar_pedidos(
                self.spreadsheet,
                self.action_index,
                self.username,
                self.password,
                self.progress.emit,
                self.cancel_event,
                headless=self.headless,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.password = ""


class UpdateWorker(QThread):
    status_color = Signal(str, str)
    done = Signal()

    def run(self) -> None:
        try:
            result = verificar_e_instalar(VERSION)
            if result == "atualizado":
                self.status_color.emit(UPDATE_OK, f"v{VERSION} · atualizado")
            elif result == "atualizando":
                self.status_color.emit(UPDATE_BUSY, "Atualizando... o app será reiniciado")
                self.done.emit()
            elif result.startswith("nova_versao:"):
                tag = result.split(":", 1)[1]
                self.status_color.emit(UPDATE_BUSY, f"Nova versão disponível: {tag}")
            elif result == "sem_conexao":
                self.status_color.emit(UPDATE_UNKNOWN, f"v{VERSION} · sem conexão")
            else:
                self.status_color.emit(UPDATE_UNKNOWN, f"v{VERSION}")
        except Exception:
            self.status_color.emit(UPDATE_UNKNOWN, f"v{VERSION}")


# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------

class Icon(QWidget):
    def __init__(self, kind, color=COR_ICONE, size=24, parent=None):
        super().__init__(parent)
        self.kind, self.color = kind, color
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width() / 24, self.height() / 24)
        pen = QPen(QColor(self.color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if self.kind == "folder":
            self._pasta(p, seta=False)
        elif self.kind == "save":
            self._pasta(p, seta=True)
        elif self.kind == "file":
            self._arquivo(p)
        elif self.kind == "check":
            pen.setWidthF(2)
            p.setPen(pen)
            self._check(p)
        elif self.kind == "key":
            self._chave(p)
        p.end()

    @staticmethod
    def _linha(p, x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _pasta(self, p, seta):
        path = QPainterPath()
        path.moveTo(3.75, 16.25)
        path.lineTo(3.75, 6.75)
        path.cubicTo(3.75, 5.65, 4.65, 4.75, 5.75, 4.75)
        path.lineTo(9.11, 4.75)
        path.lineTo(11.91, 7.75)
        path.lineTo(18.25, 7.75)
        path.cubicTo(19.35, 7.75, 20.25, 8.65, 20.25, 9.75)
        path.lineTo(20.25, 16.25)
        path.cubicTo(20.25, 18, 19, 19.25, 17.25, 19.25)
        path.lineTo(6.75, 19.25)
        path.cubicTo(5, 19.25, 3.75, 18, 3.75, 16.25)
        p.drawPath(path)
        if seta:
            self._linha(p, 12, 10.5, 12, 15.5)
            self._linha(p, 10, 13.5, 12, 15.5)
            self._linha(p, 14, 13.5, 12, 15.5)

    def _arquivo(self, p):
        path = QPainterPath()
        path.moveTo(7, 3.75)
        path.lineTo(13.17, 3.75)
        path.lineTo(18, 8.58)
        path.lineTo(18, 20.25)
        path.lineTo(7, 20.25)
        path.cubicTo(5.7, 20.25, 5, 19.4, 5, 18.25)
        path.lineTo(5, 5.75)
        path.cubicTo(5, 4.6, 5.8, 3.75, 7, 3.75)
        p.drawPath(path)
        self._linha(p, 13.5, 4, 13.5, 8.5)
        self._linha(p, 13.5, 8.5, 18, 8.5)
        self._linha(p, 8.5, 13, 15.25, 13)
        self._linha(p, 8.5, 16.5, 13.25, 16.5)

    @staticmethod
    def _check(p):
        path = QPainterPath()
        path.moveTo(6.75, 12.25)
        path.lineTo(10, 15.5)
        path.lineTo(17.25, 8.25)
        p.drawPath(path)

    def _chave(self, p):
        p.drawEllipse(QPointF(9, 14), 4.5, 4.5)
        self._linha(p, 12.5, 10.8, 20.5, 3)
        self._linha(p, 18, 5.5, 20.5, 3)
        self._linha(p, 15.5, 8, 18, 5.5)


def criar_rotulo(text, size, color, weight=QFont.Normal, wrap=False):
    w = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setWeight(weight)
    w.setFont(f)
    w.setStyleSheet(f"color: {color}; background: transparent;")
    w.setWordWrap(wrap)
    return w


def criar_divisor(color):
    d = QFrame()
    d.setFixedHeight(1)
    d.setStyleSheet(f"background:{color}; border:none;")
    return d


class SelectionRow(QFrame):
    def __init__(self, number, title, description, button_text, icon_kind, choose):
        super().__init__()
        self.button_text = button_text
        self.icon_kind = icon_kind
        self.setObjectName("selectionRow")
        self.setStyleSheet("#selectionRow { background: transparent; border: none; }")
        self.setMinimumHeight(110)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 18, 16, 18)
        outer.setSpacing(12)
        self.icon_holder = QFrame()
        self.icon_holder.setFixedSize(43, 43)
        self.icon_holder.setStyleSheet(ESTILO_FUNDO_ICONE)
        icon_lay = QHBoxLayout(self.icon_holder)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        self._icon_lay = icon_lay
        self._icon_lay.addWidget(Icon(icon_kind))
        outer.addWidget(self.icon_holder, 0, Qt.AlignTop)
        outer.addLayout(self._montar_textos(number, title, description), 1)
        self.button = QPushButton(button_text)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setMinimumWidth(126)
        self.button.setFixedHeight(39)
        self.button.setStyleSheet(ESTILO_BOTAO_LINHA)
        self.button.clicked.connect(choose)
        outer.addWidget(self.button, 0, Qt.AlignVCenter)

    def _montar_textos(self, number, title, description) -> QLayout:
        content = QVBoxLayout()
        content.setSpacing(0)
        content.setContentsMargins(0, 1, 0, 0)
        head = QHBoxLayout()
        head.setSpacing(9)
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(criar_rotulo("ETAPA " + number, 9, "#7b8791", QFont.Bold))
        self.status = criar_rotulo("SELECIONADO", 8, COR_SELECIONADO, QFont.Bold)
        self.status.setStyleSheet(f"color: {COR_SELECIONADO}; background: #e5f4ed; border-radius: 9px; padding: 3px 8px;")
        self.status.hide()
        head.addWidget(self.status)
        head.addStretch()
        content.addLayout(head)
        content.addSpacing(5)
        content.addWidget(criar_rotulo(title, 12, BG, QFont.DemiBold))
        content.addSpacing(4)
        content.addWidget(criar_rotulo(description, 10, "#6d7780", wrap=True))
        self.current = criar_rotulo("", 10, "#344b5e", QFont.Medium)
        self.current.hide()
        content.addSpacing(5)
        content.addWidget(self.current)
        content.addStretch()
        return content

    def definir_valor(self, value):
        selected = bool(value)
        self.status.setVisible(selected)
        self.current.setText(value)
        self.current.setToolTip(value)
        self.current.setVisible(selected)
        self.button.setText("Alterar" if selected else self.button_text)
        old = self._icon_lay.takeAt(0)
        if old and old.widget():
            old.widget().deleteLater()
        self._icon_lay.addWidget(
            Icon("check" if selected else self.icon_kind,
                 COR_SELECIONADO if selected else COR_ICONE)
        )
        self.icon_holder.setStyleSheet(
            ESTILO_FUNDO_ICONE_SELECIONADO if selected else ESTILO_FUNDO_ICONE
        )

    def set_enabled(self, enabled: bool):
        self.button.setEnabled(enabled)


class CredentialsRow(QFrame):
    """Etapa de credenciais: dois campos inline (usuário + senha)."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("credRow")
        self.setStyleSheet("#credRow { background: transparent; border: none; }")
        self.setMinimumHeight(110)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 18, 16, 18)
        outer.setSpacing(12)

        icon_holder = QFrame()
        icon_holder.setFixedSize(43, 43)
        icon_holder.setStyleSheet(ESTILO_FUNDO_ICONE)
        icon_lay = QHBoxLayout(icon_holder)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        icon_lay.addWidget(Icon("key"))
        outer.addWidget(icon_holder, 0, Qt.AlignTop)

        content = QVBoxLayout()
        content.setSpacing(0)
        content.setContentsMargins(0, 1, 0, 0)
        content.addWidget(criar_rotulo("ETAPA 02", 9, "#7b8791", QFont.Bold))
        content.addSpacing(5)
        content.addWidget(criar_rotulo("Credenciais", 12, BG, QFont.DemiBold))
        content.addSpacing(6)

        fields = QHBoxLayout()
        fields.setSpacing(10)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuário")
        self.username_input.setFixedHeight(32)
        self.username_input.setStyleSheet(
            "QLineEdit {background:#ffffff; border:1px solid #d9dddc; border-radius:7px;"
            " color:#344a5b; font:11px 'Segoe UI'; padding:0 8px;}"
            " QLineEdit:focus {border-color:#a0b0bc;}"
        )
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(32)
        self.password_input.setStyleSheet(self.username_input.styleSheet())
        fields.addWidget(self.username_input)
        fields.addWidget(self.password_input)
        content.addLayout(fields)

        content.addSpacing(4)
        content.addWidget(criar_rotulo("A senha não é salva e nunca sai do computador.", 9, "#9aa3a9"))
        content.addStretch()
        outer.addLayout(content, 1)

        self.username_input.textChanged.connect(self.changed)
        self.password_input.textChanged.connect(self.changed)

    @property
    def username(self) -> str:
        return self.username_input.text().strip()

    @property
    def password(self) -> str:
        return self.password_input.text()

    def set_enabled(self, enabled: bool):
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------

class App(QWidget):
    sinal_update_status = Signal(str, str)
    sinal_update_reiniciar = Signal()
    sinal_tarefa_concluida = Signal(object)
    sinal_tarefa_falhou = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(1180, 755)
        self.setMinimumSize(900, 675)
        self.setStyleSheet(f"background: {BG};")
        self.spreadsheet = ""
        self.mode = MODE_REABRIR
        self.worker: ProcessingWorker | None = None
        self.cancel_event = Event()
        self.started = False

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 24, 48, 26)
        root.setSpacing(0)
        self._montar_cabecalho(root)
        center = QHBoxLayout()
        center.setSpacing(60)
        center.addLayout(self._montar_painel_esquerdo(), 4)
        center.addWidget(self._montar_cartao(), 9)
        root.addLayout(center, 1)
        self._montar_rodape(root)

        self.sinal_update_status.connect(self._on_update_status)
        self.sinal_update_reiniciar.connect(self._ao_reiniciar_update)
        self.sinal_tarefa_concluida.connect(self._ao_concluir)
        self.sinal_tarefa_falhou.connect(self._ao_falhar)

        self._iniciar_update()
        self.definir_modo(MODE_REABRIR)

    # --- Montagem ----------------------------------------------------------------

    def _montar_cabecalho(self, root):
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(5)
        heading.addWidget(criar_rotulo("G E R E N C I A R   P E D I D O S", 9, "#85929c", QFont.Bold))
        heading.addWidget(criar_rotulo(APP_NAME, 14, TEXT, QFont.DemiBold))
        header.addLayout(heading)
        header.addStretch()
        self.update_dot = QLabel("●")
        self.update_dot.setStyleSheet(f"color:{UPDATE_BUSY}; background:transparent; font-size:14px;")
        header.addWidget(self.update_dot)
        self.update_text = criar_rotulo("Verificando atualização...", 10, "#a0aab1", QFont.Medium)
        header.addWidget(self.update_text)
        root.addLayout(header)
        root.addSpacing(20)
        root.addWidget(criar_divisor(COR_DIVISOR_ESCURO))

    def _montar_painel_esquerdo(self) -> QLayout:
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        left.addStretch()
        self.eyebrow = criar_rotulo("", 9, ACTION, QFont.Bold)
        left.addWidget(self.eyebrow)
        left.addSpacing(20)
        left.addWidget(criar_rotulo("Automatize seus pedidos\ncom confiança.", 26, TEXT, QFont.DemiBold, True))
        left.addSpacing(22)
        self.intro = criar_rotulo("", 11, "#a5afb6", wrap=True)
        self.intro.setMinimumWidth(240)
        self.intro.setMaximumWidth(340)
        left.addWidget(self.intro)
        left.addSpacing(37)
        left.addWidget(criar_divisor(COR_DIVISOR_ESCURO))
        left.addSpacing(24)
        security = QHBoxLayout()
        security.setSpacing(14)
        circle = QFrame()
        circle.setFixedSize(34, 34)
        circle.setStyleSheet("background:#304658; border-radius:17px;")
        ci = QHBoxLayout(circle)
        ci.setContentsMargins(5, 5, 5, 5)
        ci.addWidget(Icon("file", "#a6b4bd", 20))
        security.addWidget(circle, 0, Qt.AlignTop)
        security.addWidget(
            criar_rotulo("Os dados são processados localmente e não são enviados a nenhum servidor.", 10, "#8998a3", wrap=True), 1
        )
        left.addLayout(security)
        left.addStretch()
        return left

    def _montar_cartao(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("#card {background: #f8f7f3; border-radius: 18px;}")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(52)
        shadow.setOffset(0, 22)
        shadow.setColor(QColor(6, 18, 28, 80))
        card.setGraphicsEffect(shadow)
        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self._montar_seletor_modo(layout)
        self._montar_titulo_cartao(layout)
        layout.addWidget(criar_divisor("#dde1df"))
        self._montar_paginas(layout)
        layout.addWidget(criar_divisor("#dde1df"))
        self._montar_log(layout)
        self._montar_rodape_cartao(layout)
        return card

    def _montar_seletor_modo(self, layout):
        bar = QHBoxLayout()
        bar.setContentsMargins(28, 16, 28, 0)
        bar.setSpacing(8)
        self.mode_buttons: list[QPushButton] = []
        for mode, text in (
            (MODE_REABRIR, "Reabrir pedidos"),
            (MODE_CANCELAR, "Cancelar pedidos"),
            (MODE_ENCERRAR, "Encerrar pedidos"),
        ):
            btn = QPushButton(text)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, m=mode: self.definir_modo(m))
            bar.addWidget(btn)
            self.mode_buttons.append(btn)
        bar.addStretch()
        layout.addLayout(bar)

    def _montar_titulo_cartao(self, layout):
        top = QHBoxLayout()
        top.setContentsMargins(28, 14, 28, 14)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.card_title = criar_rotulo("", 13, BG, QFont.DemiBold)
        self.card_subtitle = criar_rotulo("", 10, "#7a838a")
        titles.addWidget(self.card_title)
        titles.addWidget(self.card_subtitle)
        top.addLayout(titles)
        top.addStretch()
        self.count_badge = criar_rotulo("0 de 2", 9, "#68747d", QFont.Bold)
        self.count_badge.setStyleSheet(
            "color:#68747d; background:transparent; border:1px solid #d9dddc; border-radius:12px; padding:6px 12px;"
        )
        top.addWidget(self.count_badge)
        layout.addLayout(top)

    def _montar_paginas(self, layout):
        self.spreadsheet_row = SelectionRow(
            "01", "Planilha de pedidos",
            "Selecione o arquivo .xlsx com os números dos pedidos na coluna 'Nº Pedido'.",
            "Selecionar planilha", "file",
            self._escolher_planilha,
        )
        self.credentials_row = CredentialsRow()
        self.credentials_row.changed.connect(self._atualizar_estado)

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        pl.addWidget(self.spreadsheet_row)
        pl.addWidget(criar_divisor("#e3e5e2"))
        pl.addWidget(self.credentials_row)
        pl.addStretch()
        layout.addWidget(page)

    def _montar_log(self, layout):
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(16, 12, 16, 8)
        wl.setSpacing(0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("O andamento do processamento aparecerá aqui.")
        self.log.setFixedHeight(130)
        self.log.setStyleSheet(
            "QPlainTextEdit {background:#ffffff; color:#344a5b; border:1px solid #e3e5e2;"
            " border-radius:9px; padding:8px; font:10px 'Segoe UI';}"
        )
        wl.addWidget(self.log)
        layout.addWidget(wrapper)

    def _montar_rodape_cartao(self, layout):
        footer = QFrame()
        footer.setStyleSheet(
            "background: #f1f1ed; border-bottom-left-radius: 18px; border-bottom-right-radius:18px;"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(28, 18, 28, 18)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.ready_title = criar_rotulo("Aguardando configurações", 10, "#344a5b", QFont.DemiBold)
        self.ready_hint = criar_rotulo("Preencha as etapas acima para continuar.", 9, "#838c91", wrap=True)
        texts.addWidget(self.ready_title)
        texts.addWidget(self.ready_hint)
        self.headless_check = QCheckBox("Ocultar janela Chrome")
        self.headless_check.setStyleSheet(
            "QCheckBox { color:#344a5b; font:10px 'Segoe UI'; background:transparent; }"
            "QCheckBox::indicator { width:16px; height:16px; border:1px solid #c5cac8;"
            " border-radius:4px; background:#fff; }"
            "QCheckBox::indicator:checked { background:#317458; border-color:#317458; }"
        )
        texts.addSpacing(6)
        texts.addWidget(self.headless_check)
        fl.addLayout(texts, 1)
        self.stop_button = QPushButton("Parar após o pedido atual")
        self.stop_button.setFixedHeight(46)
        self.stop_button.setMinimumWidth(160)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setStyleSheet(ESTILO_PARAR)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._solicitar_parada)
        fl.addWidget(self.stop_button)
        self.start_button = QPushButton()
        self.start_button.setFixedHeight(46)
        self.start_button.setMinimumWidth(170)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self._iniciar)
        fl.addWidget(self.start_button)
        layout.addWidget(footer)

    def _montar_rodape(self, root):
        root.addSpacing(18)
        root.addWidget(criar_divisor(COR_DIVISOR_ESCURO))
        root.addSpacing(14)
        bottom = QHBoxLayout()
        bottom.addWidget(criar_rotulo(APP_NAME, 9, "#83919c"))
        bottom.addStretch()
        bottom.addWidget(criar_rotulo("Processamento local · dados seguros", 9, "#83919c"))
        root.addLayout(bottom)

    # --- Lógica ------------------------------------------------------------------

    def definir_modo(self, mode: int):
        self.mode = mode
        texts = MODE_TEXTS[mode]
        self.eyebrow.setText(texts["eyebrow"])
        self.intro.setText(texts["intro"])
        self.card_title.setText(texts["title"])
        self.card_subtitle.setText(texts["subtitle"])
        self.start_button.setText(texts["start"])
        for i, btn in enumerate(self.mode_buttons):
            active = i == mode
            btn.setStyleSheet(
                f"QPushButton {{background:{BG if active else 'transparent'};"
                f" color:{TEXT if active else '#344a5b'};"
                f" border:1px solid {BG if active else '#d9dddc'};"
                " border-radius:8px; font:600 11px 'Segoe UI'; padding:0 14px;}}"
            )
        self._atualizar_estado()

    def _escolher_planilha(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha de pedidos", "", "Planilhas Excel (*.xlsx *.xls)"
        )
        if path:
            self.spreadsheet = path
            self.spreadsheet_row.definir_valor(Path(path).name)
            self._atualizar_estado()

    def _atualizar_estado(self, *_):
        count = sum([bool(self.spreadsheet), bool(self.credentials_row.username and self.credentials_row.password)])
        ready = count == 2
        texts = MODE_TEXTS[self.mode]
        self.count_badge.setText(f"{count} de 2")

        for btn in self.mode_buttons:
            btn.setEnabled(not self.started)
        self.spreadsheet_row.set_enabled(not self.started)
        self.credentials_row.set_enabled(not self.started)

        if self.started:
            self.ready_title.setText(texts["running"])
            self.ready_hint.setText(texts["running_hint"])
        else:
            self.ready_title.setText("Tudo pronto para começar" if ready else "Aguardando configurações")
            self.ready_hint.setText(
                "Revise as etapas e clique em iniciar." if ready else "Preencha as etapas acima para continuar."
            )

        can_start = ready and not self.started
        self.start_button.setEnabled(can_start)
        self.start_button.setStyleSheet(ESTILO_INICIAR_ATIVO if can_start else ESTILO_INICIAR_INATIVO)

    def _iniciar(self):
        if not self.spreadsheet or not self.credentials_row.username or not self.credentials_row.password:
            return
        self.started = True
        self.cancel_event = Event()
        self.log.clear()
        self.stop_button.setEnabled(True)
        self.start_button.setText("◌  Processando...")
        self._atualizar_estado()

        self.worker = ProcessingWorker(
            self.spreadsheet,
            self.mode,
            self.credentials_row.username,
            self.credentials_row.password,
            self.cancel_event,
            headless=self.headless_check.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.succeeded.connect(self.sinal_tarefa_concluida)
        self.worker.failed.connect(self.sinal_tarefa_falhou)
        self.worker.finished.connect(self._ao_finalizar_worker)
        self.worker.start()

    def _on_progress(self, msg: str):
        self.log.appendPlainText(msg)
        self.log.ensureCursorVisible()

    def _solicitar_parada(self):
        self.cancel_event.set()
        self.stop_button.setEnabled(False)
        self.log.appendPlainText("Parada solicitada — o pedido atual será concluído antes de parar.")

    def _ao_finalizar_worker(self):
        self.started = False
        self.worker = None
        self.stop_button.setEnabled(False)
        self.start_button.setText(MODE_TEXTS[self.mode]["start"])
        self._atualizar_estado()

    def _ao_concluir(self, result: ProcessingSummary):
        estado = "interrompido" if result.cancelled else "concluído"
        self.log.appendPlainText(
            f"\n✓ Processamento {estado}: {result.completed}/{result.total} pedido(s) · {len(result.failed)} falha(s)."
        )
        if result.output_file:
            self.log.appendPlainText(f"Planilha: {result.output_file}")

    def _ao_falhar(self, message: str):
        self.log.appendPlainText(f"\n✗ Erro: {message}")
        QMessageBox.critical(self, "Não foi possível processar", message)

    def closeEvent(self, event):
        if self.started:
            QMessageBox.information(
                self, "Processamento em andamento",
                "Solicite a parada e aguarde o pedido atual terminar antes de fechar.",
            )
            event.ignore()
            return
        event.accept()

    # --- Atualização automática --------------------------------------------------

    def _iniciar_update(self):
        self._update_worker = UpdateWorker()
        self._update_worker.status_color.connect(self.sinal_update_status)
        self._update_worker.done.connect(self.sinal_update_reiniciar)
        self._update_worker.start()

    def _on_update_status(self, color: str, text: str):
        self.update_dot.setStyleSheet(f"color:{color}; background:transparent; font-size:14px;")
        self.update_text.setText(text)

    def _ao_reiniciar_update(self):
        if not self.started:
            QApplication.quit()


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def abrir_janela() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    if not _garantir_instancia_unica():
        QMessageBox.information(None, APP_NAME, "O programa já está aberto.")
        return 0
    icon = caminho_recurso(ICON_FILENAME)
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = App()
    window.show()
    return app.exec()
