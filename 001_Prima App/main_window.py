from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from maps.geotiff_map import GeoTiffMapWidget
from maps.online_map import OnlineMapWidget
from meshcore.protocol import (
    PUSH_CODE_TELEMETRY_RESPONSE,
    RESP_CODE_CONTACT,
    RESP_CODE_CONTACTS_START,
    RESP_CODE_END_OF_CONTACTS,
    RESP_CODE_ERR,
    RESP_CODE_SELF_INFO,
    build_app_start,
    build_device_query,
    build_get_contacts,
    build_set_device_time,
    build_telemetry_request,
    decode_contact,
    decode_telemetry_response,
)
from meshcore.serial_transport import SerialWorker
from models import Contact, TelemetryPoint
from tracking.csv_logger import CsvSessionLogger


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MeshCore Tracker")

        self.serial_thread: QThread | None = None
        self.serial_worker: SerialWorker | None = None
        self.contacts: dict[str, Contact] = {}
        self.tracks: dict[str, list[dict]] = {}
        self.csv_logger = CsvSessionLogger()
        self._polling = False

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_cycle)

        self._build_ui()
        self.refresh_ports()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

        # Sidebar
        sidebar = QWidget()
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(390)
        side = QVBoxLayout(sidebar)

        usb_group = QGroupBox("Connessione MeshCore USB")
        usb_layout = QVBoxLayout(usb_group)
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Aggiorna")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_button)
        usb_layout.addLayout(port_row)

        connect_row = QHBoxLayout()
        self.connect_button = QPushButton("Connetti")
        self.disconnect_button = QPushButton("Disconnetti")
        self.disconnect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_serial)
        self.disconnect_button.clicked.connect(self.disconnect_serial)
        connect_row.addWidget(self.connect_button)
        connect_row.addWidget(self.disconnect_button)
        usb_layout.addLayout(connect_row)

        self.usb_status = QLabel("Non connesso")
        usb_layout.addWidget(self.usb_status)
        side.addWidget(usb_group)

        contacts_group = QGroupBox("Contatti")
        contacts_layout = QVBoxLayout(contacts_group)
        self.contacts_list = QListWidget()
        self.contacts_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        contacts_layout.addWidget(self.contacts_list)

        select_row = QHBoxLayout()
        select_all = QPushButton("Tutti")
        select_none = QPushButton("Nessuno")
        select_all.clicked.connect(lambda: self.set_all_contacts_checked(True))
        select_none.clicked.connect(lambda: self.set_all_contacts_checked(False))
        select_row.addWidget(select_all)
        select_row.addWidget(select_none)
        contacts_layout.addLayout(select_row)
        side.addWidget(contacts_group, 1)

        poll_group = QGroupBox("Polling posizione")
        poll_form = QFormLayout(poll_group)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setValue(15)
        self.interval_spin.setSuffix(" s")
        poll_form.addRow("IntPing:", self.interval_spin)

        self.start_button = QPushButton("Avvia")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_polling)
        self.stop_button.clicked.connect(self.stop_polling)
        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        poll_form.addRow(buttons)
        side.addWidget(poll_group)

        map_group = QGroupBox("Cartografia")
        map_layout = QVBoxLayout(map_group)
        self.map_mode = QComboBox()
        self.map_mode.addItems(["Online — OpenStreetMap", "Offline — GeoTIFF"])
        self.map_mode.currentIndexChanged.connect(self._map_mode_changed)
        map_layout.addWidget(self.map_mode)
        self.load_geotiff_button = QPushButton("Carica GeoTIFF…")
        self.load_geotiff_button.clicked.connect(self.load_geotiff)
        self.load_geotiff_button.setEnabled(False)
        map_layout.addWidget(self.load_geotiff_button)
        side.addWidget(map_group)

        # Map area
        map_container = QWidget()
        map_box = QVBoxLayout(map_container)
        map_box.setContentsMargins(0, 0, 0, 0)

        self.map_stack = QStackedWidget()
        self.online_map = OnlineMapWidget()
        self.offline_map = GeoTiffMapWidget()
        self.map_stack.addWidget(self.online_map)
        self.map_stack.addWidget(self.offline_map)
        map_box.addWidget(self.map_stack, 1)

        self.last_position = QLabel("Nessuna posizione ricevuta.")
        self.last_position.setMinimumHeight(30)
        map_box.addWidget(self.last_position)

        splitter.addWidget(sidebar)
        splitter.addWidget(map_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([330, 1070])

        status = QStatusBar()
        self.setStatusBar(status)
        self.statusBar().showMessage("Pronto.")

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData()
        self.port_combo.clear()
        ports = list(list_ports.comports())
        for p in ports:
            label = f"{p.device} — {p.description}"
            self.port_combo.addItem(label, p.device)
        if current:
            idx = self.port_combo.findData(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        if not ports:
            self.port_combo.addItem("Nessuna porta seriale trovata", None)

    def connect_serial(self) -> None:
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "MeshCore", "Selezionare una porta seriale valida.")
            return

        self.disconnect_serial()

        self.serial_thread = QThread(self)
        self.serial_worker = SerialWorker(port, 115200)
        self.serial_worker.moveToThread(self.serial_thread)
        self.serial_thread.started.connect(self.serial_worker.run)
        self.serial_worker.connected.connect(self._serial_connected)
        self.serial_worker.disconnected.connect(self._serial_disconnected)
        self.serial_worker.error.connect(self._serial_error)
        self.serial_worker.frame_received.connect(self._handle_frame)
        self.serial_thread.start()

        self.usb_status.setText(f"Connessione a {port}…")
        self.connect_button.setEnabled(False)

    def _serial_connected(self, port: str) -> None:
        self.usb_status.setText(f"Connesso: {port}")
        self.disconnect_button.setEnabled(True)
        self.statusBar().showMessage("USB connessa. Inizializzazione MeshCore…")

        self.send(build_app_start("MeshCoreTracker", 3))

    def _serial_disconnected(self) -> None:
        self.stop_polling()
        self.usb_status.setText("Non connesso")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.statusBar().showMessage("USB disconnessa.")

        if self.serial_thread is not None:
            self.serial_thread.quit()
            self.serial_thread.wait(1000)
            self.serial_thread.deleteLater()
        self.serial_thread = None
        self.serial_worker = None

    def _serial_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Errore seriale: {message}")
        QMessageBox.critical(self, "Errore seriale", message)

    def disconnect_serial(self) -> None:
        self.stop_polling()
        if self.serial_worker is not None:
            self.serial_worker.stop()
        if self.serial_thread is not None:
            self.serial_thread.quit()
            self.serial_thread.wait(1500)

    def send(self, payload: bytes) -> None:
        if self.serial_worker is not None:
            self.serial_worker.enqueue(payload)

    def _handle_frame(self, frame: bytes) -> None:
        if not frame:
            return

        code = frame[0]

        if code == RESP_CODE_SELF_INFO:
            # Once APP_START is accepted, negotiate protocol, sync time, fetch contacts.
            self.send(build_device_query(3))
            self.send(build_set_device_time(int(time.time())))
            self.send(build_get_contacts())
            self.statusBar().showMessage("MeshCore inizializzato. Lettura contatti…")

        elif code == RESP_CODE_CONTACTS_START:
            self.contacts.clear()
            self.contacts_list.clear()

        elif code == RESP_CODE_CONTACT:
            try:
                contact = decode_contact(frame)
            except Exception as exc:
                self.statusBar().showMessage(f"Errore decodifica contatto: {exc}")
                return
            self.contacts[contact.key_hex] = contact
            self._add_contact_item(contact)

        elif code == RESP_CODE_END_OF_CONTACTS:
            self.statusBar().showMessage(f"Contatti caricati: {len(self.contacts)}")

        elif code == PUSH_CODE_TELEMETRY_RESPONSE:
            self._handle_telemetry(frame)

        elif code == RESP_CODE_ERR:
            err = frame[1] if len(frame) > 1 else -1
            self.statusBar().showMessage(f"MeshCore RESP_CODE_ERR: {err}")

    def _add_contact_item(self, contact: Contact) -> None:
        item = QListWidgetItem(contact.name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, contact.key_hex)
        if contact.adv_lat is not None and contact.adv_lon is not None:
            item.setToolTip(f"Advert: {contact.adv_lat:.6f}, {contact.adv_lon:.6f}")
        self.contacts_list.addItem(item)

    def set_all_contacts_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.contacts_list.count()):
            self.contacts_list.item(i).setCheckState(state)

    def selected_contacts(self) -> list[Contact]:
        selected: list[Contact] = []
        for i in range(self.contacts_list.count()):
            item = self.contacts_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                key_hex = item.data(Qt.ItemDataRole.UserRole)
                contact = self.contacts.get(key_hex)
                if contact:
                    selected.append(contact)
        return selected

    def start_polling(self) -> None:
        if self.serial_worker is None:
            QMessageBox.warning(self, "Polling", "Connettere prima il dispositivo MeshCore USB.")
            return
        selected = self.selected_contacts()
        if not selected:
            QMessageBox.warning(self, "Polling", "Selezionare almeno un contatto.")
            return

        self.csv_logger.new_session()
        self._polling = True
        self.interval_spin.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.poll_timer.start(self.interval_spin.value() * 1000)
        self.poll_cycle()

    def stop_polling(self) -> None:
        self._polling = False
        self.poll_timer.stop()
        self.interval_spin.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def poll_cycle(self) -> None:
        if not self._polling:
            return

        selected = self.selected_contacts()
        if not selected:
            self.stop_polling()
            return

        interval_ms = self.interval_spin.value() * 1000
        # Sequential requests reduce bursts on the mesh. Keep the whole batch inside IntPing.
        spacing = min(1000, max(250, interval_ms // max(len(selected) + 1, 1)))

        for idx, contact in enumerate(selected):
            QTimer.singleShot(
                idx * spacing,
                lambda c=contact: self._request_telemetry(c)
            )

        self.statusBar().showMessage(
            f"Polling: {len(selected)} contatti ogni {self.interval_spin.value()} s"
        )

    def _request_telemetry(self, contact: Contact) -> None:
        if self._polling and self.serial_worker is not None:
            self.send(build_telemetry_request(contact.public_key))

    def _find_contact_by_prefix(self, prefix: bytes) -> Contact | None:
        for contact in self.contacts.values():
            if contact.prefix == prefix:
                return contact
        return None

    def _handle_telemetry(self, frame: bytes) -> None:
        try:
            response = decode_telemetry_response(frame)
        except Exception as exc:
            self.statusBar().showMessage(f"Errore telemetria: {exc}")
            return

        contact = self._find_contact_by_prefix(response.public_key_prefix)
        if contact is None:
            self.statusBar().showMessage(
                f"0x8B da contatto sconosciuto: {response.public_key_prefix.hex()}"
            )
            return

        gps = response.decoded.get("gps")
        if not gps:
            self.statusBar().showMessage(f"{contact.name}: telemetria ricevuta senza GPS.")
            return

        now = datetime.now().astimezone()
        point = TelemetryPoint(
            timestamp=now,
            contact_name=contact.name,
            latitude=gps["latitude"],
            longitude=gps["longitude"],
            altitude_m=gps.get("altitude_m"),
            telemetry=response.decoded,
        )

        map_point = {
            "lat": point.latitude,
            "lon": point.longitude,
            "alt": point.altitude_m,
            "time": now.strftime("%H:%M:%S"),
        }
        self.tracks.setdefault(contact.name, []).append(map_point)

        self.online_map.set_track(contact.name, self.tracks[contact.name])
        self.offline_map.set_track(contact.name, self.tracks[contact.name])

        path = self.csv_logger.append(point, response.lpp_payload.hex())

        self.last_position.setText(
            f"{contact.name}  |  "
            f"{point.latitude:.6f}, {point.longitude:.6f}  |  "
            f"Alt {point.altitude_m:.1f} m  |  "
            f"{now.strftime('%H:%M:%S')}"
        )
        self.statusBar().showMessage(f"Posizione salvata: {path}")

    def _map_mode_changed(self, index: int) -> None:
        self.map_stack.setCurrentIndex(index)
        self.load_geotiff_button.setEnabled(index == 1)
        if index == 0:
            self.online_map.fit_all()

    def load_geotiff(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Carica GeoTIFF",
            str(Path.home()),
            "GeoTIFF (*.tif *.tiff);;Tutti i file (*)",
        )
        if not path:
            return

        ok, message = self.offline_map.load_geotiff(path)
        if not ok:
            QMessageBox.warning(self, "GeoTIFF", message)
        else:
            self.statusBar().showMessage(message)

    def closeEvent(self, event) -> None:
        self.disconnect_serial()
        event.accept()
