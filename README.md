# Painel de regras fiscais da União

Monitor do cumprimento das regras fiscais da União (Governo Central): meta de resultado
primário, limite de despesas do Regime Fiscal Sustentável, regra de ouro, despesa com pessoal,
garantias, dívida e mínimos de saúde e educação (R01–R17).

- Especificação: [`docs/especificacao_painel_regras_fiscais_uniao.md`](docs/especificacao_painel_regras_fiscais_uniao.md)
- Desenho do painel (telas, fluxo de dados, decisões, roadmap): [`docs/desenho_painel.md`](docs/desenho_painel.md)
- Catálogo de indicadores: [`docs/catalogo_indicadores.md`](docs/catalogo_indicadores.md)
- Parâmetros por exercício (metas, bandas, deduções, limites): [`config/parametros_regras_fiscais_uniao.yaml`](config/parametros_regras_fiscais_uniao.yaml)

## Uso

```bash
pip install -r requirements.txt

# painel de demonstração (dados FICTÍCIOS, com aviso na tela)
python -m painel_fiscal painel --exercicio 2026 --dados exemplos/dados_ilustrativos_2026.yaml

# coleta (grava bruto em dados/brutos/AAAA-MM-DD/ e acrescenta em dados/tratados/<ano>.json)
python -m painel_fiscal coletar-bcb --exercicio 2026 --desde 2025-01-01
python -m painel_fiscal coletar-siconfi --exercicio 2026 --demonstrativo rgf --periodo 2
python -m painel_fiscal coletar-siconfi --exercicio 2026 --demonstrativo rreo --periodo 4

# dados sem API (Relatório Bimestral, LOA, LDO): dados/entrada_manual/<ano>.yaml
# (mesmo formato de exemplos/dados_ilustrativos_2026.yaml, sem "ilustrativo: true")

# apuração no terminal e painel com os dados reais
python -m painel_fiscal apurar --exercicio 2026
python -m painel_fiscal painel --exercicio 2026      # → saida/painel_2026.html

python -m pytest
```

## Estrutura

```
config/            parâmetros das regras (YAML) e mapeamento SICONFI → indicadores
painel_fiscal/
  dados.py         observações versionadas (referência, coleta, fonte, realizado/projeção)
  coletores/       bcb_sgs, siconfi, ibge_sidra, stn_rtn
  apuracao/        status (semáforo) e regras R01–R17
  painel/          HTML estático com SVG inline (tema claro/escuro)
dados/             brutos/ (não versionado), tratados/, entrada_manual/
exemplos/          dados ilustrativos para demonstração e testes
tests/
```

## Antes de usar em produção

Itens marcados **⚠ verificar** no YAML e no painel ainda não foram confirmados na fonte
primária (códigos SGS, `id_ente` da União, mapeamento de contas do SICONFI, Res. Senado
48/2007, redação consolidada da LC 200/2023). Os parâmetros de 2027 vêm do PLDO e devem ser
atualizados após a sanção da LDO 2027. Ver `docs/desenho_painel.md`, seção 5.
