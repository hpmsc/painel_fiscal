# Painel de Regras Fiscais da União — Especificação e Tabela de Parâmetros

> Documento de entrada para o Claude Code. Escopo: **somente União (Governo Central / Orçamentos Fiscal e da Seguridade Social)**.
> Posição normativa de referência: setembro/2026. Itens marcados com **⚠ verificar** devem ser confirmados na fonte primária antes de entrar em produção.
> Arquivo de configuração complementar: `parametros_regras_fiscais_uniao.yaml` (mesmo conteúdo, formato legível por máquina).

---

## 1. Objetivo do painel

Acompanhar, para cada exercício, o cumprimento das regras fiscais da União, mostrando para cada regra:
valor apurado, limite/meta, folga ou excesso, status (cumpre / alerta / descumpre), base legal, fonte e data da extração.

---

## 2. Tabela de regras (visão consolidada)

| ID | Regra | Base legal | Indicador / fórmula | Limite / meta | Fonte principal | Frequência |
|---|---|---|---|---|---|---|
| R01 | Meta de resultado primário | LRF art. 4º, §1º; LC 200/2023 art. 2º; LDO do exercício | Primário do Governo Central (critério BCB, abaixo da linha) − deduções autorizadas | Centro da meta na LDO, banda ±0,25 p.p. do PIB | BCB (NFSP) + STN (RTN) | Mensal |
| R02 | Limite de despesas primárias (Regime Fiscal Sustentável) | LC 200/2023 arts. 3º a 5º; EC 136/2025; LC 223/2025 | Despesa primária sujeita ao limite ÷ limite, por Poder/órgão | Limite do ano anterior × IPCA (12m até jun) × (1 + crescimento real entre 0,6% e 2,5%) | Relatório Bimestral de Avaliação (MPO/MF); LOA | Bimestral |
| R03 | Regra de crescimento real do limite | LC 200/2023 art. 5º | Crescimento real = 70% da variação real da receita primária (12m até jun do ano anterior); 50% se a meta do ano anterior foi descumprida | Piso 0,6% / teto 2,5% real | STN (RTN) + IBGE (IPCA) | Anual |
| R04 | Gatilhos por descumprimento / déficit | LC 200/2023 art. 6º-A; LDO/PLDO | Status booleano de cada vedação | Ativado se déficit primário apurado (2025 → efeitos em 2027, conforme PLDO 2027) | LDO/PLDO; RTN | Anual |
| R05 | Piso de investimentos | LC 200/2023 art. 10 ⚠ verificar | Dotação de investimentos na LOA ÷ PIB estimado no PLOA | ≥ 0,6% do PIB | LOA/SIOP | Anual |
| R06 | Uso de excesso de primário em investimentos | LC 200/2023 ⚠ verificar redação vigente | Excesso acima do teto da banda | Até o excesso, limitado a R$ 25 bi corrigidos (2025–2028) | RTN; LOA seguinte | Anual |
| R07 | Limitação de empenho (contingenciamento) | LRF art. 9º; LC 200/2023 ⚠ verificar teto | Contingenciamento ÷ despesas discricionárias | Observa o piso da banda (LDO 2026); teto de contingenciamento ⚠ verificar | Relatório Bimestral; decretos de programação | Bimestral |
| R08 | Regra de ouro | CF art. 167, III; LRF art. 12, §2º | Receitas de operações de crédito − despesas de capital | Operações de crédito ≤ despesas de capital (salvo créditos aprovados por maioria absoluta) | RREO Anexo 9 (SICONFI); RTN | Bimestral |
| R09 | Despesa com pessoal — total | LRF arts. 19, I, e 20, I | Despesa total com pessoal ÷ RCL | 50% da RCL | RGF Anexo 1 (SICONFI) | Quadrimestral |
| R10 | Despesa com pessoal — por Poder | LRF art. 20, I | DTP do Poder ÷ RCL | Executivo 40,9%; Legislativo (incl. TCU) 2,5%; Judiciário 6%; MPU 0,6% | RGF Anexo 1 por Poder | Quadrimestral |
| R11 | Níveis de alerta e prudencial (pessoal) | LRF art. 59, §1º, II; art. 22, parágrafo único | % do limite de R09/R10 | Alerta 90%; prudencial 95% do limite | Derivado de R09/R10 | Quadrimestral |
| R12 | Garantias concedidas pela União | Res. Senado 48/2007 ⚠ verificar artigo e % | Saldo de garantias ÷ RCL | ⚠ verificar (referência usual: 60% da RCL) | RGF Anexo 3 (SICONFI) | Quadrimestral |
| R13 | Operações de crédito da União | Res. Senado 48/2007 ⚠ verificar | Operações de crédito ÷ RCL | ⚠ verificar | RGF Anexo 4 (SICONFI) | Quadrimestral |
| R14 | Dívida consolidada da União | LRF art. 30 (limite da União nunca aprovado pelo Senado) | DCL ÷ RCL | **Sem limite vigente** — só monitoramento | RGF Anexo 2 (SICONFI) | Quadrimestral |
| R15 | Trajetória da dívida | LC 200/2023 art. 1º; Anexo de Metas Fiscais da LDO | DBGG e DLSP em % do PIB vs. projeção da LDO | Sem limite legal — comparar com a trajetória projetada | BCB (SGS) | Mensal |
| R16 | Mínimo em saúde | CF art. 198, §2º, I (EC 86/2015) | ASPS ÷ RCL | ≥ 15% da RCL | RREO Anexo 12 (SICONFI) | Bimestral |
| R17 | Mínimo em educação (MDE) | CF art. 212 | MDE ÷ receita líquida de impostos | ≥ 18% | RREO Anexo 8 (SICONFI) | Bimestral |

