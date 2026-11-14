# F11 — Entrega do laboratório e encerramento local

Data: 13/11/2026. Escopo: documentação, demonstração sintética real, reprodução
por instruções e pacote local. Sem avaliador externo, publicação, commit/tag,
push ou provisionamento AWS.

## F11.1 e F11.2 — Documentação

O README foi reescrito por problema, público, arquitetura, duas trilhas de
execução, resultados observados e limites. Removida a sequência acumulada de
promessas de fases já executadas. O diagrama distingue fluxo e supervisão;
a arquitetura explica ACID por tabela e publicação multitabular da aplicação.

ABT e indicadores continuam normatizados pelos contratos executáveis e pelo
dicionário existente. Nulos, cobertura, grão, aritmética e caráter retrospectivo
foram conferidos com `src/gold/model.py` e contratos. A operação continua usando
os registries próprios F08/F09 e um host/driver, sem transformar F07 em leitor S3.
O guia de estudo recebe a leitura aplicada da entrega. Links e caminhos foram
verificados no projeto e no pacote selecionado.

## F11.3 — Demonstração

Comandos, sequência e expectativas: `docs/entrega/DEMONSTRACAO.md`.
O script `scripts/demo_portfolio.py` usa fixtures inventadas e componentes reais
S3A/Delta/Silver/Gold/publicação. Registra CSVs consultados e quatro etapas:
carga/consulta, falha após commit privado, retomada/correção e leitura histórica.
`render_demo.py` lê os CSVs e confere hashes antes de gerar PNG/SVG.

A primeira tentativa foi recusada pelo guard de proveniência, pois o script
foi ajustado durante a execução; não é aceita como demonstração. O hook foi
corrigido para `after_commit:gold.abt:merge`, e a repetição usa fonte estável.
O log inicial permanece apenas como diagnóstico local. A implementação atual
registra status failed ao ocorrer exceção, em vez de deixar status running.

Resultado aprovado: `artifacts/f11/demo-approved/report.json`, **129,069 s**.
Quatro etapas passaram; três casos e dois meses. Correção 10→11 na anuidade e
5→6 na soma histórica. CURRENT preservado na falha; zero inserts/updates por novo
MERGE na retomada. Leitura histórica igual ao baseline e prefixo removido.
[Imagem da execução](../entrega/imagens/correcao_sintetica.png).

## F11.4 — Reprodução por instruções

Autorrevisão pelo executor, sem afirmar independência de avaliador. A fonte foi
exportada para `/tmp/credit-risk-f11-repro`, sem runtime, dados, credenciais ou
Git herdados. Os três bootstraps e comandos documentados são executados nessa
cópia. Variáveis herdadas Java/Python/AWS/Kaggle são removidas no processo.

A comparação exige os mesmos hashes dos seis CSVs; IDs, tempos e prefixos podem
variar. Não se compara duração como se fosse requisito de igualdade. A prova
RAW→S3 integral permanece a execução F10; a demo F11 parte de Silver tipada.

Resultado aprovado: **136,816 s** na reprodução; os **seis CSVs ficaram
idênticos por hash**. PNG e SVG também coincidiram. Fontes executadas da demo e
do renderer conferidas entre cópias. Registros: `artifacts/f11/validation/`
(`reproduction.json`, `reproduction.log`, `reproduced_demo/`,
`bootstrap_environment.log` e `reproduction_source_manifest.json`).
Na revisão do pacote, links relativos da página promovida a README precisaram
de ajuste; a versão final passou na verificação de links internos.

## F11.5 — Conclusão técnica e pacote

A nota `docs/entrega/CONCLUSAO_TECNICA.md` revisa os dez critérios finais do
roteiro e as versões observadas, ligando cada conclusão à sua prova. A CI remota
não foi executada e nenhuma ação de Git/publicação foi pressuposta.

`package_portfolio.py` exporta código sem outputs, inclui documentação selecionada
e somente CSV/figuras da demo inventada aprovada. Confere hashes, segredos locais
conhecidos, arquivos regulares e inventário dentro do tar. O pacote não inclui
dataset real, outputs históricos, logs, runtime ou credenciais. O README próprio
do pacote evita links para documentação real excluída. A preparação do pacote
não libera a redistribuição do dataset ou do working tree original.

Pacote aprovado: `artifacts/f11/credit-risk-portfolio-synthetic-final.tar.gz`,
**194 arquivos**, 359.790 bytes. SHA-256:
`64a4848021e1f7e32d56423e40066b42c366fd5f029fe4b6fee4fee954c9b97e`.
Auditoria: três valores de segredos locais conhecidos conferidos sem matches;
zero outputs no notebook exportado; inventário exato e hashes do tar aprovados.
`package.json` e `validation/package_review.json` registram a revisão.
A primeira versão do arquivo comprimido, com links relativos inconsistentes,
não é a entrega aceita. O working tree original continua fora desse pacote.

## F11.6 — Encerramento e evolução

Aprendizados, backlog e inventário de dependências AWS estão em
`docs/entrega/EVOLUCAO_E_AWS.md`. O inventário separa versões, responsabilidade
local e alterações a avaliar; nenhum serviço AWS foi contratado ou provisionado.
**F11.1–F11.6 aceitos; 72/72 itens e 12/12 fases concluídos no escopo local.**
Os checks finais compilaram 143 arquivos Python, validaram seis scripts shell,
18 YAMLs e o catálogo de 153 testes. A revisão verificou links de 133 documentos
Markdown e as 19 colunas do dicionário ABT contra o código. A regressão integral
continua sendo a F10, não uma nova execução alegada em F11.

A auditoria `artifacts/f11/protected_inputs_check.json` confirmou seis RAW,
recorte/Bronze, dois recibos F03, 90 arquivos Silver, 127 analíticos, dois bundles
F07 e CURRENT filesystem preservados; fingerprints F05/F06/F08 permanecem iguais.

Após preservar relatórios, logs e saídas, o serviço da reprodução foi confirmado
parado e a cópia descartável foi removida. Dados/runtime originais permanecem.
Registro: `artifacts/f11/validation/cleanup.json`. O aceite consolidado e hashes
das provas ficam em `artifacts/f11/acceptance.json`.
