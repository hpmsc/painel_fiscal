# Catálogo de indicadores

Chaves que a apuração (`painel_fiscal/apuracao/regras.py`) lê da base de observações.
Valores monetários em **R$ bilhões correntes**; razões e taxas como **fração** (0,05 = 5%);
dívida em **% do PIB** (ex.: 79,2). `tipo`: `realizado` (BCB, RTN, SICONFI) ou
`projecao` (LDO, PLOA/LOA, Relatório Bimestral).

| Indicador | Regra | Tipo usual | Fonte | Observação |
|---|---|---|---|---|
| `primario_gc_abaixo_linha_bi` | R01 | realizado (acum. no ano) / projecao | BCB SGS 4639; Relatório Bimestral | **Superávit positivo.** SGS 4639 é fluxo mensal em R$ milhões com déficit positivo: o coletor aplica `fator: -0.001` e acumula no ano |
| `primario_gc_acima_linha_bi` | R01 (referência) | realizado | STN RTN | Mostra a discrepância estatística |
| `deducoes_meta_total_bi` | R01 | projecao | Relatório Bimestral (carga manual) | Total deduzido informado pela fonte; quando presente, prevalece sobre a soma item a item do YAML |
| `bloqueio_limite_despesas_bi` | R02 (referência) | projecao | Relatório Bimestral (carga manual) | Bloqueio para cumprir o limite de despesas |
| `despesas_fundo_social_bi` | R01 (dedução 2026) | projecao/realizado | LOA; Relatório Bimestral | LC 223/2025 |
| `precatorios_bi` | R01 (dedução) | projecao/realizado | LOA; Relatório Bimestral | 2026: não deduzido até confirmar; 2027: deduz (1 − 39,4%) |
| `despesas_excepcionalizadas_bi` | R01 (dedução 2027) | projecao | PLDO/LOA | Limitado a R$ 65,66 bi |
| `despesa_sujeita_limite_bi` / `limite_despesa_bi` | R02 | projecao | Relatório Bimestral; LOA | Total do Regime Fiscal Sustentável |
| `despesa_sujeita_limite_{poder}_bi` / `limite_despesa_{poder}_bi` | R02 | projecao | Relatório Bimestral | poder ∈ executivo, legislativo, judiciario, mpu, dpu |
| `limite_despesa_anterior_bi`, `ipca_12m_jun` | R02 (cálculo alternativo) | realizado | LOA anterior; IBGE | Usados só se `limite_despesa_bi` faltar |
| `variacao_real_receita_primaria_12m_jun` | R03 | realizado | STN RTN + IPCA | 12 meses até junho do ano anterior |
| `meta_ano_anterior_cumprida` | R03 | realizado | apuração do ano anterior | booleano |
| `investimentos_loa_bi` | R05 | projecao | SIOP (orcamentoBR) | GND 4 das despesas primárias (RP em `fontes.siop.rp_primarias`), dotação da LOA |
| `pib_estimado_ploa_bi` | R05 | projecao | PLOA (carga manual) | |
| `fator_ipca_desde_jan2023` | R06 | realizado | IBGE | Fator acumulado (ex.: 1,17) |
| `contingenciamento_bi` | R07; R01 | projecao | Relatório Bimestral; decretos (carga manual) | Não está no SIOP. Na projeção do R01, é somado ao resultado ajustado (a limitação de empenho reduz a despesa) |
| `despesas_discricionarias_bi` | R07 | projecao | SIOP (orcamentoBR) | RP em `fontes.siop.rp_discricionarias`, dotação atualizada |
| `receitas_operacoes_credito_bi`, `despesas_capital_bi` | R08 | realizado | RREO Anexo 9 | |
| `creditos_maioria_absoluta_bi` | R08 (ressalva) | realizado | Leis de crédito | Créditos suplementares/especiais aprovados por maioria absoluta |
| `rcl_bi` | R09–R14, R16 | realizado | RGF Anexo 1 | |
| `dtp_total_bi` | R09 | realizado | RGF Anexo 1 | Se ausente, soma dos quatro Poderes |
| `dtp_{executivo,legislativo_incl_tcu,judiciario,mpu}_bi` | R10/R11 | realizado | RGF Anexo 1 por Poder | Soma dos blocos (instituição/rótulo) do Poder |
| `limite_dtp_{poder}_bi` | R10/R11 | realizado | RGF Anexo 1 por Poder | Soma dos limites oficiais dos blocos; respeita a repartição do art. 20 (inclusive os 3% do DF/ex-territórios). Sem ele, usa o % do YAML |
| `limite_garantias_senado_bi`, `limite_operacoes_credito_senado_bi` | R12/R13 | realizado | RGF Anexos 3 e 4 | Limites publicados (60% da RCL em 2025); conferência |
| `garantias_bi` | R12 | realizado | RGF Anexo 3 | |
| `operacoes_credito_rgf_bi` | R13 | realizado | RGF Anexo 4 | |
| `dcl_bi` | R14 | realizado | RGF Anexo 2 | |
| `dbgg_pct_pib`, `dlsp_pct_pib` | R15 | realizado (série mensal) | BCB SGS 13762 / 4513 | Confirmados |
| `trajetoria_ldo_dbgg_pct_pib` | R15 | projecao | Anexo de Metas Fiscais da LDO | Um ponto por fim de ano |
| `asps_bi` | R16 | realizado | RREO Anexo 12 | |
| `mde_bi`, `receita_liquida_impostos_bi` | R17 | realizado | RREO Anexo 8 | |
