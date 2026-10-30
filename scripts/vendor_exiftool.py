"""Fetch a pinned, SHA-512-verified ExifTool distribution from npm.

Windows: native launcher + Perl runtime. Other systems: Perl script + modules.
No npm or Node installation is needed at runtime or during packaging.
"""
import base64
import hashlib
from io import BytesIO
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request

PACKAGES = {
    "exe": "DcpybFsR7Dp3FMrPDaq3iy+dcFrPTYENJeazy19TQoefpp4MQml5YXMAx2TpYRFuYoFLcXi9dupyufdrj6sS+A==",
    "pl": "RPXLoynEgak2D9zclE4oCpXII4S3EZlHXJIFHvjktByDgM7+ievXBfqtEWw6dK0xbk/L+cLVTWKoUBhOH+P/1A==",
}


def main():
    kind = "exe" if sys.platform == "win32" else "pl"
    url = f"https://registry.npmjs.org/exiftool-vendored.{kind}/-/exiftool-vendored.{kind}-13.60.0.tgz"
    data = urllib.request.urlopen(url, timeout=120).read()
    assert base64.b64encode(hashlib.sha512(data).digest()).decode() == PACKAGES[kind], "Checksum mismatch"
    dest = Path(__file__).resolve().parents[1] / "vendor"
    dest.mkdir(exist_ok=True)
    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as archive:
        for item in archive.getmembers():
            relative = Path(item.name).relative_to("package")
            target = dest / relative
            if not target.resolve().is_relative_to(dest.resolve()) or item.issym() or item.islnk():
                raise ValueError("Unsafe archive member")
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(item) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(item.mode)
    print(f"ExifTool 13.60.0 installed in {dest}")


if __name__ == "__main__":
    main()
