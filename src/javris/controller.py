"""The single QML-facing object: state, telemetry properties and command entry.

QML reads from here and never mutates anything except through the explicit
``@Slot`` methods, keeping data flow one-directional (backend -> presentation).
All formatting for display lives here so QML stays free of business logic.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .commands.router import CommandRouter, Severity
from .state import AssistantState, InvalidTransitionError, can_transition
from .telemetry.models import TelemetrySnapshot
from .telemetry.service import MIN_INTERVAL_MS, TelemetrySampler

#: Duration of the boot sequence before the HUD settles into standby.
BOOT_DURATION_MS = 1800

#: Maximum console lines retained. Bounded so a long-running session cannot
#: grow the model without limit.
MAX_LOG_LINES = 200

_MODES = ("DIAGNOSTICS", "MONITOR")


def format_bytes(value: float | None) -> str:
    """Format a byte count with a binary unit suffix, or ``--`` when unknown."""
    if value is None:
        return "--"
    magnitude = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(magnitude) < 1024.0 or unit == "TiB":
            precision = 0 if unit == "B" else 1
            return f"{magnitude:.{precision}f} {unit}"
        magnitude /= 1024.0
    return f"{magnitude:.1f} TiB"


def format_rate(value: float | None) -> str:
    """Format a bytes-per-second rate, or ``--`` when unknown."""
    if value is None:
        return "--"
    return f"{format_bytes(value)}/s"


def format_duration(seconds: float | None) -> str:
    """Format a duration as ``NdNNh NNm``, or ``--`` when unknown."""
    if seconds is None or seconds < 0:
        return "--"
    total = int(seconds)
    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"


def format_percent(value: float | None) -> str:
    """Format a percentage to one decimal place, or ``--`` when unknown."""
    return "--" if value is None else f"{value:.1f}"


class HudController(QObject):
    """Owns assistant state, drives telemetry polling and routes commands."""

    stateChanged = Signal()
    modeChanged = Signal()
    snapshotChanged = Signal()
    logChanged = Signal()
    shutdownRequested = Signal()

    def __init__(
        self,
        sampler: TelemetrySampler | None = None,
        interval_ms: int = 1000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sampler = sampler if sampler is not None else TelemetrySampler()
        self._router = CommandRouter(_MODES)
        self._state = AssistantState.BOOTING
        self._mode = _MODES[0]
        self._snapshot = TelemetrySnapshot(monotonic_time=0.0)
        self._log: list[str] = []
        self._windowed = False

        self._interval_ms = max(MIN_INTERVAL_MS, interval_ms)
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._poll)

        self._boot_timer = QTimer(self)
        self._boot_timer.setSingleShot(True)
        self._boot_timer.setInterval(BOOT_DURATION_MS)
        self._boot_timer.timeout.connect(self._finish_boot)

        self.append_log(Severity.INFO, "J.A.V.R.I.S. core initialising.")

    # -- lifecycle ---------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Begin the boot sequence and start telemetry polling."""
        self._poll()  # Prime the counters so the first visible sample has deltas.
        self._timer.start()
        self._boot_timer.start()

    @Slot()
    def stop(self) -> None:
        """Stop all timers. Safe to call more than once."""
        self._timer.stop()
        self._boot_timer.stop()

    def _finish_boot(self) -> None:
        if self._state is AssistantState.BOOTING:
            self.set_state(AssistantState.STANDBY)
            self.append_log(Severity.OK, "All systems nominal. Standing by.")

    # -- telemetry ---------------------------------------------------------

    def _poll(self) -> None:
        snapshot = self._sampler.sample()
        previously_degraded = self._snapshot.is_degraded
        self._snapshot = snapshot
        self.snapshotChanged.emit()

        # Report degradation once on the transition, not on every poll, so a
        # persistently missing sensor cannot flood the console.
        if snapshot.is_degraded and not previously_degraded:
            self.append_log(
                Severity.WARN,
                f"Telemetry unavailable: {', '.join(snapshot.degraded_sources)}.",
            )
        elif previously_degraded and not snapshot.is_degraded:
            self.append_log(Severity.OK, "All telemetry sources restored.")

    # -- state -------------------------------------------------------------

    def set_state(self, target: AssistantState) -> None:
        """Transition to ``target``.

        Raises:
            InvalidTransitionError: If the transition is not permitted.
        """
        if not can_transition(self._state, target):
            raise InvalidTransitionError(self._state, target)
        if target is self._state:
            return
        self._state = target
        self.stateChanged.emit()

    @Slot(str, result=bool)
    def requestState(self, name: str) -> bool:  # noqa: N802 - QML naming convention
        """Attempt a transition by name, returning success rather than raising.

        QML has no exception contract, so illegal transitions requested from the
        UI are reported as a logged refusal instead of crashing the engine.
        """
        try:
            target = AssistantState(name.upper())
        except ValueError:
            self.append_log(Severity.ERROR, f"Unknown state '{name}'.")
            return False
        try:
            self.set_state(target)
        except InvalidTransitionError as error:
            self.append_log(Severity.ERROR, str(error))
            return False
        return True

    # -- commands ----------------------------------------------------------

    @Slot(str)
    def submitCommand(self, line: str) -> None:  # noqa: N802 - QML naming convention
        """Dispatch a console command and reflect its result in the HUD."""
        self.append_log(Severity.INFO, f"> {line.strip()}")
        result = self._router.dispatch(line)

        if result.message == "__CLEAR__":
            self._log.clear()
            self.logChanged.emit()
            return

        self.append_log(result.severity, result.message)
        if result.mode is not None and result.mode != self._mode:
            self._mode = result.mode
            self.modeChanged.emit()
        if result.shutdown:
            self.stop()
            self.shutdownRequested.emit()

    @Slot()
    def cycleMode(self) -> None:  # noqa: N802 - QML naming convention
        """Advance to the next HUD mode."""
        index = (_MODES.index(self._mode) + 1) % len(_MODES)
        self._mode = _MODES[index]
        self.modeChanged.emit()
        self.append_log(Severity.OK, f"Mode set to {self._mode}.")

    def append_log(self, severity: Severity, message: str) -> None:
        """Append one bounded, severity-tagged line to the console log."""
        self._log.append(f"{severity.value}\u001f{message}")
        if len(self._log) > MAX_LOG_LINES:
            del self._log[: len(self._log) - MAX_LOG_LINES]
        self.logChanged.emit()

    # -- properties exposed to QML ----------------------------------------

    def set_windowed(self, value: bool) -> None:
        """Choose windowed rather than full-screen presentation.

        Must be called before QML loads: the window flags it drives cannot be
        changed after the window has been created, which is why the QML-facing
        property is declared constant.
        """
        self._windowed = bool(value)

    @Property(bool, constant=True)
    def windowed(self) -> bool:
        """True when the HUD should open in a normal window, not full screen."""
        return self._windowed

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        """Current assistant state name."""
        return self._state.value

    @Property(str, notify=modeChanged)
    def mode(self) -> str:
        """Current HUD mode name."""
        return self._mode

    @Property(list, notify=logChanged)
    def log(self) -> list[str]:
        """Console lines, each ``SEVERITY\\x1fmessage``, oldest first."""
        return list(self._log)

    @Property(float, notify=snapshotChanged)
    def cpuPercent(self) -> float:  # noqa: N802
        """Aggregate CPU utilisation; -1.0 when not yet measurable."""
        value = self._snapshot.cpu_total_percent
        return -1.0 if value is None else value

    @Property(str, notify=snapshotChanged)
    def cpuText(self) -> str:  # noqa: N802
        """Aggregate CPU utilisation, formatted for display."""
        return format_percent(self._snapshot.cpu_total_percent)

    @Property(list, notify=snapshotChanged)
    def coreLoads(self) -> list[float]:  # noqa: N802
        """Per-core utilisation as 0.0-1.0 fractions."""
        return [percent / 100.0 for percent in self._snapshot.cpu_core_percents]

    @Property(float, notify=snapshotChanged)
    def memoryFraction(self) -> float:  # noqa: N802
        """Physical memory usage as a 0.0-1.0 fraction; -1.0 when unknown."""
        memory = self._snapshot.memory
        return -1.0 if memory is None else memory.used_fraction

    @Property(str, notify=snapshotChanged)
    def memoryText(self) -> str:  # noqa: N802
        """Memory usage as ``used / total``."""
        memory = self._snapshot.memory
        if memory is None:
            return "--"
        return f"{format_bytes(memory.used)} / {format_bytes(memory.total)}"

    @Property(float, notify=snapshotChanged)
    def swapFraction(self) -> float:  # noqa: N802
        """Swap usage as a 0.0-1.0 fraction; -1.0 when unknown."""
        memory = self._snapshot.memory
        return -1.0 if memory is None else memory.swap_used_fraction

    @Property(str, notify=snapshotChanged)
    def loadText(self) -> str:  # noqa: N802
        """Load averages over 1, 5 and 15 minutes."""
        load = self._snapshot.load_average
        if load is None:
            return "--"
        return f"{load.one:.2f}  {load.five:.2f}  {load.fifteen:.2f}"

    @Property(str, notify=snapshotChanged)
    def uptimeText(self) -> str:  # noqa: N802
        """System uptime, formatted for display."""
        return format_duration(self._snapshot.uptime_seconds)

    @Property(str, notify=snapshotChanged)
    def temperatureText(self) -> str:  # noqa: N802
        """CPU package temperature in Celsius, or ``--`` when no sensor exists."""
        value = self._snapshot.temperature_celsius
        return "--" if value is None else f"{value:.1f}"

    @Property(str, notify=snapshotChanged)
    def networkRxText(self) -> str:  # noqa: N802
        """Inbound network throughput."""
        return format_rate(self._snapshot.net_rx_bytes_per_sec)

    @Property(str, notify=snapshotChanged)
    def networkTxText(self) -> str:  # noqa: N802
        """Outbound network throughput."""
        return format_rate(self._snapshot.net_tx_bytes_per_sec)

    @Property(list, notify=snapshotChanged)
    def disks(self) -> list[dict[str, object]]:
        """Per-filesystem usage records for the storage panel."""
        return [
            {
                "mount": disk.mount_point,
                "fraction": disk.used_fraction,
                "text": f"{format_bytes(disk.used)} / {format_bytes(disk.total)}",
            }
            for disk in self._snapshot.disks
        ]

    @Property(bool, notify=snapshotChanged)
    def degraded(self) -> bool:
        """True when any telemetry source is unavailable."""
        return self._snapshot.is_degraded

    @Property(str, notify=snapshotChanged)
    def degradedText(self) -> str:  # noqa: N802
        """Comma-separated names of unavailable telemetry sources."""
        return ", ".join(self._snapshot.degraded_sources)
