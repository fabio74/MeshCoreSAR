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
    RESP_CODE_SENT,
    build_app_start,
    build_device_query,
    build_get_contacts,
    build_set_device_time,
    build_telemetry_request,
    decode_contact,
    decode_sent_response,
    decode_telemetry_response,
)
from meshcore.serial_transport import SerialWorker
from models import Contact, TelemetryPoint
from tracking.csv_logger import CsvSessionLogger
from tracking.gpx_exporter import export_tracks_gpx


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MeshCore Tracker")

        self.serial_thread: QThread | None = None
        self.serial_worker: SerialWorker | None = None
        self.contacts: dict[str, Contact] = {}
        self.tracks: dict[str, list[dict]] = {}
        self.latest_positions: dict[str, TelemetryPoint] = {}
        self.csv_logger = CsvSessionLogger()
        self._polling = False
        self._poll_queue: list[Contact] = []
        self._current_poll_contact: Contact | None = None
        self._current_poll_retry = 0
        self._cycle_started_monotonic = 0.0

        # A new cycle starts only after the previous one has completed.
        # This prevents overlapping telemetry requests on the MeshCore radio.
        self.poll_timer = QTimer(self)
        self.poll_timer.setSingleShot(True)
        self.poll_timer.timeout.connect(self.poll_cycle)

        # While a contact is being queried, this timer waits first for
        # RESP_CODE_SENT and then for the 0x8B telemetry response.
        self.response_timer = QTimer(self)
        self.response_timer.setSingleShot(True)
        self.response_timer.timeout.connect(self._poll_request_timeout)

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
        sidebar.setMinimumWidth(320)
        sidebar.setMaximumWidth(430)
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

        contacts_group = QGroupBox("Contatti da interrogare")
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
        side.addWidget(contacts_group, 2)

        visibility_group = QGroupBox("Tracce visibili sulla mappa")
        visibility_layout = QVBoxLayout(visibility_group)
        self.track_visibility_list = QListWidget()
        self.track_visibility_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.track_visibility_list.itemChanged.connect(self._track_visibility_changed)
        visibility_layout.addWidget(self.track_visibility_list)

        vis_buttons = QHBoxLayout()
        vis_all = QPushButton("Tutte")
        vis_none = QPushButton("Nessuna")
        vis_all.clicked.connect(lambda: self.set_all_tracks_visible(True))
        vis_none.clicked.connect(lambda: self.set_all_tracks_visible(False))
        vis_buttons.addWidget(vis_all)
        vis_buttons.addWidget(vis_none)
        visibility_layout.addLayout(vis_buttons)
        side.addWidget(visibility_group, 1)

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

        self.export_gpx_button = QPushButton("Esporta tracce GPX…")
        self.export_gpx_button.clicked.connect(self.export_gpx)
        poll_form.addRow(self.export_gpx_button)
        side.addWidget(poll_group)

        map_group = QGroupBox("Cartografia")
        map_layout = QFormLayout(map_group)
        self.map_mode = QComboBox()
        self.map_mode.addItems(["Online", "Offline — GeoTIFF"])
        self.map_mode.currentIndexChanged.connect(self._map_mode_changed)
        map_layout.addRow("Modalità:", self.map_mode)

        self.online_layer_combo = QComboBox()
        self.online_layer_combo.addItem("OpenStreetMap", "osm")
        self.online_layer_combo.addItem("OpenTopoMap", "opentopo")
        self.online_layer_combo.addItem("Esri Satellite", "esri_satellite")
        self.online_layer_combo.currentIndexChanged.connect(self._online_layer_changed)
        map_layout.addRow("Mappa online:", self.online_layer_combo)

        self.load_geotiff_button = QPushButton("Carica GeoTIFF…")
        self.load_geotiff_button.clicked.connect(self.load_geotiff)
        self.load_geotiff_button.setEnabled(False)
        map_layout.addRow(self.load_geotiff_button)
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

        splitter.addWidget(sidebar)
        splitter.addWidget(map_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([370, 1030])

        status = QStatusBar()
        self.setStatusBar(status)
        self.coordinates_status = QLabel("Coordinate dispositivi: —")
        self.coordinates_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.coordinates_status.setMinimumWidth(560)
        status.addPermanentWidget(self.coordinates_status, 1)
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
            self.send(build_device_query(3))
            self.send(build_set_device_time(int(time.time())))
            self.send(build_get_contacts())
            self.statusBar().showMessage("MeshCore inizializzato. Lettura contatti…")

        elif code == RESP_CODE_CONTACTS_START:
            self.contacts.clear()
            self.contacts_list.clear()
            self.track_visibility_list.blockSignals(True)
            self.track_visibility_list.clear()
            self.track_visibility_list.blockSignals(False)

        elif code == RESP_CODE_CONTACT:
            try:
                contact = decode_contact(frame)
            except Exception as exc:
                self.statusBar().showMessage(f"Errore decodifica contatto: {exc}")
                return
            self.contacts[contact.key_hex] = contact
            self._add_contact_item(contact)
            self._add_track_visibility_item(contact.name)

        elif code == RESP_CODE_END_OF_CONTACTS:
            self.statusBar().showMessage(f"Contatti caricati: {len(self.contacts)}")

        elif code == RESP_CODE_SENT:
            self._handle_sent_response(frame)

        elif code == PUSH_CODE_TELEMETRY_RESPONSE:
            self._handle_telemetry(frame)

        elif code == RESP_CODE_ERR:
            err = frame[1] if len(frame) > 1 else -1
            if self._polling and self._current_poll_contact is not None:
                self._handle_poll_error(err)
            else:
                self.statusBar().showMessage(f"MeshCore RESP_CODE_ERR: {err}")

    def _add_contact_item(self, contact: Contact) -> None:
        item = QListWidgetItem(contact.name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, contact.key_hex)
        if contact.adv_lat is not None and contact.adv_lon is not None:
            item.setToolTip(f"Advert: {contact.adv_lat:.6f}, {contact.adv_lon:.6f}")
        self.contacts_list.addItem(item)

    def _add_track_visibility_item(self, contact_name: str) -> None:
        item = QListWidgetItem(contact_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, contact_name)
        self.track_visibility_list.addItem(item)
        self.online_map.set_track_visibility(contact_name, True)
        self.offline_map.set_track_visibility(contact_name, True)

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

    def set_all_tracks_visible(self, visible: bool) -> None:
        self.track_visibility_list.blockSignals(True)
        state = Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        for i in range(self.track_visibility_list.count()):
            item = self.track_visibility_list.item(i)
            item.setCheckState(state)
            name = item.data(Qt.ItemDataRole.UserRole)
            self.online_map.set_track_visibility(name, visible)
            self.offline_map.set_track_visibility(name, visible)
        self.track_visibility_list.blockSignals(False)
        if visible and self.map_mode.currentIndex() == 0:
            self.online_map.fit_all()

    def _track_visibility_changed(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        self.online_map.set_track_visibility(name, visible)
        self.offline_map.set_track_visibility(name, visible)

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
        self._poll_queue.clear()
        self._current_poll_contact = None
        self._current_poll_retry = 0
        self.poll_timer.stop()
        self.response_timer.stop()
        self.interval_spin.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.poll_cycle()

    def stop_polling(self) -> None:
        self._polling = False
        self.poll_timer.stop()
        self.response_timer.stop()
        self._poll_queue.clear()
        self._current_poll_contact = None
        self._current_poll_retry = 0
        self.interval_spin.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def poll_cycle(self) -> None:
        """Start one non-overlapping polling cycle.

        IntPing is the minimum interval between cycle starts. If radio round trips
        take longer than IntPing, the next cycle waits rather than overlapping.
        """
        if not self._polling:
            return
        if self._current_poll_contact is not None or self._poll_queue:
            return

        selected = self.selected_contacts()
        if not selected:
            self.stop_polling()
            return

        self._cycle_started_monotonic = time.monotonic()
        self._poll_queue = list(selected)
        self.statusBar().showMessage(
            f"Nuovo ciclo: {len(selected)} contatti — IntPing {self.interval_spin.value()} s"
        )
        self._poll_next_contact()

    def _poll_next_contact(self) -> None:
        if not self._polling:
            return

        self.response_timer.stop()
        self._current_poll_contact = None
        self._current_poll_retry = 0

        if not self._poll_queue:
            elapsed_ms = int((time.monotonic() - self._cycle_started_monotonic) * 1000)
            target_ms = self.interval_spin.value() * 1000
            delay_ms = max(250, target_ms - elapsed_ms)
            self.statusBar().showMessage(
                f"Ciclo completato. Prossimo ciclo tra {delay_ms / 1000:.1f} s"
            )
            self.poll_timer.start(delay_ms)
            return

        self._current_poll_contact = self._poll_queue.pop(0)
        self._send_current_poll_request()

    def _send_current_poll_request(self) -> None:
        contact = self._current_poll_contact
        if not self._polling or contact is None or self.serial_worker is None:
            return

        self.send(build_telemetry_request(contact.public_key))
        # Guard time while waiting for the immediate RESP_CODE_SENT/ERR.
        self.response_timer.start(2500)
        retry_text = "" if self._current_poll_retry == 0 else f" — retry {self._current_poll_retry}"
        self.statusBar().showMessage(f"Richiesta posizione → {contact.name}{retry_text}")

    def _handle_sent_response(self, frame: bytes) -> None:
        """Honor MeshCore's per-request suggested round-trip timeout."""
        if not self._polling or self._current_poll_contact is None:
            return
        try:
            sent = decode_sent_response(frame)
        except Exception as exc:
            self.statusBar().showMessage(f"RESP_CODE_SENT non valida: {exc}")
            return

        # Add a small margin for USB dispatch/UI scheduling. Keep an upper bound
        # so a non-responsive node cannot block the application indefinitely.
        wait_ms = max(2500, min(60000, sent.suggested_timeout_ms + 1500))
        self.response_timer.start(wait_ms)
        self.statusBar().showMessage(
            f"{self._current_poll_contact.name}: richiesta inviata, attesa max {wait_ms / 1000:.1f} s"
        )

    def _handle_poll_error(self, err: int) -> None:
        contact = self._current_poll_contact
        if contact is None:
            return
        self.response_timer.stop()

        if self._current_poll_retry < 1:
            self._current_poll_retry += 1
            self.statusBar().showMessage(
                f"{contact.name}: MeshCore ERR {err}; nuovo tentativo…"
            )
            expected_prefix = bytes(contact.prefix)
            QTimer.singleShot(1000, lambda p=expected_prefix: self._retry_current_poll(p))
            return

        self.statusBar().showMessage(
            f"{contact.name}: MeshCore ERR {err} dopo retry; passo al contatto successivo"
        )
        QTimer.singleShot(300, self._poll_next_contact)

    def _poll_request_timeout(self) -> None:
        contact = self._current_poll_contact
        if not self._polling or contact is None:
            return

        if self._current_poll_retry < 1:
            self._current_poll_retry += 1
            self.statusBar().showMessage(
                f"{contact.name}: timeout; nuovo tentativo…"
            )
            expected_prefix = bytes(contact.prefix)
            QTimer.singleShot(750, lambda p=expected_prefix: self._retry_current_poll(p))
            return

        self.statusBar().showMessage(
            f"{contact.name}: nessuna telemetria dopo 2 tentativi; passo al successivo"
        )
        QTimer.singleShot(300, self._poll_next_contact)

    def _retry_current_poll(self, expected_prefix: bytes) -> None:
        """Retry only if the same contact is still the active request."""
        contact = self._current_poll_contact
        if (
            not self._polling
            or contact is None
            or contact.prefix != expected_prefix
        ):
            return
        self._send_current_poll_request()

    def _complete_current_poll(self, contact: Contact, result: str) -> None:
        current = self._current_poll_contact
        if current is None or current.prefix != contact.prefix:
            return

        self.response_timer.stop()
        self._current_poll_contact = None
        self._current_poll_retry = 0
        self.statusBar().showMessage(f"{contact.name}: {result}")
        QTimer.singleShot(300, self._poll_next_contact)

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
            self._complete_current_poll(contact, "telemetria ricevuta senza GPS")
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
            "timestamp": now.isoformat(timespec="seconds"),
        }
        self.tracks.setdefault(contact.name, []).append(map_point)
        self.latest_positions[contact.name] = point

        self.online_map.set_track(contact.name, self.tracks[contact.name])
        self.offline_map.set_track(contact.name, self.tracks[contact.name])
        self._update_coordinate_status()

        path = self.csv_logger.append(point, response.lpp_payload.hex())
        self._complete_current_poll(
            contact,
            f"{point.latitude:.6f}, {point.longitude:.6f} — salvato in {path}",
        )

    def _update_coordinate_status(self) -> None:
        if not self.latest_positions:
            self.coordinates_status.setText("Coordinate dispositivi: —")
            self.coordinates_status.setToolTip("")
            return

        compact: list[str] = []
        detailed: list[str] = []
        for name in sorted(self.latest_positions, key=str.casefold):
            p = self.latest_positions[name]
            compact.append(f"{name}: {p.latitude:.6f}, {p.longitude:.6f}")
            alt = "—" if p.altitude_m is None else f"{p.altitude_m:.1f} m"
            detailed.append(
                f"{name}\nLat: {p.latitude:.6f}\nLon: {p.longitude:.6f}\n"
                f"Alt: {alt}\nOra: {p.timestamp.strftime('%H:%M:%S')}"
            )

        full = "  |  ".join(compact)
        self.coordinates_status.setText(full)
        self.coordinates_status.setToolTip("\n\n".join(detailed))

    def export_gpx(self) -> None:
        nonempty = {name: pts for name, pts in self.tracks.items() if pts}
        if not nonempty:
            QMessageBox.information(self, "GPX", "Non ci sono ancora tracce da esportare.")
            return

        default_name = "MeshCoreTracks_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".gpx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta tracce GPX",
            str(Path.home() / default_name),
            "GPX (*.gpx)",
        )
        if not path:
            return
        if not path.lower().endswith(".gpx"):
            path += ".gpx"

        try:
            exported = export_tracks_gpx(nonempty, path)
        except Exception as exc:
            QMessageBox.critical(self, "GPX", f"Errore esportazione GPX:\n{exc}")
            return

        self.statusBar().showMessage(f"GPX esportato: {exported}")

    def _map_mode_changed(self, index: int) -> None:
        self.map_stack.setCurrentIndex(index)
        offline = index == 1
        self.load_geotiff_button.setEnabled(offline)
        self.online_layer_combo.setEnabled(not offline)
        if not offline:
            self.online_map.fit_all()

    def _online_layer_changed(self, index: int) -> None:
        layer_key = self.online_layer_combo.itemData(index)
        if layer_key:
            self.online_map.set_base_layer(layer_key)

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
