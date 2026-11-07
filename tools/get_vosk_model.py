"""Downloads the offline speech model (about 40 MB) into models/.   Run from the project folder:

    python tools/get_vosk_model.py

models/ is not stored in git (it's too big), so you need this once per copy of the project, and again if you
ever delete the project folder. If the download fails, get the zip by hand from
https://alphacephei.com/vosk/models and unzip it so this folder exists:  models/vosk-model-small-en-us-0.15
"""
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NAME = "vosk-model-small-en-us-0.15"
URL = f"https://alphacephei.com/vosk/models/{NAME}.zip"
ROOT = Path(__file__).resolve().parents[1]


def install(url=URL, models_dir=ROOT / "models"):
    """Download + unzip the model. Returns the installed folder. Does nothing if it's already there."""
    models_dir = Path(models_dir)
    target = models_dir / NAME
    if target.exists():
        print(f"Already installed: {target}")
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        archive = tmp / "model.zip"
        print(f"Downloading {url}\n(about 40 MB, this can take a minute)")
        with urllib.request.urlopen(url, timeout=60) as response, open(archive, "wb") as out:
            shutil.copyfileobj(response, out)
        unpacked = (tmp / "unpacked").resolve()
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():                       # refuse anything that would escape the folder
                if not str((unpacked / member).resolve()).startswith(str(unpacked)):
                    raise RuntimeError(f"unsafe path in zip: {member}")
            z.extractall(unpacked)
        if not (unpacked / NAME).is_dir():
            raise RuntimeError(f"the zip did not contain a '{NAME}' folder")
        shutil.move(str(unpacked / NAME), str(target))
    print(f"Installed: {target}")
    return target


if __name__ == "__main__":
    try:
        install(sys.argv[1] if len(sys.argv) > 1 else URL)
    except Exception as exc:
        print(f"\nCould not install the speech model: {exc}")
        print("Download it by hand from https://alphacephei.com/vosk/models and unzip it to:")
        print(f"    {ROOT / 'models' / NAME}")
        sys.exit(1)
