# Catálogo de indicadores

Chaves que a apuração (`painel_fiscal/apuracao/regras.py`) lê da base de observações.
Valores monetários em **R$ bilhões correntes**; razões e taxas como **fração** (0,05 = 5%);
dívida em **% do PIB** (ex.: 79,2). `tipo`: `realizado` (BCB, RTN, SICONFI) ou
`projecao` (LDO, PLOA/LOA, Relatório Bimestral).

| Indicador | Regra | Tipo usual | Fonte | Observação |
|---|---|---|---|---|
| `primario_gc_abaixo_linha_bi` | R01 | realizado (acum. no ano) / projecao | BCB SGS; Relatório Bimestral | **Superávit positivo.** NFSP do BCB vem com déficit positivo: coletar com `fator=-1`. Código SGS a identificar |
| `primario_gc_acima_linha_bi` | R01 (referência) | realizado | STN RTN | Mostra a discrepância estatística |
| `despesas_fundo_social_bi` | R01 (dedução 2026) | projecao/realizado | LOA; Relatório Bimestral | LC 223/2025 |
| `precatorios_bi` | R01 (dedução) | projecao/realizado | LOA; Relatório Bimestral | 2026: não deduzido até confirmar; 2027: deduz (1 − 39,4%) |
| `despesas_excepcionalizadas_bi` | R01 (dedução 2027) | projecao | PLDO/LOA | Limitado a R$ 65,66 bi |
| `despesa_sujeita_limite_bi` / `limite_despesa_bi` | R02 | projecao | Relatório Bimestral; LOA | Total do Regime Fiscal Sustentável |
| `despesa_sujeita_limite_{poder}_bi` / `limite_despesa_{poder}_bi` | R02 | projecao | Relatório Bimestral | poder ∈ executivo, legislativo, judiciario, mpu, dpu |
| `limite_despesa_anterior_bi`, `ipca_12m_jun` | R02 (cálculo alternativo) | realizado | LOA anterior; IBGE | Usados só se `limite_despesa_bi` faltar |
| `variacao_real_receita_primaria_12m_jun` | R03 | realizado | STN RTN + IPCA | 12 meses até junho do ano anterior |
| `meta_ano_anterior_cumprida` | R03 | realizado | apuração do ano anterior | booleano |
| `investimentos_loa_bi`, `pib_estimado_ploa_bi` | R05 | projecao | LOA/SIOP; PLOA | |
| `fator_ipca_desde_jan2023` | R06 | realizado | IBGE | Fator acumulado (ex.: 1,17) |
| `contingenciamento_bi`, `despesas_discricionarias_bi` | R07 | projecao | Relatório Bimestral; decretos | |
| `receitas_operacoes_credito_bi`, `despesas_capital_bi` | R08 | realizado | RREO Anexo 9 | |
| `creditos_maioria_absoluta_bi` | R08 (ressalva) | realizado | Leis de crédito | Créditos suplementares/especiais aprovados por maioria absoluta |
| `rcl_bi` | R09–R14, R16 | realizado | RGF Anexo 1 | |
| `dtp_total_bi` | R09 | realizado | RGF Anexo 1 | |
| `dtp_{executivo,legislativo_incl_tcu,judiciario,mpu}_bi` | R10/R11 | realizado | RGF Anexo 1 por Poder | chave = nome do limite no YAML |
| `garantias_bi` | R12 | realizado | RGF Anexo 3 | |
| `operacoes_credito_rgf_bi` | R13 | realizado | RGF Anexo 4 | |
| `dcl_bi` | R14 | realizado | RGF Anexo 2 | |
| `dbgg_pct_pib`, `dlsp_pct_pib` | R15 | realizado (série mensal) | BCB SGS 13762 / 4513 (⚠) | |
| `trajetoria_ldo_dbgg_pct_pib` | R15 | projecao | Anexo de Metas Fiscais da LDO | Um ponto por fim de ano |
| `asps_bi` | R16 | realizado | RREO Anexo 12 | |
| `mde_bi`, `receita_liquida_impostos_bi` | R17 | realizado | RREO Anexo 8 | |
