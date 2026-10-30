import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from stckr.__main__ import main
    raise SystemExit(main())
