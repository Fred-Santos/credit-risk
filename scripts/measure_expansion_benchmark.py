"""E01: mede árvore, memória do host e diretórios efetivos da carga."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid
from scripts.measure_resources import process_tree_rss, directory_bytes


def host_memory():
    return {k:int(v.split()[0])*1024 for k,v in
            (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
            if k in {'MemTotal','MemAvailable','SwapTotal','SwapFree'}}


def main():
    root = Path(__file__).resolve().parents[1]
    run_id = uuid.uuid4().hex
    target = root / 'artifacts/expansion/e01' / run_id
    scratch = root / '.runtime/tmp/expansion' / run_id
    memory = host_memory()
    # Não iniciar carga de heap 8 GiB sem ao menos 10 GiB disponíveis no host.
    if memory['MemAvailable'] < 10 * 1024**3:
        raise RuntimeError('Menos de 10 GiB disponíveis; fechar cargas concorrentes antes de medir')
    command = [str(root/'.venv/bin/python'),'-m','scripts.benchmark_expansion','--run-id',run_id]
    start = time.monotonic()
    result = {'run_id':run_id, 'command':command, 'initial_host':memory,
        'peak_tree_rss_bytes':0, 'peak_scratch_bytes':0, 'peak_artifacts_bytes':0,
        'min_mem_available_bytes':memory['MemAvailable'], 'max_swap_used_bytes':0,
        'min_disk_free_bytes':shutil.disk_usage(root).free, 'samples':0,
        'interval_seconds':0.5, 'pressure_interrupt':False,
        'limitations':'RSS pode contar páginas compartilhadas e perder picos; diretórios medidos não incluem dados do serviço SeaweedFS. Spill é obtido dos event logs, não desta amostragem.'}
    child = subprocess.Popen(command,cwd=root,start_new_session=True)
    pressure = 0
    while True:
        memory = host_memory()
        result['samples'] += 1
        result['peak_tree_rss_bytes'] = max(result['peak_tree_rss_bytes'],process_tree_rss(child.pid))
        result['peak_scratch_bytes'] = max(result['peak_scratch_bytes'],directory_bytes(scratch))
        result['peak_artifacts_bytes'] = max(result['peak_artifacts_bytes'],directory_bytes(target))
        result['min_mem_available_bytes'] = min(result['min_mem_available_bytes'],memory['MemAvailable'])
        result['max_swap_used_bytes'] = max(result['max_swap_used_bytes'],memory['SwapTotal']-memory['SwapFree'])
        result['min_disk_free_bytes'] = min(result['min_disk_free_bytes'],shutil.disk_usage(root).free)
        pressure = pressure+1 if memory['MemAvailable'] < 1024**3 else 0
        if child.poll() is not None: break
        if pressure >= 3 and not result['pressure_interrupt']:
            os.killpg(child.pid,signal.SIGINT)
            result['pressure_interrupt'] = True
        time.sleep(.5)
    result.update(exit_code=child.returncode, duration_seconds=round(time.monotonic()-start,3), final_host=host_memory())
    target.mkdir(parents=True,exist_ok=True)
    (target/'resources.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'run_id':run_id,'exit_code':child.returncode,'resources':str(target/'resources.json')}))
    return child.returncode


if __name__ == '__main__':
    raise SystemExit(main())
