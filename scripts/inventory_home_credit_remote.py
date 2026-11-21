"""Lista o catálogo remoto; não baixa dados. Execute via scripts/project.sh."""
import json
import re
from datetime import datetime, timezone
import yaml
from pathlib import Path
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi(); api.authenticate()
    files=[]; token=None; seen=set()
    while True:
        page=api.competition_list_files('home-credit-credit-risk-model-stability',page_token=token,page_size=100)
        files.extend({'name': f.name, 'bytes': f.total_bytes} for f in page.files)
        token=page.next_page_token
        if not token: break
        if token in seen: raise RuntimeError('Paginação repetida')
        seen.add(token)
except Exception:
    raise SystemExit('Falha ao consultar catálogo Kaggle; verifique acesso e rede.')
assert len(files)==len({f['name'] for f in files})
Path('artifacts/expansion').mkdir(parents=True, exist_ok=True)
Path('artifacts/expansion/remote_files.json').write_text(json.dumps({'competition':'home-credit-credit-risk-model-stability','files':sorted(files,key=lambda f:f['name'])},indent=2)+'\n')
print('Arquivos catalogados:',len(files))

groups = {}
for item in sorted(files, key=lambda f: f['name']):
    if not item['name'].startswith('parquet_files/train/'):
        continue
    logical = re.sub(r'(_[012])_\d+$', r'\1', Path(item['name']).stem)
    groups.setdefault(logical, []).append(item)
catalog = {'version': 1, 'competition': 'home-credit-credit-risk-model-stability',
           'scope': 'all_train_parquet', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
           'dictionary': 'feature_definitions.csv', 'tables': groups}
Path('configs/home_credit_expansion_catalog.yaml').write_text(yaml.safe_dump(catalog, sort_keys=False))
print('Tabelas de treino:', len(groups))
