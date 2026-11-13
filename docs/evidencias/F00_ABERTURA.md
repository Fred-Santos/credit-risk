# Evidência — abertura de F00

Data: 12/11/2026. Escopo: F00.1, investigação F00.2 e registro F00.6.
Inspeção de ambiente complementar a F01.1, ainda não aceita como inventário da
máquina final do usuário. Sem execução da pipeline e sem `run_id` de dados.

## Referência do código e estado

Commit base inspecionado: `03f21ced74dc272cce7725e54b384b03a454aafe`.
Havia alterações locais em Bronze/qualidade/testes e documentação. Foram
preservadas. O commit base não representa sozinho o conteúdo modificado localmente.

Documentos produzidos:

- [Escopo do produto](../ESCOPO_PRODUTO.md): público, perguntas, entregas e limites.
- [Avaliação da fonte](../governance/SOURCE.md): evidência externa, alternativas e pendências.
- [Decisões](../DECISOES.md): direção aprovada e dependências em aberto.

## Inspeção reproduzível do ambiente da sessão

Na raiz do repositório:

```bash
git rev-parse HEAD
git status --short
python3 --version
command -v python3 java docker kaggle
df -h .
free -h
```

Se `command -v` não localizar um executável, sua saída pode ser vazia e o retorno
indicar ausência. Isso não significa que o pacote não exista em outro ambiente.
Os módulos Python também foram examinados com `importlib.util.find_spec`.

| Item | Observado nesta sessão |
|---|---|
| Sistema | Ubuntu 26.04.1 LTS em kernel Linux WSL2 |
| Python | 3.14.4, `/usr/bin/python3` |
| RAM visível ao sistema | 16.214.664 kB em `/proc/meminfo`, aproximadamente 15,46 GiB |
| Disco livre do filesystem do projeto | Aproximadamente 949,81 GiB na inspeção |
| `java`, `docker`, `kaggle` | Não encontrados no PATH |
| Módulos `pyspark`, `delta`, `pandas`, `pyarrow`, `xlrd` | Não encontrados no Python inspecionado |
| Módulo `yaml` | Encontrado |
| Pasta `data/` | Ausente |

Não foram instalados pacotes nem acessadas credenciais. Os números de RAM/disco
são do ambiente visível à sessão e não substituem o orçamento informado pelo
usuário para o computador final. Python disponível não implica compatibilidade
já validada com a versão Spark/Delta que será escolhida.

## Validações documentais

| Verificação | Esperado | Obtido |
|---|---|---|
| Escopo com público, perguntas e limites | Produto definido sem inventar resultados | Registrado; perguntas ligadas aos campos históricos e a cenários de engenharia |
| Fonte com condições adequadas | Regra verificável para o escopo | Restrição localizada; escolha de fonte permanece pendente em SOURCE |
| Decisões de trabalho | Diferenciar aprovação, proposta e validação | Registro criado; versões, campos e serviço de objetos continuam pendentes |
| Inspeção de dados | Não afirmar medidas novas sem arquivos | Não executada; documentação histórica identificada como histórica |

Os termos foram examinados por busca da página oficial; o procedimento e
localizadores estão em SOURCE. Arquivos de dados não foram baixados. Nenhum teste
da pipeline foi executado nesta sessão porque a entrega foi documental; os
resultados de testes de sessões anteriores não foram apresentados como novos.

## Continuidade

F00.1 e F00.6 atendem aos critérios documentais. F00.2 continua em andamento e
F00.3–F00.5 aguardam fonte e ambiente. F01.1 tem levantamento parcial; confirmar
qual é o computador de execução final ao preparar o ambiente.

O usuário escolheu expressamente manter Home Credit pendente de autorização
específica. Foi preparado rascunho de solicitação, sem envio. Não houve troca
de dataset nem contato externo; ambiente e testes sintéticos podem avançar.