---

## 3. Parâmetros por exercício (tabela editável — NÃO fixar no código)

| Parâmetro | 2026 (LDO 2026 — Lei sancionada) | 2027 (PLDO 2027 — em tramitação) | Observação |
|---|---|---|---|
| Meta primária — centro | R$ 34,3 bi (0,25% do PIB) | R$ 73,2 bi (0,50% do PIB) | PLDO 2027 ainda sujeito a alteração no Congresso |
| Banda de tolerância | ±0,25 p.p. → cumpre entre R$ 0 e R$ 68,5 bi | ±0,25 p.p. → R$ 36,61 bi | |
| Piso da banda usado para contingenciamento | Sim (LDO 2026 autoriza mirar o limite inferior) | ⚠ verificar | |
| Deduções da meta — precatórios | Excluídos do limite de despesas (EC 136/2025); tratamento na meta ⚠ verificar | Entra na meta 39,4% das despesas com precatórios/RPV | |
| Deduções da meta — outras | Saúde/educação temporárias com recursos do Fundo Social (LC 223/2025) | Compensação de até R$ 65,66 bi em despesas excepcionalizadas | Listar item a item a partir do texto da LDO |
| Gatilhos art. 6º-A ativos | ⚠ controvérsia (TCU/consultorias: já em 2026; governo: 2027) | Sim — p. ex. vedação a benefício tributário | Registrar como "controvérsia" no painel |
| Crescimento real do limite de despesa | ⚠ extrair do PLOA/LOA 2026 | ⚠ extrair do PLOA 2027 | Entre 0,6% e 2,5% |
| IPCA de correção do limite | IPCA 12m até jun/2025 | IPCA 12m até jun/2026 | IBGE |
| Metas indicativas seguintes | — | 2028: ⚠; 2029: ⚠; 2030: 1,50% do PIB (R$ 272,2 bi) | Anexo de Metas Fiscais |

---

## 4. Fontes de dados e acesso

