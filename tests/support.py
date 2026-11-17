"""Test doubles for the app loop."""

from __future__ import annotations

from dataclasses import dataclass, field


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


class FakeTransport:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.fail_start = ""
        self._connected = False
        self.reports: list[tuple[int, int]] = []
        self.pairing_calls: list[str] = []
        self.unpaired = 0
        self.renamed: list[str] = []
        self.host_name = "DESKTOP-7K2"
        self.host_address = "AA:BB:CC:DD:EE:FF"

    def start(self) -> None:
        if self.fail_start:
            raise RuntimeError(self.fail_start)
        self.started = True

    def close(self) -> None:
        self.closed = True

    def poll(self, timeout: float = 0.0) -> None:
        pass

    def send_mouse(self, dx: int = 0, dy: int = 0, buttons: int = 0, wheel: int = 0) -> int:
        self.reports.append((dx, dy))
        return 1 if self._connected else 0

    def start_pairing(self, seconds: int = 180) -> None:
        self.pairing_calls.append(f"start:{seconds}")

    def stop_pairing(self) -> None:
        self.pairing_calls.append("stop")

    def unpair(self) -> None:
        self.unpaired += 1

    def drop_host(self) -> None:
        self._connected = False

    def rename(self, name: str) -> None:
        self.renamed.append(name)

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected


@dataclass
class FakeDisplay:
    images: list = field(default_factory=list)

    def show(self, image) -> None:
        self.images.append(image)


class ScriptedKeypad:
    def __init__(self) -> None:
        self.events = []

    def queue(self, *events) -> None:
        self.events.extend(events)

    def poll(self):
        events, self.events = self.events, []
        return events
