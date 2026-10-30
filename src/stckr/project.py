"""Portable projects: copied results/history, referenced originals, regenerable decode cache."""
from pathlib import Path
import json
import os
import shutil
import uuid


def save_project(destination, sources, results):
    dest = Path(destination)
    if dest.suffix != ".stckr":
        dest = dest.with_suffix(".stckr")
    if dest.exists():
        raise FileExistsError("Bitte einen neuen Projektnamen wählen; vorhandene Projekte werden nicht überschrieben.")
    temp = dest.with_name("." + dest.name + "-" + uuid.uuid4().hex[:8])
    temp.mkdir(parents=True)
    try:
        saved_results = []
        for result in results:
            shutil.copytree(result["directory"], temp / "results" / result["id"])
            item = dict(result)
            item["directory"] = "results/" + item["id"]
            saved_results.append(item)
        data = {"version": 1, "sources": sources, "results": saved_results}
        (temp / "project.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.rename(temp, dest)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return dest


def load_project(path):
    path = Path(path)
    if path.name == "project.json":
        path = path.parent
    root = path.resolve()
    data = json.loads((root / "project.json").read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Nicht unterstützte Projektversion")
    for result in data["results"]:
        directory = (root / result["directory"]).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Ungültiger Ergebnispfad im Projekt")
        result["directory"] = str(directory)
        if not (directory / "result.npy").is_file():
            raise ValueError("Unvollständiges Projekt: Ergebnis fehlt")
    return data
