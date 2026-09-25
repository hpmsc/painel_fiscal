# Desenho do painel de regras fiscais da União

Complementa a [especificação](especificacao_painel_regras_fiscais_uniao.md). Este documento
registra **como o painel foi pensado**: para quem é, quais perguntas responde, como as telas
se organizam, como o dado flui e quais decisões de apuração foram tomadas.

## 1. Para quem e para quê

Público: quem acompanha a política fiscal federal (analistas de orçamento, controle
externo, pesquisadores). O painel precisa responder em segundos:

1. **A União está cumprindo as regras fiscais neste exercício?** → semáforo.
2. **Onde está o risco?** → regras em alerta, prudencial ou descumprimento, com a folga.
3. **A meta primária vai ser cumprida?** → projeção oficial vs. banda, com as deduções explícitas.
4. **Quanto espaço resta no limite de despesas e no limite de pessoal?** → uso do limite por Poder.
5. **A dívida está na trajetória prevista na LDO?** → série vs. projeção.
6. **O que ainda é incerto?** → quadro de controvérsias e pendências.

Princípio: o painel **não esconde a incerteza normativa**. Onde o limite legal não está
confirmado, mostra o valor apurado com status "Limite a confirmar", sem inventar um veredito.

## 2. Estrutura da tela

```
┌──────────────────────────────────────────────────────────────────┐
│ Regras fiscais da União — exercício 2026                         │
│ escopo · fonte dos parâmetros (LDO/PLDO) · posição normativa     │
│ [aviso se houver dado ilustrativo]                               │
├──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│ ✕ n      │ !! n     │ ! n      │ ✓ n      │ · n                  │  resumo do semáforo
├──────────┴──────────┴──────────┴──────────┴──────────────────────┤
│ Semáforo: R01…R17 — apurado | limite/meta | folga | status |     │  tabela = visão
│           fonte · data de referência · data de coleta · notas    │  acessível de tudo
├───────────────────────────────┬──────────────────────────────────┤
│ R01 Meta primária             │ R02 Limite de despesas por Poder │
│ banda piso–teto, centro,      │ barras de uso do limite com      │
│ resultado ajustado, acumulado │ linhas 90% / 95% / 100%          │
│ + tabela de deduções          │                                  │
├───────────────────────────────┼──────────────────────────────────┤
│ R09–R11 Pessoal por Poder     │ R15 Dívida (% PIB)               │
│ uso do limite da LRF          │ DBGG e DLSP vs. projeção da LDO  │
├───────────────────────────────┴──────────────────────────────────┤
│ Controvérsias e pendências (⚠ verificar, PLDO, gatilhos…)        │
└──────────────────────────────────────────────────────────────────┘
```

Decisões visuais:

- **Status nunca só por cor**: cada status tem ícone e rótulo (✓ Cumpre, ! Alerta, !! Prudencial, ✕ Descumpre).
- Pessoal e limite de despesas são mostrados como **% do próprio limite** (1 = 100%), para
  que Poderes com limites diferentes (40,9% vs. 0,6% da RCL) fiquem comparáveis.
- A projeção da LDO aparece tracejada, continuação da série realizada.
- HTML único, estático, sem dependências externas: abre em qualquer navegador, pode ser
  publicado como página estática ou anexado a um relatório. Tema claro e escuro.

## 3. Fluxo de dados

```
 fontes                coletores/             dados/                   apuracao/        painel/
 ───────               ──────────             ──────                   ─────────        ───────
 BCB SGS ───────────▶ bcb_sgs.py    ─┐
 SICONFI RREO/RGF ──▶ siconfi.py    ─┤──▶ brutos/AAAA-MM-DD/<fonte>/   (JSON bruto + URL + parâmetros)
 IBGE SIDRA ────────▶ ibge_sidra.py ─┤──▶ tratados/<ano>.json ───┐
 STN RTN (CKAN) ────▶ stn_rtn.py    ─┘                           ├──▶ regras.py ──▶ render.py ──▶ saida/painel_<ano>.html
 Relatório Bimestral,                                            │      ▲
 LOA, LDO (PDF) ─────▶ carga manual ──▶ entrada_manual/<ano>.yaml┘      │
                                                config/parametros_regras_fiscais_uniao.yaml
```

