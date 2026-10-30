from __future__ import annotations
import argparse
import multiprocessing as mp
from pathlib import Path
import sys


def main():
    mp.freeze_support()
    parser = argparse.ArgumentParser(description="STCKR — Linear-RAW Focus Stacking")
    sub = parser.add_subparsers(dest="command")
    stack = sub.add_parser("stack", help="Stack ohne Oberfläche berechnen")
    stack.add_argument("sources", nargs="+")
    stack.add_argument("-o", "--output", required=True)
    stack.add_argument("--method", choices=["A", "B", "C"], default="C")
    stack.add_argument("--radius", type=int, default=5)
    stack.add_argument("--smoothing", type=float, default=1.2)
    stack.add_argument("--levels", type=int, default=7)
    stack.add_argument("--no-align", action="store_true")
    stack.add_argument("--affine", action="store_true")
    stack.add_argument("--overwrite", action="store_true")
    stack.add_argument("--cache", default=".cache/stckr")
    gui = sub.add_parser("gui", help="Desktop-App starten")
    gui.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    demo = sub.add_parser("demo", help="Synthetische Beispielserie erzeugen")
    demo.add_argument("directory", nargs="?", default="demo-stack")
    args = parser.parse_args()
    if args.command == "demo":
        from .demo import create_demo
        create_demo(Path(args.directory))
        print(Path(args.directory).resolve())
        return
    if args.command == "stack":
        from .engine import run_stack
        from .models import Settings, ColorInfo
        from .export import export_image
        import numpy as np
        try:
            result = run_stack(args.sources, Settings(method=args.method, radius=args.radius,
                               smoothing=args.smoothing, levels=args.levels, align=not args.no_align,
                               affine=args.affine), args.cache,
                               lambda phase, p: print(f"\r{p:6.1%} {phase:35s}", end="", flush=True))
            export_image(args.output, np.load(result.image_path, mmap_mode="r"), ColorInfo(**result.color),
                         overwrite=args.overwrite)
            print(f"\n{Path(args.output).resolve()}")
        except Exception as error:
            parser.exit(1, f"\nFehler: {error}\n")
        return
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
    from PySide6.QtCore import QUrl
    from .backend import Backend
    from .canvas import PhotoCanvas
    app = QApplication(sys.argv[:1])
    app.setOrganizationName("STCKR")
    app.setApplicationName("STCKR")
    qmlRegisterType(PhotoCanvas, "STCKR", 1, 0, "PhotoCanvas")
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("studio", backend)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(backend.shutdown)
    if args.command == "gui" and args.smoke_test:
        from PySide6.QtCore import QTimer
        backend.add_paths(sorted(str(p) for p in args.smoke_test.glob("focus-*.png")))
        backend.render(5, 1.2, 5, False, False, False, False)
        def complete():
            if backend._results:
                app.exit(0)
            elif not backend.busy:
                app.exit(1)
        timer = QTimer()
        timer.timeout.connect(complete)
        timer.start(100)
        QTimer.singleShot(60000, lambda: app.exit(2))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
