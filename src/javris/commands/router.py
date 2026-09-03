"""Allow-list command dispatch for the HUD console.

Security posture: this router **never** executes a shell, spawns a process,
opens a file or touches the network. It maps a fixed vocabulary of verbs onto
in-process handlers. Anything not in the vocabulary is rejected with a message.
Input is length-capped and control characters are stripped before parsing, so a
pasted terminal escape sequence cannot reach the log renderer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

#: Hard cap on accepted input length. Longer input is rejected outright rather
#: than truncated, so a command is never silently reinterpreted.
MAX_COMMAND_LENGTH = 200


class Severity(str, Enum):
    """Log severity, mapped to a distinct colour in the HUD."""

    INFO = "INFO"
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of dispatching one command line."""

    severity: Severity
    message: str
    #: Requested HUD mode, when the command asked for one; otherwise ``None``.
    mode: str | None = None
    #: True when the command asked the application to exit.
    shutdown: bool = False


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """A single entry in the command vocabulary."""

    verb: str
    summary: str
    handler: Callable[[CommandRouter, tuple[str, ...]], CommandResult]


def _strip_control_characters(text: str) -> str:
    """Remove control characters, which have no legitimate place in a command."""
    return "".join(char for char in text if char.isprintable() or char == " ")


class CommandRouter:
    """Parses and dispatches console input against a fixed vocabulary.

    Args:
        modes: The HUD mode names that ``mode <name>`` may select.
    """

    def __init__(self, modes: tuple[str, ...] = ("DIAGNOSTICS", "MONITOR")) -> None:
        self._modes = modes
        self._specs: dict[str, CommandSpec] = {}
        for spec in (
            CommandSpec("help", "List available commands.", CommandRouter._cmd_help),
            CommandSpec("status", "Report current system status.", CommandRouter._cmd_status),
            CommandSpec(
                "mode",
                f"Switch HUD mode: {' | '.join(mode.lower() for mode in modes)}.",
                CommandRouter._cmd_mode,
            ),
            CommandSpec("clear", "Clear the console log.", CommandRouter._cmd_clear),
            CommandSpec("shutdown", "Close the HUD.", CommandRouter._cmd_shutdown),
        ):
            self._specs[spec.verb] = spec

    @property
    def verbs(self) -> tuple[str, ...]:
        """Every recognised verb, in alphabetical order."""
        return tuple(sorted(self._specs))

    def dispatch(self, line: str) -> CommandResult:
        """Parse and execute one command line.

        Never raises; every failure path returns a ``CommandResult`` the HUD can
        display, because an unparseable command is normal user input, not a bug.
        """
        if len(line) > MAX_COMMAND_LENGTH:
            return CommandResult(
                Severity.ERROR,
                f"Input rejected: exceeds {MAX_COMMAND_LENGTH} characters.",
            )

        cleaned = _strip_control_characters(line).strip()
        if not cleaned:
            return CommandResult(Severity.WARN, "Empty command ignored.")

        tokens = cleaned.split()
        verb = tokens[0].lower()
        spec = self._specs.get(verb)
        if spec is None:
            return CommandResult(
                Severity.ERROR,
                f"Unknown command '{verb}'. Type 'help' for the command list.",
            )
        return spec.handler(self, tuple(tokens[1:]))

    # -- handlers ----------------------------------------------------------

    def _cmd_help(self, _args: tuple[str, ...]) -> CommandResult:
        ordered = sorted(self._specs.values(), key=lambda spec: spec.verb)
        listing = "  ".join(f"{spec.verb} - {spec.summary}" for spec in ordered)
        return CommandResult(Severity.INFO, listing)

    def _cmd_status(self, _args: tuple[str, ...]) -> CommandResult:
        return CommandResult(Severity.OK, "All monitored subsystems reporting.")

    def _cmd_mode(self, args: tuple[str, ...]) -> CommandResult:
        if not args:
            return CommandResult(
                Severity.WARN,
                f"Usage: mode <{' | '.join(mode.lower() for mode in self._modes)}>",
            )
        requested = args[0].upper()
        if requested not in self._modes:
            return CommandResult(Severity.ERROR, f"Unknown mode '{args[0]}'.")
        return CommandResult(Severity.OK, f"Mode set to {requested}.", mode=requested)

    def _cmd_clear(self, _args: tuple[str, ...]) -> CommandResult:
        return CommandResult(Severity.INFO, "__CLEAR__")

    def _cmd_shutdown(self, _args: tuple[str, ...]) -> CommandResult:
        return CommandResult(Severity.WARN, "Shutting down.", shutdown=True)
