"""Runtime Java 17 portátil para Linux x86_64; sem alterar pacotes do sistema."""
import hashlib
from pathlib import Path
import platform
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / ".runtime" / "java"
VERSION = "17.0.21+9"
URL = ("https://github.com/adoptium/temurin17-binaries/releases/download/"
       "jdk-17.0.21%2B9/OpenJDK17U-jre_x64_linux_hotspot_17.0.21_9.tar.gz")
SHA256 = "9f41bf88c7900c7097444a1bdeb84146ae692bc08842490ab098063c74bf9a8a"


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("Bootstrap validado apenas para Linux x86_64. Configure Java 17 via JAVA_HOME.")
    if (ROOT / f"jdk-{VERSION}-jre" / "bin" / "java").is_file():
        print("Runtime Java já disponível")
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    archive = ROOT / "temurin17.tar.gz"
    try:
        with urllib.request.urlopen(URL, timeout=120) as response, archive.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError("Checksum Java diferente do esperado")
        with tarfile.open(archive) as bundle:
            bundle.extractall(ROOT, filter="data")
    finally:
        archive.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
