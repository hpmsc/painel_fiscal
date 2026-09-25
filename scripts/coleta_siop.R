#!/usr/bin/env Rscript
# coleta_siop.R — dotação e execução da despesa da União por Resultado Primário x GND,
# no endpoint de dados abertos do SIOP, via pacote orcamentoBR (MPO, CRAN). Sem credencial.
# Mesmo caminho do painel_fundos: só as funções públicas do pacote, nada de SPARQL à mão.
#
# Grava dados/siop/siop_rp_gnd_AAAA.csv (Orçamentos Fiscal e da Seguridade Social), com
# PLOA, LOA (dotação inicial), LOA + créditos, empenhado, liquidado e pago. Confere a soma
# contra o total do ano (consulta sem dimensões) para detectar resposta truncada.
#
# Uso: Rscript scripts/coleta_siop.R 2025 2026
# SIOP_IGNORAR_CERTIFICADO=1 repassa ignoreSecureCertificate=TRUE (paliativo se a cadeia
# de certificados embutida no pacote expirar).

invisible(Sys.setlocale("LC_CTYPE", "C.UTF-8"))
if (!exists("despesaDetalhada")) suppressPackageStartupMessages(library(orcamentoBR))

DIR <- "dados/siop"
IGNORA_CERT <- identical(Sys.getenv("SIOP_IGNORAR_CERTIFICADO"), "1")
TENTATIVAS <- 3
VALORES <- c("ploa", "loa", "loa_mais_credito", "empenhado", "liquidado", "pago")
COLUNAS <- c("exercicio", "rp_cod", "rp_desc", "gnd_cod", "gnd_desc", VALORES)
dir.create(DIR, recursive = TRUE, showWarnings = FALSE)
msg <- function(...) cat(format(Sys.time(), "%H:%M:%S"), ..., "\n")

com_tentativas <- function(rotulo, fn) {
  for (i in seq_len(TENTATIVAS)) {
    r <- tryCatch(fn(), error = function(e) e)
    if (!inherits(r, "error")) return(r)
    msg("  falha", i, "/", TENTATIVAS, "em", rotulo, ":", conditionMessage(r))
    Sys.sleep(5 * i)
  }
  NULL
}

padroniza <- function(df, ano) {
  mapa <- c(ResultadoPrimario_cod = "rp_cod", ResultadoPrimario_desc = "rp_desc",
            GND_cod = "gnd_cod", GND_desc = "gnd_desc")
  for (n in names(mapa)) if (n %in% names(df)) names(df)[names(df) == n] <- mapa[[n]]
  for (c in COLUNAS) if (!c %in% names(df)) df[[c]] <- NA
  df <- df[, COLUNAS]
  df$exercicio <- ano
  for (c in VALORES) df[[c]] <- round(as.numeric(df[[c]]), 2)
  df
}

coletar <- function(ano) {
  msg("Exercício", ano)
  d <- com_tentativas(paste("despesaDetalhada", ano), function()
    despesaDetalhada(exercicio = ano, ResultadoPrimario = TRUE, GND = TRUE,
                     ignoreSecureCertificate = IGNORA_CERT))
  total <- com_tentativas(paste("total", ano), function()
    despesaDetalhada(exercicio = ano, ignoreSecureCertificate = IGNORA_CERT))
  if (is.null(d) || nrow(d) == 0) { msg("  sem resposta do SIOP"); return(FALSE) }
  d <- padroniza(d, ano)
  soma <- sum(d$loa_mais_credito, na.rm = TRUE)
  ref <- if (is.null(total)) NA else sum(as.numeric(total$loa_mais_credito), na.rm = TRUE)
  if (!is.na(ref) && ref > 0 && abs(soma - ref) / ref > 0.001) {
    msg("  resposta incompleta: soma", soma, "vs total", ref, "— arquivo não gravado")
    return(FALSE)
  }
  arq <- file.path(DIR, sprintf("siop_rp_gnd_%d.csv", ano))
  tmp <- paste0(arq, ".tmp")
  for (c in names(d)) if (is.character(d[[c]])) d[[c]] <- enc2utf8(d[[c]])
  write.table(d, tmp, sep = ";", dec = ".", row.names = FALSE, na = "", quote = TRUE)
  file.rename(tmp, arq)
  msg("  gravado", arq, "(", nrow(d), "linhas; LOA+créditos R$",
      format(round(soma / 1e9, 1), big.mark = ".", decimal.mark = ","), "bi )")
  print(aggregate(cbind(loa, loa_mais_credito, empenhado) ~ rp_cod + rp_desc, data = d,
                  FUN = function(x) round(sum(x) / 1e9, 2)))
  TRUE
}

anos <- as.integer(commandArgs(trailingOnly = TRUE))
if (length(anos) == 0) anos <- as.integer(format(Sys.Date(), "%Y"))
ok <- vapply(anos, function(a) tryCatch(coletar(a), error = function(e) { msg("  erro:", conditionMessage(e)); FALSE }), logical(1))
quit(status = if (any(ok)) 0 else 1)
