"""Entrada interativa de token Kaggle sem eco ou histórico de comandos."""
from getpass import getpass
import os
from pathlib import Path
import sys
import tempfile


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Execute em um terminal interativo para digitar o token sem exibi-lo.")
    token = getpass("Cole o token Kaggle (entrada oculta): ").strip()
    if not token or any(character.isspace() for character in token) or token == '<YOUR_TOKEN>':
        raise SystemExit("Token vazio ou inválido. Cole somente o token gerado no Kaggle.")
    directory = Path(os.environ.get('KAGGLE_CONFIG_DIR', '.kaggle'))
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.token-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(token + '\n')
        os.replace(temporary, directory / 'access_token')
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Token salvo localmente. Valide o acesso listando os arquivos da competição.")


if __name__ == '__main__':
    main()