- **Observação** é a unidade de dado: indicador, valor, data de referência, data de coleta,
  fonte, tipo (`realizado` | `projecao`). Nada é sobrescrito; a apuração usa a observação
  mais recente. Revisões do BCB e da STN ficam preservadas.
- Fontes sem API (Relatório Bimestral, LOA, LDO) entram por YAML manual no mesmo formato,
  sempre com a fonte citada.
- Parâmetros legais (metas, bandas, deduções, limites) vêm **só** do YAML de parâmetros.

## 4. Regras de apuração implementadas

| Situação | Tratamento |
|---|---|
| R01 com dado realizado de dezembro | Status oficial sobre o realizado (BCB, abaixo da linha) |
| R01 com exercício aberto e projeção do Relatório Bimestral | Status sobre a projeção, marcado "projeção" |
| R01 só com acumulado parcial | "Em apuração": acumulado não é comparável à meta anual |
| Deduções da meta | **Somadas** ao resultado (são despesas excluídas do cômputo). Percentual computado (2027: 39,4% dos precatórios) e teto (R$ 65,66 bi) vêm do YAML. Dedução com `tratamento_meta: null` **não** é aplicada e vira pendência |
| R02 sem `limite_despesa_bi` | Calcula: limite anterior × (1 + IPCA 12m jun) × (1 + crescimento real) |
| R02 por Poder | Status geral = pior entre total e Poderes |
| R03 | 70% (ou 50% se a meta anterior foi descumprida) da variação real da receita, entre 0,6% e 2,5%; alerta se divergir do valor oficial |
| R06 | Excesso sobre o teto da banda, limitado a R$ 25 bi × fator IPCA desde jan/2023; só dentro da vigência 2025–2028 |
| R08 | Operações de crédito − despesas de capital ≤ 0; créditos aprovados por maioria absoluta entram como ressalva |
| R11 | Pior status entre R09 e R10 (níveis de alerta 90% e prudencial 95% do YAML) |
| Limite `null` + `verificar: true` (R07, R13) | "Limite a confirmar": valor exibido, sem veredito |
| Sem limite legal (R14, R15) | "Monitoramento" |

> Nota: o YAML original descrevia R01 como `primário − deduções`. Como as deduções são
> despesas retiradas do cômputo da meta, o resultado ajustado **soma** essas despesas.
> O texto do YAML foi ajustado para refletir isso.

## 5. Roadmap

1. **Confirmar pendências (⚠)** — códigos SGS (primário do Governo Central, DBGG, DLSP),
   `id_ente` da União no SICONFI, mapeamento de contas em `config/mapeamento_siconfi.yaml`,
   percentuais da Res. Senado 48/2007, redação consolidada da LC 200/2023.
2. **Validar com 2025** (exercício fechado): coletar RGF 3º quadrimestre, RREO 6º bimestre e
   séries do BCB, e comparar o painel com os números publicados pela STN/BCB. Registrar como
   teste de regressão (`tests/test_2025.py`).
3. **Parser do RTN** (xlsx) para o primário acima da linha e a despesa sujeita ao limite.
4. **Extração semiautomática do Relatório Bimestral** (PDF → tabelas → YAML de entrada manual,
   com revisão humana).
5. **Agendamento** (GitHub Actions): coleta semanal, geração do HTML e publicação em GitHub Pages.
6. **Histórico por bimestre**: evolução da projeção da meta ao longo do ano (quanto cada
   relatório bimestral moveu o resultado) e comparação com benchmarks (IFI, Prisma Fiscal, Focus).
7. **Visão plurianual**: 2026 (LDO) e 2027 (PLDO) lado a lado, com as metas indicativas até 2030.
