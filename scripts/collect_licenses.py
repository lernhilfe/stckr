from importlib.metadata import distributions
from pathlib import Path
import shutil


def main():
    destination = Path("vendor/licenses")
    destination.mkdir(parents=True, exist_ok=True)
    for dist in distributions():
        name = dist.metadata.get("Name", "unknown")
        for file in dist.files or []:
            if any(term in str(file).lower() for term in ("license", "copying", "copyright", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = destination / name / str(file).replace("..", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    print(destination.resolve())


if __name__ == "__main__":
    main()
