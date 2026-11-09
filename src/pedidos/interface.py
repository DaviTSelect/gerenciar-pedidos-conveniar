"""Painel PySide6 para selecionar planilha e processar pedidos."""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .automacao import ProcessingSummary, processar_pedidos
from .auto_update import verificar_e_instalar
from .config import CONVENIAR_PASSWORD, CONVENIAR_USERNAME, FINAL_ACTIONS
from .version import APP_NAME, VERSION

BG = "#203447"
TEXT = "#efede5"
ACTION = "#e94c1f"


class ProcessingWorker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        spreadsheet: str,
        action_index: int,
        username: str,
        password: str,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.spreadsheet = spreadsheet
        self.action_index = action_index
        self.username = username
        self.password = password
        self.cancel_event = cancel_event

    def run(self) -> None:
        try:
            result = processar_pedidos(
                self.spreadsheet,
                self.action_index,
                self.username,
                self.password,
                self.progress.emit,
                self.cancel_event,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.password = ""


class UpdateWorker(QThread):
    status = Signal(str)

    def run(self) -> None:
        self.status.emit(verificar_e_instalar(VERSION))


class App(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(820, 700)
        self.setMinimumSize(720, 600)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};")
        self.spreadsheet = ""
        self.worker: ProcessingWorker | None = None
        self.cancel_event = Event()
        self._build_ui()
        self._update_start_state()
        self._iniciar_verificacao_update()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(18)

        title = QLabel("Processamento de pedidos")
        title.setStyleSheet('font: 600 22px "Segoe UI"; color: #efede5;')
        root.addWidget(title)
        subtitle = QLabel(
            "Selecione a planilha, escolha uma ação e processe os pedidos em sequência."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet('font: 11px "Segoe UI"; color: #a5afb6;')
        root.addWidget(subtitle)

        self.file_button = QPushButton("Selecionar planilha")
        self.file_button.clicked.connect(self._select_spreadsheet)
        self.file_button.setMinimumHeight(42)
        root.addWidget(self.file_button)
        self.file_label = QLabel("Nenhuma planilha selecionada")
        self.file_label.setStyleSheet("color: #a5afb6;")
        root.addWidget(self.file_label)

        root.addWidget(self._section_label("Ação final"))
        self.actions = QListWidget()
        self.actions.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.actions.setMaximumHeight(125)
        self.actions.setStyleSheet(
            "QListWidget { background:#fff; color:#344a5b; border:0; border-radius:8px; padding:5px; }"
            "QListWidget::item { padding:9px; }"
            "QListWidget::item:selected { background:#e5f4ed; color:#203447; }"
        )
        for action in FINAL_ACTIONS:
            self.actions.addItem(QListWidgetItem(action.label))
        self.actions.currentRowChanged.connect(self._update_start_state)
        root.addWidget(self.actions)

        credentials = QHBoxLayout()
        credentials.setSpacing(12)
        username_column = QVBoxLayout()
        username_column.addWidget(self._section_label("Usuário"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuário do Conveniar")
        if CONVENIAR_USERNAME:
            self.username_input.setText(CONVENIAR_USERNAME)
        username_column.addWidget(self.username_input)
        password_column = QVBoxLayout()
        password_column.addWidget(self._section_label("Senha"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Senha (ou preencha no .env)")
        if CONVENIAR_PASSWORD:
            self.password_input.setText(CONVENIAR_PASSWORD)
        password_column.addWidget(self.password_input)
        credentials.addLayout(username_column)
        credentials.addLayout(password_column)
        root.addLayout(credentials)
        self.username_input.textChanged.connect(self._update_start_state)
        self.password_input.textChanged.connect(self._update_start_state)
        credentials_hint = QLabel(
            "A senha não é salva. As ações são executadas automaticamente após iniciar."
        )
        credentials_hint.setStyleSheet("color: #a5afb6; font-size: 10px;")
        root.addWidget(credentials_hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        root.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("O andamento do processamento aparecerá aqui.")
        self.log.setStyleSheet(
            "QPlainTextEdit { background:#fff; color:#344a5b; border:0; border-radius:8px; padding:8px; }"
        )
        root.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.stop_button = QPushButton("Parar após o pedido atual")
        self.stop_button.clicked.connect(self._request_stop)
        self.stop_button.setEnabled(False)
        buttons.addWidget(self.stop_button)
        self.start_button = QPushButton("Iniciar processamento")
        self.start_button.clicked.connect(self._start)
        self.start_button.setMinimumHeight(42)
        self.start_button.setStyleSheet(
            f"QPushButton {{ background:{ACTION}; color:white; border:0; "
            "border-radius:8px; padding:0 18px; font-weight:600; }"
            "QPushButton:disabled { background:#697780; color:#c6cbd0; }"
        )
        buttons.addWidget(self.start_button)
        root.addLayout(buttons)

        self.version_label = QLabel(f"v{VERSION}  ·  ⟳ Verificando atualizações...")
        self.version_label.setStyleSheet("color: #a5afb6; font-size: 10px;")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.version_label)

    def _iniciar_verificacao_update(self) -> None:
        self._update_worker = UpdateWorker()
        self._update_worker.status.connect(self._on_update_status)
        self._update_worker.start()

    def _on_update_status(self, status: str) -> None:
        if status == "atualizado":
            self.version_label.setText(f"v{VERSION}  ·  ● Atualizado")
        elif status == "atualizando":
            self.version_label.setText(f"v{VERSION}  ·  ▲ Atualizando... o app será reiniciado")
        elif status.startswith("nova_versao:"):
            tag = status.split(":", 1)[1]
            self.version_label.setText(f"v{VERSION}  ·  ▲ Nova versão disponível: {tag}")
        elif status == "sem_conexao":
            self.version_label.setText(f"v{VERSION}  ·  ⚠ Sem conexão — verificação offline")
        else:
            self.version_label.setText(f"v{VERSION}")

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet('font: 600 11px "Segoe UI"; color: #efede5;')
        return label

    def _select_spreadsheet(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar planilha de pedidos",
            "",
            "Planilhas Excel (*.xlsx *.xls)",
        )
        if file_path:
            self.spreadsheet = file_path
            self.file_label.setText(Path(file_path).name)
            self.file_label.setToolTip(file_path)
            self._update_start_state()

    def _update_start_state(self, *_args) -> None:
        ready = bool(
            self.spreadsheet
            and self.actions.currentRow() >= 0
            and self.username_input.text().strip()
            and self.password_input.text()
        )
        running = self.worker is not None and self.worker.isRunning()
        self.start_button.setEnabled(ready and not running)
        self.file_button.setEnabled(not running)
        self.actions.setEnabled(not running)
        self.username_input.setEnabled(not running)
        self.password_input.setEnabled(not running)

    def _start(self) -> None:
        action_index = self.actions.currentRow()
        if not self.spreadsheet or action_index < 0:
            return

        self.cancel_event = Event()
        self.worker = ProcessingWorker(
            self.spreadsheet,
            action_index,
            self.username_input.text().strip(),
            self.password_input.text(),
            self.cancel_event,
        )
        self.password_input.clear()
        self.log.clear()
        self.progress.show()
        self.stop_button.setEnabled(True)
        self.worker.progress.connect(self.log.appendPlainText)
        self.worker.succeeded.connect(self._on_succeeded)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        self._update_start_state()

    def _request_stop(self) -> None:
        self.cancel_event.set()
        self.stop_button.setEnabled(False)
        self.log.appendPlainText("Parada solicitada; o pedido atual será concluído.")

    def _on_succeeded(self, result: ProcessingSummary) -> None:
        state = "interrompido" if result.cancelled else "concluído"
        self.log.appendPlainText(
            f"Processamento {state}: {result.completed}/{result.total} pedido(s) concluído(s); "
            f"{len(result.failed)} falha(s)."
        )
        if result.output_file:
            self.log.appendPlainText(f"Resultados (Item PT + Status) salvos em: {result.output_file}")
        if result.failed:
            self.log.appendPlainText("\n".join(result.failed))

    def _on_failed(self, message: str) -> None:
        self.log.appendPlainText(f"Erro: {message}")
        QMessageBox.critical(self, "Não foi possível processar", message)

    def _on_finished(self) -> None:
        self.progress.hide()
        self.stop_button.setEnabled(False)
        self.worker = None
        self._update_start_state()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Processamento em andamento",
                "Solicite a parada e aguarde o pedido atual terminar antes de fechar.",
            )
            event.ignore()
            return
        event.accept()


def abrir_janela() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    return app.exec()