| Fonte | Conteúdo | Acesso | Observação para implementação |
|---|---|---|---|
| **BCB — SGS** | Primário do Governo Central (abaixo da linha), NFSP, DBGG, DLSP, PIB acumulado 12m | API REST: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa` | Códigos de referência: DBGG % PIB = 13762; DLSP % PIB = 4513 (⚠ confirmar). Código do primário do Governo Central: ⚠ identificar no catálogo SGS |
| **STN — Resultado do Tesouro Nacional (RTN)** | Receitas, despesas, primário acima da linha, despesa sujeita ao limite | Tesouro Transparente (CKAN): `https://www.tesourotransparente.gov.br/ckan/api/3/action/package_search?q=resultado+do+tesouro+nacional` | Planilha da série histórica (xlsx); fazer parser com a versão/data de publicação |
| **SICONFI (STN)** | RREO e RGF da União (RCL, pessoal, regra de ouro, dívida, garantias, saúde, educação) | API: `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo` e `/tt/rgf` (parâmetros `an_exercicio`, `nr_periodo`, `co_tipo_demonstrativo`, `no_anexo`, `id_ente`, `co_poder`) | `id_ente` da União ⚠ confirmar (usualmente `1`). Paginação via `offset` |
| **Relatório Bimestral de Avaliação de Receitas e Despesas Primárias** (MPO/MF) | Limite de despesas por Poder, espaço fiscal, contingenciamento, projeção do primário | PDF em gov.br/planejamento e gov.br/fazenda | Sem API: coleta semiautomática (download + extração de tabelas) ou carga manual |
| **SIOP / Painel do Orçamento Federal** | Dotação e execução da LOA (investimentos, discricionárias) | Painel público; webservice exige credencial | Usar o painel/exportação pública; webservice só se houver acesso |
| **Portal da Transparência (CGU)** | Execução da despesa | API com chave gratuita | Complementar |
| **IBGE — SIDRA** | IPCA; PIB nominal | API: `https://apisidra.ibge.gov.br/values/t/{tabela}/...` | IPCA: tabela 1737; PIB corrente trimestral: tabela 1846 (⚠ confirmar variáveis) |
| **Textos legais** | LDO, LOA, LC 200, LRF, EC 136, LC 223 | planalto.gov.br; congressonacional.leg.br (LDO/LOA) | Alimentam manualmente a tabela de parâmetros (seção 3) |
| **Benchmarks** | Projeções independentes | IFI/Senado (RAF); Prisma Fiscal (MF); Focus (BCB) | Camada opcional de "expectativa de mercado" |

---

## 5. Regras de apuração (para o código respeitar)

1. **Meta primária**: o cumprimento oficial usa o critério **abaixo da linha do BCB**. O RTN (acima da linha) aparece como referência, mostrando a discrepância estatística.
2. **Deduções e exceções são parâmetros anuais** (seção 3), nunca constantes no código. Cada dedução precisa de valor, base legal e fonte.
3. **Status**:
   - Meta: `cumpre` se `resultado_ajustado ≥ limite_inferior_banda`; destacar se acima do teto da banda (aciona R06).
   - Limites percentuais (pessoal etc.): `ok` < 90% do limite; `alerta` ≥ 90%; `prudencial` ≥ 95%; `excedido` ≥ 100%.
   - Regras sem limite legal (R14, R15): apenas `monitoramento`.
4. **Versionamento**: guardar cada extração com data de coleta e data de referência, porque BCB e STN revisam séries.
5. **Controvérsias**: campo de texto por regra/exercício (ex.: vigência dos gatilhos do art. 6º-A em 2026).
6. **Projeção vs. realizado**: separar valores da LDO/relatório bimestral (projeção) dos valores apurados (BCB/RTN/RGF).

---

## 6. Sugestão de arquitetura para o Claude Code

- `config/parametros_regras_fiscais_uniao.yaml` — regras + parâmetros por exercício (este pacote).
- `coletores/` — um módulo por fonte (bcb_sgs, stn_rtn, siconfi, ibge_sidra, relatorio_bimestral).
- `dados/brutos/AAAA-MM-DD/` e `dados/tratados/` — extrações versionadas.
- `apuracao/` — cálculo de cada regra (R01…R17) a partir dos tratados + parâmetros.
- `painel/` — dashboard com: visão geral (semáforo por regra), meta primária (realizado 12m vs. banda), limite de despesas por Poder, pessoal por Poder vs. alerta/prudencial, dívida vs. trajetória da LDO, e um quadro de controvérsias/itens pendentes.
- Testes: validar cada fórmula com um exercício já fechado (ex.: 2025) contra os números publicados pela STN/BCB.

---

## 7. Pendências antes de produção (⚠)

- Confirmar os códigos SGS (primário do Governo Central, DBGG, DLSP) e o `id_ente` da União no SICONFI.
- Confirmar os artigos e percentuais da Res. Senado 48/2007 (garantias e operações de crédito).
- Confirmar a redação consolidada da LC 200/2023 após a LC 223/2025 e a EC 136/2025: lista de exceções do limite, piso de investimento, teto de contingenciamento e uso do excesso de primário.
- Extrair do texto da LDO 2026 e do PLDO 2027 a lista exata de deduções da meta.
- Atualizar a seção 3 quando a LDO 2027 for sancionada.
