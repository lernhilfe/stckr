"""Load the actual QML UI, render a frame, and optionally save a screenshot."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
from pathlib import Path
import sys
from PySide6.QtCore import QTimer, QUrl, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from stckr.backend import Backend
from stckr.canvas import PhotoCanvas


def main():
    errors = []
    def log(kind, context, message):
        print(message, file=sys.stderr)
        if "Error" in message or "failed" in message or "is not" in message or "Cannot" in message:
            errors.append(message)
    qInstallMessageHandler(log)
    app = QApplication([])
    app.setApplicationName("STCKR-Smoke")
    app.setOrganizationName("STCKR")
    qmlRegisterType(PhotoCanvas, "STCKR", 1, 0, "PhotoCanvas")
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("studio", backend)
    import stckr
    engine.load(QUrl.fromLocalFile(str(Path(stckr.__file__).parent / "qml" / "Main.qml")))
    assert engine.rootObjects(), "QML konnte nicht geladen werden"
    if "--demo" in sys.argv:
        from stckr.demo import create_demo
        from stckr.engine import run_stack
        from stckr.models import Settings
        root = Path("/tmp/stckr-gui-demo") if sys.platform != "win32" else Path(os.environ["TEMP"]) / "stckr-gui-demo"
        create_demo(root, 900, 600)
        paths = sorted(str(p) for p in root.glob("focus-*.png"))
        backend.add_paths(paths)
        result = run_stack(paths, Settings(align=False), root / "cache")
        backend._results.append(result.to_dict())
        backend.resultsChanged.emit()
        backend.selectResult(0)
    def finish():
        if "--screenshot" in sys.argv:
            target = sys.argv[sys.argv.index("--screenshot") + 1]
            assert engine.rootObjects()[0].grabWindow().save(target)
        app.quit()
    QTimer.singleShot(1500, finish)
    app.exec()
    backend.shutdown()
    assert not errors, "\n".join(errors)
    print("GUI smoke passed")


if __name__ == "__main__":
    main()
