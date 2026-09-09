from __future__ import annotations

import queue
import threading
import time

import serial
from PySide6.QtCore import QObject, Signal

from meshcore.protocol import UsbFrameParser, encode_usb_frame


class SerialWorker(QObject):
    frame_received = Signal(bytes)
    connected = Signal(str)
    disconnected = Signal()
    error = Signal(str)
    log = Signal(str)

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self._running = threading.Event()
        self._outgoing: queue.Queue[bytes] = queue.Queue()
        self._serial: serial.Serial | None = None

    def enqueue(self, payload: bytes) -> None:
        """Thread-safe: called by the GUI thread, consumed by the serial worker."""
        self._outgoing.put(payload)

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        parser = UsbFrameParser()
        self._running.set()

        try:
            with serial.Serial(
                self.port,
                self.baudrate,
                timeout=0.08,
                write_timeout=1.0,
            ) as ser:
                self._serial = ser
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass

                self.connected.emit(self.port)

                while self._running.is_set():
                    while True:
                        try:
                            payload = self._outgoing.get_nowait()
                        except queue.Empty:
                            break
                        packet = encode_usb_frame(payload)
                        ser.write(packet)
                        ser.flush()
                        self.log.emit(f"TX {payload.hex(' ')}")

                    waiting = ser.in_waiting
                    data = ser.read(waiting if waiting else 1)
                    if data:
                        for frame in parser.feed(data):
                            self.log.emit(f"RX {frame.hex(' ')}")
                            self.frame_received.emit(frame)

                    time.sleep(0.005)

        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._serial = None
            self._running.clear()
            self.disconnected.emit()
