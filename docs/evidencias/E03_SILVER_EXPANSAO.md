# E03 — Silver extensível e revisões

Estado: E03.1–E03.4 aceitos no escopo local. Snapshot `ef9c66b2a9d86511bcb8d3d5`.
[Contratos e limites](../contratos/EXPANSAO_SILVER_E_ABT.md).

Foram publicadas **17 tabelas Delta**, com **92,174,107 linhas**,
preservando todas as colunas da Bronze e acrescentando revisão inicial 1 e flag
de simulação false. As 58 conversões ISO enumeradas no contrato terminaram sem
novos nulos. Todas as tabelas passaram por chaves únicas/não nulas, domínios,
finito, referência à base e comparação exata de cada célula com a transformação
aprovada da Bronze. Os vínculos entre grupos auditados tiveram zero órfãos.
As tabelas vazias na janela são: train_tax_registry_c_1. Seus schemas foram preservados.

Os pins registram UUID, versão zero, schema e contagem. O manifesto foi publicado
por rename após aprovação conjunta, sem ativar CURRENT ou modificar o MVP.
Os arquivos/logs Delta têm checksums. A reexecução confirmou reuso do pacote
sem reescrever as tabelas. A transformação bloqueia o pacote inteiro
em caso de rejeição; diagnóstico privado por chave/arquivo/regra é reproduzível
com `scripts/diagnose_expansion_source.py`. A fixture inválida demonstrou esse
registro e a preservação da entrada. Não houve rejeições na execução real.

Uma correção em `train_other_1` foi simulada em snapshot filho privado
`c5cdbdab075752f4f5af26cf`: +1 unidade transformada em um valor, revisão 2.
O MERGE foi conferido por reconstrução independente; o pai permaneceu intacto.
**Um caso afetado**, meses antigos/novos [202001],
foi registrado sem coletar os IDs no driver. A reexecução reutilizou o filho.
As outras tabelas continuam pinadas ao pai; não houve CDC real.

| Medição | Resultado |
|---|---:|
| Processo Silver completo | 982.721 s |
| Pico RSS da árvore | 9.59 GiB |
| Pico de temporários medidos | 4.91 GiB |

A JVM usou heap de 8 GiB no Linux/WSL com cerca de 15,46 GiB visíveis. RSS inclui
memória fora do heap e pode somar páginas compartilhadas; amostras podem perder
picos. O medidor cobre `.runtime/tmp/expansion-stages`, não todo o disco.
A primeira execução Silver usou o padrão Delta de 50 partições de snapshot;
os comandos posteriores explicitam quatro, como no perfil S3 anterior.

```bash
bash scripts/project.sh -m scripts.run_expansion silver --bronze-id a728cbc74ed5507307b398a5
bash scripts/project.sh -m scripts.run_expansion revision-demo --silver-id ef9c66b2a9d86511bcb8d3d5
```
