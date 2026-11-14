# Comando operacional — F09.1

O comando valida dependências locais já aprovadas (RAW, recorte, Bronze e landing
F04), espelha entradas por hash e executa Silver → Gold → publicação S3.
Não exige F05/F06 como comparadores nem injeta falhas ou reinicia o servidor
no meio do processamento. A aquisição autenticada e os aceites de entrada
continuam nos comandos documentados no README; fonte ausente bloqueia a operação.

```bash
bash scripts/objects.sh -m src.pipelines.operate_lakehouse \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --source-report artifacts/f04/runs/20261113T020347Z_1609747b.json \
  --mode update --batch b00_w000_051
```

| Modo | Efeito |
|---|---|
| update | Aplica todos os pacotes até `--batch`, inclusive, preservando a ordem; exige limite explícito |
| replay | Reenvia os pacotes ao mesmo estado; recibos/revisões evitam duplicações; sem limite, inclui todos |
| rebuild | Cria estado novo por run_id e reconstrói os pacotes; sem limite, inclui todos; preserva o estado anterior |

`--batch` também limita replay/rebuild. É o batch_id exato do manifesto F04,
não uma data de negócio. Um limite anterior a um lote já aplicado é recusado:
para obter resultado histórico, usar rebuild em vez de tentar regredir o estado.
A entrada é o catálogo finito de sete pacotes simulados da F04, não um feed CDC.

Cada execução compara a Silver com uma reconstrução independente antes de
publicar. A Gold usa os mesmos contratos e SQL; nesta interface, materializa-se
a ABT integral da saída selecionada. Publicações são imutáveis, com três Silver
e duas Gold, e ficam em `operational-publications/<selection_id>`; CURRENT F08
permanece no registro da demonstração. O estado operacional fica em `operations/`.
Alterar código/configuração cria outra identidade de estado.

Relatórios: `artifacts/f09/runs/<run_id>.json`. Mesmo uma falha registra etapa e
causa quando ocorre dentro do executor. O [supervisor F09.2](ESTADOS_E_ERROS.md)
registra também inicialização, tentativas, códigos de saída e classificação de retry.

O serviço iniciado pelo comando é parado no finally; um serviço já ligado é
mantido ligado. Backend e credenciais são preservados. Um lock operacional
serializa comandos desta interface; os locks dos componentes continuam ativos.
Adotar um host/driver cooperante por vez, incluindo execução das demonstrações.

Validação real aprovada: [evidência F09.1](../evidencias/F09_COMANDO_UNICO.md).
Não executar dois comandos Spark simultaneamente.
