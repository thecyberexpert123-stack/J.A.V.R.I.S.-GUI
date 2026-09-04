"""The single QML-facing object: state, telemetry properties and command entry.

QML reads from here and never mutates anything except through the explicit
``@Slot`` methods, keeping data flow one-directional (backend -> presentation).
All formatting for display lives here so QML stays free of business logic.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .attention import Alert, AttentionMonitor, MetricReading, Prominence
from .bridge.client import KernelClient
from .bridge.protocol import Outcome, OutcomeKind
from .commands.router import CommandRouter, Severity
from .state import AssistantState, InvalidTransitionError, can_transition
from .telemetry.models import TelemetrySnapshot
from .telemetry.proc_reader import ProcReader
from .telemetry.service import MIN_INTERVAL_MS, TelemetrySampler

#: Duration of the boot sequence before the HUD settles into standby.
BOOT_DURATION_MS = 1800

#: Maximum console lines retained. Bounded so a long-running session cannot
#: grow the model without limit.
MAX_LOG_LINES = 200

_MODES = ("DIAGNOSTICS", "MONITOR", "ASSISTANT")

#: Which metrics each mode already presents as a large, central element.
#:
#: This table is the documented proxy for gaze direction used by
#: :mod:`javris.attention`; it must be kept in step with the mode QML. A metric
#: listed here is considered already-seen in that mode and is never escalated,
#: because escalation exists to move information the operator would otherwise
#: miss. DIAGNOSTICS foregrounds three large gauges; MONITOR foregrounds only
#: the reactor core, which encodes processor load.
_CENTRAL_METRICS: dict[str, frozenset[str]] = {
    "DIAGNOSTICS": frozenset({"cpu", "memory", "swap"}),
    "MONITOR": frozenset({"cpu"}),
    # ASSISTANT is a modal takeover: it deliberately shows almost no telemetry,
    # so nothing is "already central" and any breach is escalatable.
    "ASSISTANT": frozenset(),
}


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
    alertChanged = Signal()
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
        # Static host facts, read once: these cannot change while we run, so
        # polling them every frame would be waste.
        self._identity = ProcReader().read_host_identity()

        # -- agent bridge ---------------------------------------------------
        # Created but NOT started: connecting is an explicit act, and a HUD
        # that silently spawned a privileged agent on launch would be exactly
        # the kind of surprise this project avoids.
        self._kernel = KernelClient(self)
        self._kernel.connected.connect(self._on_kernel_connected)
        self._kernel.disconnected.connect(self._on_kernel_disconnected)
        self._kernel.completed.connect(self._on_kernel_completed)
        self._kernel.started.connect(self._on_kernel_started)
        #: Request awaiting the owner's decision, or an empty string.
        self._pending_consent: str = ""
        #: The most recent jarvis_do request text. Held so that a refusal can
        #: be re-sent verbatim after consent -- the owner must approve the
        #: exact request they were shown, never a reconstruction of it.
        self._last_do_request: str = ""
        self._log: list[str] = []
        self._windowed = False
        self._attention = AttentionMonitor()
        self._alert: Alert | None = None

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

        self._evaluate_attention()

    # -- attention escalation ---------------------------------------------

    def _metric_readings(self) -> tuple[MetricReading, ...]:
        """Describe every escalatable metric for the current mode.

        Only metrics with a meaningful saturation point appear here. Uptime,
        throughput and load average are excluded: they have no ceiling against
        which "how full is it" could be judged, so a fraction would be invented.
        """
        central = _CENTRAL_METRICS.get(self._mode, frozenset())

        def prominence(key: str) -> Prominence:
            return Prominence.CENTRAL if key in central else Prominence.PERIPHERAL

        cpu = self._snapshot.cpu_total_percent
        memory = self._snapshot.memory

        readings = [
            MetricReading(
                key="cpu",
                label="Processor load",
                fraction=None if cpu is None else cpu / 100.0,
                readout=format_percent(cpu),
                unit="%",
                prominence=prominence("cpu"),
                advice="Sustained processor saturation.",
            ),
            MetricReading(
                key="memory",
                label="Memory pressure",
                fraction=None if memory is None else memory.used_fraction,
                readout=("--" if memory is None else format_percent(memory.used_fraction * 100.0)),
                unit="%",
                prominence=prominence("memory"),
                advice="Physical memory near capacity.",
            ),
            MetricReading(
                key="swap",
                label="Swap pressure",
                fraction=None if memory is None else memory.swap_used_fraction,
                readout=(
                    "--" if memory is None else format_percent(memory.swap_used_fraction * 100.0)
                ),
                unit="%",
                prominence=prominence("swap"),
                advice="Swap in heavy use; expect stalls.",
            ),
        ]
        readings.extend(
            MetricReading(
                key=f"disk:{disk.mount_point}",
                label=f"Storage {disk.mount_point}",
                fraction=disk.used_fraction,
                readout=format_percent(disk.used_fraction * 100.0),
                unit="%",
                prominence=Prominence.PERIPHERAL,
                advice=f"Filesystem {disk.mount_point} is filling up.",
            )
            for disk in self._snapshot.disks
        )
        return tuple(readings)

    def _evaluate_attention(self) -> None:
        """Run the escalation policy and announce any change on the console."""
        previous = self._alert
        current = self._attention.update(self._metric_readings())
        self._alert = current

        if previous is None and current is None:
            return

        changed = (
            previous is None
            or current is None
            or previous.key != current.key
            or previous.severity is not current.severity
        )
        if not changed:
            # The readout moves every poll; the UI rebinds, but re-announcing an
            # unchanged condition on the console would just be noise.
            self.alertChanged.emit()
            return

        if current is None and previous is not None:
            self.append_log(Severity.OK, f"{previous.label} back within limits.")
        elif current is not None:
            severity = Severity.ERROR if current.severity.value == "CRITICAL" else Severity.WARN
            self.append_log(
                severity,
                f"{current.label} at {current.readout}{current.unit}. {current.advice}",
            )
        self.alertChanged.emit()

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
            self._set_mode(result.mode)
        if result.agent_disconnect:
            self._disconnect_agent()
        if result.agent_tool is not None:
            self._dispatch_agent(result.agent_tool, result.agent_argument)
        if result.shutdown:
            self.stop()
            self.shutdownRequested.emit()

    @Slot()
    def cycleMode(self) -> None:  # noqa: N802 - QML naming convention
        """Advance to the next HUD mode."""
        index = (_MODES.index(self._mode) + 1) % len(_MODES)
        self._set_mode(_MODES[index])
        self.append_log(Severity.OK, f"Mode set to {self._mode}.")

    def _set_mode(self, mode: str) -> None:
        """Switch mode and immediately re-run the escalation policy.

        Prominence is mode-dependent, so a mode change can make an escalated
        metric central (releasing the alert) or push a central one into the
        periphery. Re-evaluating here means the HUD is correct on the next
        frame rather than up to one poll interval later.
        """
        self._mode = mode
        self.modeChanged.emit()
        self._evaluate_attention()

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

    # -- attention properties ---------------------------------------------

    @Property(bool, notify=alertChanged)
    def alertActive(self) -> bool:  # noqa: N802
        """True when a condition has been escalated to the main display."""
        return self._alert is not None

    @Property(str, notify=alertChanged)
    def alertLabel(self) -> str:  # noqa: N802
        """Name of the escalated condition; empty when none is active."""
        return "" if self._alert is None else self._alert.label

    @Property(str, notify=alertChanged)
    def alertReadout(self) -> str:  # noqa: N802
        """Formatted value of the escalated condition."""
        return "" if self._alert is None else self._alert.readout

    @Property(str, notify=alertChanged)
    def alertUnit(self) -> str:  # noqa: N802
        """Unit suffix for :attr:`alertReadout`."""
        return "" if self._alert is None else self._alert.unit

    @Property(str, notify=alertChanged)
    def alertAdvice(self) -> str:  # noqa: N802
        """One-line explanation of the escalated condition."""
        return "" if self._alert is None else self._alert.advice

    @Property(str, notify=alertChanged)
    def alertSeverity(self) -> str:  # noqa: N802
        """``WARN``, ``CRITICAL``, or empty when no alert is active."""
        return "" if self._alert is None else self._alert.severity.value

    @Property(float, notify=alertChanged)
    def alertFraction(self) -> float:  # noqa: N802
        """Normalised 0.0-1.0 value of the escalated condition; -1.0 when none."""
        return -1.0 if self._alert is None else self._alert.fraction

    # -- battery ------------------------------------------------------------

    @Property(bool, notify=snapshotChanged)
    def batteryPresent(self) -> bool:  # noqa: N802
        """True when this host actually has a battery.

        Desktops, virtual machines and containers have none. The UI hides the
        whole readout rather than showing an empty or full cell.
        """
        return self._snapshot.battery is not None

    @Property(float, notify=snapshotChanged)
    def batteryFraction(self) -> float:  # noqa: N802
        """Charge as a 0.0-1.0 fraction; -1.0 when absent or unreadable."""
        battery = self._snapshot.battery
        if battery is None or battery.percent is None:
            return -1.0
        return battery.percent / 100.0

    @Property(str, notify=snapshotChanged)
    def batteryText(self) -> str:  # noqa: N802
        """Charge percentage, formatted for display."""
        battery = self._snapshot.battery
        if battery is None or battery.percent is None:
            return "--"
        return f"{battery.percent:.0f} %"

    @Property(str, notify=snapshotChanged)
    def batteryState(self) -> str:  # noqa: N802
        """``CHARGING``, ``DISCHARGING``, or ``UNKNOWN``.

        An unknown kernel status is reported as unknown rather than guessed:
        showing "discharging" on a machine that is plugged in would be a lie
        about the one thing this readout exists to convey.
        """
        battery = self._snapshot.battery
        if battery is None or battery.charging is None:
            return "UNKNOWN"
        return "CHARGING" if battery.charging else "DISCHARGING"

    @Property(str, notify=snapshotChanged)
    def batteryRuntimeText(self) -> str:  # noqa: N802
        """Estimated time to empty, or an empty string when not measurable."""
        battery = self._snapshot.battery
        if battery is None or battery.seconds_remaining is None:
            return ""
        return format_duration(battery.seconds_remaining)

    # -- host identity -------------------------------------------------------

    @Property(list, constant=True)
    def hostFacts(self) -> list[str]:  # noqa: N802
        """Static machine facts as ``label\\x1fvalue`` rows.

        Only genuinely readable facts appear. A host that exposes no CPU model
        simply yields fewer rows -- there is no placeholder text, and nothing
        here is invented. This is the honest counterpart to a "PC SPECS" panel
        listing fictional hardware.
        """
        identity = self._identity
        rows: list[tuple[str, str | None]] = [
            ("HOST", identity.hostname),
            ("OS", identity.os_name),
            ("KERNEL", identity.kernel_release),
            ("PROCESSOR", identity.cpu_model),
            (
                "LOGICAL CORES",
                None if identity.cpu_cores is None else str(identity.cpu_cores),
            ),
            (
                "MEMORY",
                None
                if identity.memory_total_bytes is None
                else format_bytes(identity.memory_total_bytes),
            ),
        ]
        return [f"{label}\x1f{value}" for label, value in rows if value]

    # -- agent bridge ---------------------------------------------------------

    agentChanged = Signal()
    consentChanged = Signal()

    @Property(bool, notify=agentChanged)
    def agentConnected(self) -> bool:  # noqa: N802
        """True once the kernel handshake has completed."""
        return self._kernel.ready

    @Property(str, notify=agentChanged)
    def agentVersion(self) -> str:  # noqa: N802
        """Kernel version string, or empty when not connected."""
        return self._kernel.version

    @Property(bool, notify=agentChanged)
    def agentAvailable(self) -> bool:  # noqa: N802
        """True when a jarvis executable exists on PATH."""
        return KernelClient.available()

    @Property(str, notify=consentChanged)
    def pendingConsent(self) -> str:  # noqa: N802
        """The request awaiting an owner decision, or an empty string.

        While this is non-empty the UI must show a consent prompt. It is the
        only path by which ``allow: true`` can ever be sent.
        """
        return self._pending_consent

    @Slot()
    def connectAgent(self) -> None:  # noqa: N802
        """Spawn the kernel and begin the handshake."""
        if self._kernel.ready:
            self.append_log(Severity.INFO, "Agent already connected.")
            return
        self.append_log(Severity.INFO, "Connecting to the JARVIS kernel...")
        self._request_state_quietly(AssistantState.PROCESSING)
        if not self._kernel.start():
            self._request_state_quietly(AssistantState.OFFLINE)

    @Slot()
    def approveConsent(self) -> None:  # noqa: N802
        """Re-send the pending request with the owner's explicit consent.

        This is the *only* place ``allow=True`` originates, and it is reachable
        only from a deliberate UI action. It clears the pending request first,
        so one approval can authorise exactly one call.
        """
        request = self._pending_consent
        if not request:
            return
        self._pending_consent = ""
        self.consentChanged.emit()
        self.append_log(Severity.WARN, f"Consent given. Executing: {request}")
        self._request_state_quietly(AssistantState.EXECUTING)
        if not self._kernel.execute(request, allow=True, tag="do"):
            self.append_log(Severity.ERROR, "The agent is not connected.")
            self._request_state_quietly(AssistantState.ERROR)

    @Slot()
    def declineConsent(self) -> None:  # noqa: N802
        """Dismiss the consent prompt without acting."""
        if not self._pending_consent:
            return
        self._pending_consent = ""
        self.consentChanged.emit()
        self.append_log(Severity.INFO, "Declined. Nothing was run.")
        self._request_state_quietly(AssistantState.STANDBY)

    def _disconnect_agent(self) -> None:
        self._kernel.stop()

    def _dispatch_agent(self, tool: str, argument: str) -> None:
        """Send one tool call on behalf of a console verb."""
        if not self._kernel.ready:
            self.append_log(
                Severity.ERROR,
                "The agent is not connected. Use the connect action first.",
            )
            return

        self._request_state_quietly(AssistantState.PROCESSING)
        if tool == "jarvis_do":
            # Never pre-authorised: the kernel decides whether this needs
            # consent, and only approveConsent() may answer that question.
            self._last_do_request = argument
            self._kernel.execute(argument, allow=False, tag="do")
        elif tool == "jarvis_explain":
            self._kernel.call(tool, {"question": argument}, tag="explain")
        elif tool == "jarvis_preview":
            self._kernel.call(tool, {"request": argument}, tag="preview")
        else:
            self._kernel.call(tool, {}, tag=tool)

    def _on_kernel_started(self, _tag: str) -> None:
        self._request_state_quietly(AssistantState.PROCESSING)

    def _on_kernel_connected(self, version: str) -> None:
        self.append_log(Severity.OK, f"Agent connected. Kernel {version}.")
        self.agentChanged.emit()
        self._request_state_quietly(AssistantState.STANDBY)

    def _on_kernel_disconnected(self, reason: str) -> None:
        self.append_log(Severity.WARN, reason)
        self.agentChanged.emit()
        if self._pending_consent:
            self._pending_consent = ""
            self.consentChanged.emit()
        # Telemetry keeps running: losing the agent must never take the HUD
        # down with it (honest degradation, never a faked agent).
        self._request_state_quietly(AssistantState.STANDBY)

    def _on_kernel_completed(self, tag: str, outcome: Outcome) -> None:
        """Render one tool result and move the state machine accordingly."""
        if outcome.kind is OutcomeKind.REFUSED:
            self.append_log(Severity.WARN, outcome.text)
            if outcome.hint:
                self.append_log(Severity.INFO, outcome.hint)
            if outcome.consent_required and tag == "do":
                # Hold the request so approveConsent() has something to send.
                # Storing the text is not authorisation; only the owner's
                # action is.
                self._pending_consent = self._last_do_request
                self.consentChanged.emit()
            self._request_state_quietly(AssistantState.STANDBY)
            return

        if outcome.kind in (OutcomeKind.FAILED, OutcomeKind.PROTOCOL_ERROR):
            self.append_log(Severity.ERROR, outcome.text)
            self._request_state_quietly(AssistantState.ERROR)
            return

        self._request_state_quietly(AssistantState.SPEAKING)
        self.append_log(Severity.OK, outcome.text)
        self._request_state_quietly(AssistantState.STANDBY)

    def _request_state_quietly(self, target: AssistantState) -> None:
        """Move to ``target`` when the transition table permits it.

        Illegal transitions are skipped rather than logged as errors: the
        bridge reports what the kernel is doing, and the state table is the
        authority on which of those reports can be represented right now.
        """
        if can_transition(self._state, target):
            self.set_state(target)
