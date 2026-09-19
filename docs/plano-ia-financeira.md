# Plano — IA Financeira Local & Busca na Web

**Cliente:** Rony Santos  
**Fonte:** [plano-projeto-ia-financeira.pdf](./plano-projeto-ia-financeira.pdf)  
**Setup:** [setup-local.md](./setup-local.md)  
**Produto:** Agente financeiro autônomo local (Ollama) + web search + execução via MetaTrader 5

---

## Objetivo

Construir um agente ReAct (Reason + Act) 100% no PC que:

1. Raciocina com LLM local (sem custo recorrente de API de modelo)
2. Consulta notícias e eventos macro na internet em tempo real
3. Combina sentimento/web com indicadores técnicos do MT5
4. Envia ordens ao MetaTrader 5 somente quando as travas de risco forem respeitadas

---

## Arquitetura (híbrida)

| Camada | Responsabilidade | Stack |
|--------|------------------|--------|
| Coleta externa | Notícias, calendário, relatórios | DuckDuckGo (`ddgs`); Tavily opcional depois |
| Cérebro local | Raciocínio, ferramentas, decisão JSON | Ollama **`qwen2.5:7b`** |
| Mercado | Indicadores, ordens, risco | Python `MetaTrader5`, guardrails de capital |
| Predição (evolução) | Sinal complementar ML | XGBoost (fase posterior) |

Fluxo: **ativo → busca web → MT5 (RSI/MA/ATR) → LLM → JSON → guardrails → dry-run order (ou demo se explícito)**.

---

## Decisões travadas (Rony)

| Decisão | Escolha |
|---------|---------|
| Modelo Ollama | **`qwen2.5:7b`** (não 14B) |
| Busca web | **DuckDuckGo via `ddgs`** |
| MT5 | Path real preparado; **dry-run default**; demo só com flags explícitas |
| Confiança mínima | 70% |
| Stop diário | R$ 300 |
| Alto impacto | ±15 min |

---

## Fases

### Fase 1 — Infraestrutura e LLM local ✅

- Ambiente Python, `.env`, cliente Ollama, CLI, fallback heurístico offline

### Fase 2 — Engine de web-search ✅

- Tool DuckDuckGo, sentimento + confiança no JSON do agente

### Fase 3 — Integração MT5 ✅ *preparada (dry-run)*

- Cliente `MetaTrader5` com fallback gracioso (Linux/CI → stub)
- Indicadores RSI / MA200 / ATR nas barras reais
- Wiring no agente junto com web search
- Path de ordem: log dry-run; envio demo só com `MT5_DRY_RUN=false` **e** `MT5_ALLOW_DEMO_ORDERS=true`
- Status: código pronto para o Windows do Rony; validação ao vivo pendente na máquina dele

### Fase 4 — Validação e simulação (próxima)

- Conta demo com logs rigorosos
- Ajuste de travas
- Critério para live: confiança estável + drawdown respeitado

---

## Próximos passos

1. Rony segue [setup-local.md](./setup-local.md) no Windows
2. Rodar vários `analyze` em dry-run com Ollama + MT5 demo abertos
3. Só então considerar flags de envio demo
4. Fase 4: calendário de alto impacto automatizado + auditoria de logs

---

## Fora de escopo agora

- Conta live / capital real
- XGBoost / UI / RAG vetorial completo
- Tavily (decidido: ficar em DuckDuckGo)
