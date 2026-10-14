# Base de fundos para a Matriz de Indicadores

Pacote `fundos/`, separado do painel fiscal. Coleta as fontes públicas e grava em
`dados/fundos/` uma base no mesmo formato de campos da Matriz de Indicadores
(`r12`, `v12`, `dd12`, `ry`, `vy`, `dy`, `sh`, `pl`…), para substituir aos poucos a
exportação do Quantum Axis.

## Fluxo

```
config/fundos_universo.csv ──┐   (CNPJs: hoje os 387 fundos da Matriz)
                             ▼
CVM informe diário ── coletar-cvm ──► dados/fundos/cotas/AAAA.csv.gz
CVM registro_fundo_classe ── cadastro-cvm ──► dados/fundos/cadastro.json
BCB SGS 12 (CDI) ── coletar-cdi ──► dados/fundos/cdi.csv
CADPREV DAIR ── importar-cadprev / coletar-cadprev ──► dados/fundos/cadprev/
                             ▼
                        calcular ──► dados/fundos/metricas.json  ──► Matriz
```

## Fontes

| Fonte | Endereço | O que traz | Situação |
|---|---|---|---|
| CVM — informe diário | `dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_AAAAMM.zip` (anos antigos em `HIST/inf_diario_fi_AAAA.zip`) | cota, PL, captação, resgate e cotistas por dia | colunas pré e pós CVM 175 aceitas; ⚠ confirmar no diagnóstico até que ano há ZIP mensal |
| CVM — cadastro | `dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip` e `cad_fi.csv` | nome, situação, classificação ANBIMA, administrador, gestor, PL | ⚠ confirmar nomes de coluna |
| BCB — CDI | SGS 12 | CDI diário (% a.d.), vira índice acumulado | já usado pelo painel fiscal |
| CADPREV — DAIR | consulta pública / API (`config/fundos_fontes.yaml`) | carteira de cada RPPS por fundo: quantos RPPS têm o fundo, quanto somam, e a posição do próprio IGEPPS | ⚠ endereço da API não confirmado; importação de CSV já funciona |

## Como os indicadores são calculados

Em `fundos/metricas.py`. Retorno de janela pela cota de fechamento; volatilidade com o
desvio-padrão dos retornos diários × √252; drawdown pelo pior recuo frente ao pico
dentro da janela; Sharpe 12m sobre o CDI. Janela mais longa que o histórico do fundo
fica vazia, nunca parcial. Ano do retorno anual = dez/(A−1) a dez/A.

Diferenças esperadas frente ao Quantum: convenção de dias úteis, fundos com
subclasses (a base usa o informe da classe; sem ele, a subclasse com mais dias) e o
ano de início do fundo (o Quantum pode mostrar retorno parcial).

## Pendências

1. Rodar **Diagnóstico — fundos** no Actions e ajustar o que vier diferente.
2. CADPREV: confirmar o endereço da consulta do DAIR; preencher `cadprev.ente.cnpj`.
3. Carga inicial: **Coleta — fundos** com `desde = 2009-12`.
4. Taxas (administração + gestão + distribuição, CVM 175): fonte a definir (lâmina /
   regulamento); hoje só a que o cadastro trouxer.
5. Benchmarks além do CDI (IMA-B, IRF-M, Ibovespa…): fonte a definir (ANBIMA/B3).
6. Ligar `metricas.json` à Matriz (trocar o JSON embutido por esta base, por CNPJ).
