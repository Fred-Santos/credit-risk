# Evidência — contratos, coorte e lotes

Data: 12/11/2026. Escopo: F00.4, F00.5 e F02.2.
Fonte: arquivos reais Home Credit selecionados na entrega anterior.

## 1. Definições e implementação

- [Contratos das tabelas](../contratos/README.md) e [YAML executável](../../configs/contracts/home_credit_v1.yaml).
- [Política do recorte/lotes](../RECORTE_E_LOTES.md) e [configuração](../../configs/sample_policy.yaml).
- [Validador](../../src/quality/contracts.py) e [construtor do recorte](../../src/pipelines/build_sample.py).

Os schemas registram 214 entradas de campos entre três tabelas lógicas. Regras
de nulabilidade, chaves, referências e cobertura foram definidas explicitamente;
a simples ausência de nulos em uma coluna não foi tratada como obrigatoriedade.
Os seis arquivos de origem têm fingerprint fixado no contrato. Um arquivo
declarado sem fingerprint é erro de configuração, não uma entrada implicitamente aceita.

## 2. Execução

Na raiz do repositório:

```bash
bash scripts/project.sh -m src.pipelines.build_sample
bash scripts/project.sh -m src.pipelines.build_sample
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Primeiro run da implementação aceita: `20261112T190239Z_18f339a8`.
Artefato selecionado: `7d58bbdaa00cbabfbce54d26`.
Diretório local: `data/samples/7d58bbdaa00cbabfbce54d26/`.

O arquivo `_selection.json` guarda a identidade completa, fingerprints da
implementação/configuração/origem, checksums de saída, relatórios de contrato
e lotes. Relatórios resumidos por tentativa ficam em `artifacts/samples/`.
Os arquivos com dados individuais ficam fora do Git.

## 3. Validações executadas

| Verificação | Resultado |
|---|---|
| Edição dos seis arquivos de origem | Fingerprints coincidem com contrato |
| Schema de cada shard | Coincide com schema completo da tabela lógica |
| Contrato na origem | 16 verificações aprovadas |
| Contrato no recorte gravado | 16 verificações aprovadas |
| Valores e multiplicidade após gravação | Iguais às linhas selecionadas na origem, nos dois sentidos |
| Integridade da origem ao concluir | Confirmada novamente antes da publicação |
| Coorte/lotes | Cada caso atribuído a um lote; totais por lote reconciliados |
| Preservação | RAW original não regravada; saída publicada em pasta separada |

Os 16 checks não incluem na contagem os testes exatos de schema/fingerprint,
que falham antecipadamente em caso de desvio. A comparação bidirecional usa
`exceptAll`, preservando a verificação de multiplicidade e de nulos. Conferir
somente contagens não teria sido suficiente.

## 4. Coorte observada

| Tabela | Linhas | Casos distintos | Órfãos |
|---|---:|---:|---:|
| Base | 50.000 | 50.000 | Não se aplica |
| Estática | 50.000 | 50.000 | 0 |
| Aplicações anteriores | 215.390 | 40.076 | 0 |

A auxiliar histórica não tem correspondência para 9.924 casos, resultado aceito
pelo contrato. Sua cobertura é 80,152%. Não foram truncadas linhas históricas
dos casos selecionados; todas as relacionadas foram preservadas.

O recorte contém as 92 semanas e cobre 2019-01-01 a 2020-10-05 nesta seleção.
O rótulo 1 aparece em 1.578 casos e o rótulo 0 em 48.422. A proporção de 3,156%
é descritiva; não foi usada como critério de seleção ou aprovação da amostra.

Digest do conjunto de IDs ordenados:

```text
4d17a83b11c2d341786ff906783d729906f4634f80a65a1d1839b805ece92a0b
```

Tamanho observado do diretório publicado, somando arquivos lógicos:
13.899.266 bytes. Esse valor inclui metadados e não representa RAM ou pico de
disco da execução. Versões anteriores de desenvolvimento do recorte foram
preservadas em diretórios distintos; cada manifesto identifica sua implementação.

## 5. Lotes atribuídos

| Lote | Semanas | Casos/base/estática | Linhas históricas |
|---|---|---:|---:|
| `b00_w000_051` | 0–51 | 35.046 | 136.687 |
| `b01_w052_077` | 52–77 | 10.022 | 50.044 |
| `b02_w078_091` | 78–91 | 4.932 | 28.659 |
| Total | 0–91 | 50.000 | 215.390 |

A atribuição foi persistida em `case_batches/`. É uma simulação de chegada,
sem data real de ingestão na Home Credit. A entrega/processamento dos lotes como
incrementos, correções e atrasos ainda pertence a F04. Não há CDC ou merge Silver
implementado por essa atribuição.

## 6. Reexecução e testes

A segunda execução retornou `reused: true`, o mesmo identificador e o mesmo
digest dos casos, após conferir os arquivos gravados e a edição da origem.
Run da reexecução: `20261112T190529Z_5a497f3a`. O relatório local por tentativa
registra esse resultado; o recorte publicado foi reutilizado sem regravar seus arquivos.

Suíte obrigatória atual: **42 testes aprovados, nenhum ignorado**, em 29,486 s.
Foram adicionados testes de:

- Seleção Spark comparada com referência independente Python.
- Independência em relação a ordem das linhas, partições e rótulos.
- Lacuna/sobreposição de lotes, limite inválido e identificador repetido.
- Nulos opcionais e histórico vazio válidos.
- Nulos obrigatórios, referências órfãs e colunas extras reprovados.
- Mudança da edição da fonte e arquivo declarado sem fingerprint.
- Alteração ou arquivo adicional no recorte já publicado.

Os testes usam fixtures controladas; os números das tabelas acima vieram da
execução com os arquivos reais, registrada separadamente.

## 7. Limites e próxima etapa

O recorte não é ABT, Silver ou Gold. Não agrega atributos, não imputa nulos,
não converte as datas de origem e não prova disponibilidade temporal de features.

A etapa seguinte é F02.3: permitir que a Bronze receba explicitamente esse
recorte e validar primeira carga, repetição, falha e recuperação reais. Em seguida,
alinhar contratos de revisão, regras Bronze e reconciliação RAW/recorte → Bronze.
Não mudar a configuração da RAW original para contornar essa adaptação.
