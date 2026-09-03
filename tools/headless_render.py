#!/usr/bin/env python3
"""Render the HUD offscreen to a PNG for review, and verify it loads cleanly.

This is a smoke test and a review aid, not a pass/fail visual assertion. Qt's
own testing guidance warns against bitmap comparison as a gate, because
resolution, fonts and themes make it flaky; the image produced here is for a
human to look at. The *assertion* is that the QML graph loads without errors
and produces a non-empty frame.

Usage:
    python tools/headless_render.py --output build/hud.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSize, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
UI_ROOT = SRC_ROOT / "javris" / "ui"

# Allow running from a source checkout without an editable install.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from javris.controller import HudController  # noqa: E402
from javris.qmlregistration import register_controller  # noqa: E402
from javris.telemetry.service import TelemetrySampler  # noqa: E402


def render(
    output: Path,
    width: int,
    height: int,
    settle_ms: int,
    mode: str | None = None,
    state: str | None = None,
) -> int:
    """Load the HUD offscreen and save a frame. Returns a process exit code."""
    QCoreApplication.setAttribute(  # Software rasteriser: no GPU in CI.
        getattr(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt, "AA_UseSoftwareOpenGL", None) or 0
    )
    app = QGuiApplication(sys.argv)

    controller = HudController(sampler=TelemetrySampler(), interval_ms=200)
    controller.set_windowed(True)
    register_controller(controller)

    view = QQuickView()
    view.engine().addImportPath(str(SRC_ROOT))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(QSize(width, height))
    view.setSource(QUrl.fromLocalFile(str(UI_ROOT / "HudSurface.qml")))

    if view.status() != QQuickView.Status.Ready:
        for error in view.errors():
            print(f"QML error: {error.toString()}", file=sys.stderr)
        return 1

    if view.rootObject() is None:
        print("QML loaded but produced no root object.", file=sys.stderr)
        return 1

    controller.start()

    if mode is not None and controller.mode != mode:
        controller.cycleMode()
    if state is not None:
        # Walk the legal path out of BOOTING before forcing the target state.
        controller.requestState("STANDBY")
        controller.requestState(state)

    exit_code = 0

    def capture() -> None:
        nonlocal exit_code
        image = view.grabWindow()
        if image.isNull() or image.width() == 0:
            print("Frame grab produced an empty image.", file=sys.stderr)
            exit_code = 1
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output))
            print(f"Wrote {output} ({image.width()}x{image.height()})")
        controller.stop()
        app.quit()

    # Let the boot animation and the first telemetry poll settle first.
    QTimer.singleShot(settle_ms, capture)
    app.exec()

    # Tear the view down explicitly. Otherwise it is destroyed during
    # interpreter shutdown, after the context properties have gone, and every
    # binding re-evaluates against a null controller - producing a wall of
    # harmless but alarming TypeError output.
    view.setSource(QUrl())
    view.deleteLater()
    QCoreApplication.processEvents()
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/hud.png"))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument(
        "--mode",
        choices=["DIAGNOSTICS", "MONITOR"],
        default=None,
        help="Render a specific HUD mode instead of the default.",
    )
    parser.add_argument("--state", default=None, help="Force an assistant state, e.g. PROCESSING.")
    parser.add_argument(
        "--settle",
        type=int,
        default=2500,
        help="Milliseconds to wait before capturing, so animations settle.",
    )
    args = parser.parse_args()
    return render(args.output, args.width, args.height, args.settle, args.mode, args.state)


if __name__ == "__main__":
    raise SystemExit(main())
