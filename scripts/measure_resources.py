"""Amostra RSS da árvore de processos e bytes do diretório temporário em Linux."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def process_tree_rss(root_pid):
    processes = {}
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            status = {}
            for line in (directory / 'status').read_text().splitlines():
                if line.startswith(('PPid:', 'VmRSS:')):
                    key, value = line.split(':', 1)
                    status[key] = int(value.split()[0])
            processes[int(directory.name)] = (status['PPid'], status.get('VmRSS', 0) * 1024)
        except (OSError, ValueError, KeyError):
            continue
    descendants = {root_pid}
    while True:
        more = {pid for pid, (parent, _) in processes.items() if parent in descendants}
        if more <= descendants:
            break
        descendants |= more
    return sum(processes.get(pid, (0, 0))[1] for pid in descendants)


def directory_bytes(root):
    total = 0
    for path in root.rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass  # Arquivos temporários podem desaparecer entre listagem e stat.
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/resource_check.json'))
    parser.add_argument('--workdir', type=Path, default=Path('.runtime/tmp'))
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Informe um comando após --')
    if not Path('/proc').is_dir():
        parser.error('Medição implementada para Linux/WSL com /proc')
    started = time.perf_counter()
    peak_rss = peak_workdir = samples = 0
    process = subprocess.Popen(command)
    while True:
        peak_rss = max(peak_rss, process_tree_rss(process.pid))
        peak_workdir = max(peak_workdir, directory_bytes(args.workdir))
        samples += 1
        if process.poll() is not None:
            break
        time.sleep(0.1)
    result = {
        'command': command, 'exit_code': process.returncode,
        'duration_seconds': round(time.perf_counter() - started, 3),
        'peak_process_tree_rss_bytes': peak_rss,
        'peak_workdir_logical_bytes': peak_workdir,
        'workdir': str(args.workdir), 'samples': samples, 'interval_seconds': 0.1,
        'limitations': 'RSS soma páginas compartilhadas; amostragem pode perder picos curtos. '
                       'Disco mede somente arquivos lógicos no workdir, não caches, SO ou blocos físicos.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
