"""F09.2: CLI com relatório de inicialização, estados, erros e retry limitado."""
import argparse
import json
from pathlib import Path
from src.operation.runner import supervise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--source-report', required=True)
    parser.add_argument('--mode', choices=('update','replay','rebuild'), required=True)
    parser.add_argument('--batch')
    parser.add_argument('--max-attempts', type=int, choices=(1,2,3), default=2)
    parser.add_argument('--retry-delay', type=float, default=2)
    args = parser.parse_args()
    if args.mode == 'update' and not args.batch: parser.error('update exige --batch')
    if not 0 <= args.retry_delay <= 30: parser.error('retry-delay deve estar entre 0 e 30')
    options = dict(sample=args.sample, source_report=args.source_report, mode=args.mode, batch=args.batch)
    result = supervise(Path(__file__).resolve().parents[2], options,
        max_attempts=args.max_attempts, retry_delay=args.retry_delay)
    print(json.dumps(result))
    return result['exit_code']


if __name__ == '__main__': raise SystemExit(main())
