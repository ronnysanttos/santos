# Plano — IA Financeira Local & Busca na Web

**Cliente:** Rony Santos  
**Fonte:** [plano-projeto-ia-financeira.pdf](./plano-projeto-ia-financeira.pdf)  
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
| Coleta externa | Notícias, calendário, relatórios | DuckDuckGo / Tavily, Newspaper3k / BeautifulSoup |
| Cérebro local | Raciocínio, ferramentas, decisão JSON | Ollama (Qwen2.5 / Llama 3), LangChain ou Smolagents |
| Mercado | Indicadores, ordens, risco | Python `MetaTrader5`, guardrails de capital |
| Predição (evolução) | Sinal complementar ML | XGBoost (fase posterior) |

Fluxo alvo: **ativo → busca web → (opcional) MT5 → LLM → JSON (ação/confiança/justificativa) → guardrails → ordem ou aguardar**.

---

## Fases

### Fase 1 — Infraestrutura e LLM local *(MVP atual)*

- Ambiente Python, config via `.env`
- Cliente Ollama em `localhost:11434`
- Modelo recomendado: `qwen2.5:7b` (alternativa: `llama3.1:8b`)
- CLI de análise com saída JSON estruturada
- Fallback heurístico quando Ollama estiver offline (para demos/CI)

### Fase 2 — Engine de web-search & RAG *(MVP atual)*

- Tool `FinancialWebSearchTool` (DuckDuckGo)
- Queries direcionadas a notícias do ativo / macro (Copom, FED, etc.)
- Classificação de sentimento: Bullish (+1) / Bearish (−1) / Neutro (0) + confiança 0–100%
- Logs do raciocínio do agente

### Fase 3 — Integração preditiva + MT5

- Conectar `MetaTrader5` (Windows + terminal aberto; dry-run por padrão)
- Indicadores: RSI, médias, ATR
- Combinar sinal web + técnico
- Envio de ordens de teste em conta **demo**
- Reaproveitar padrões do scaffold EA já existente no repositório (`mt5_ea`), sem misturar escopos

### Fase 4 — Validação e simulação

- Conta demonstração
- Registro rigoroso de raciocínios (*logs*)
- Ajuste das travas de risco
- Critério de promoção a live: confiança estável + drawdown diário respeitado

---

## Decisões já tomadas (MVP)

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Linguagem | Python 3.10+ | Alinhado ao plano e ao pacote MT5 |
| Pacote | `ia_financeira` em `src/` | Separado do EA clássico; produto próprio |
| LLM | Ollama HTTP API | Plano diretor; sem API paga de modelo |
| Busca | `ddgs` (DuckDuckGo) | Gratuita; Tavily opcional depois |
| Orquestração | Agente ReAct simples (código próprio) | MVP rápido; LangChain/Smolagents na evolução |
| MT5 nesta entrega | Stub/mock de indicadores | Linux cloud sem terminal MT5; Fase 3 no Windows do Rony |
| Dry-run | Sempre ligado por padrão | Segurança de capital |
| Confiança mínima | 70% | Protocolo do PDF |
| Stop diário | R$ 300 (parametrizável) | Protocolo do PDF |
| Filtro de alto impacto | ±15 min de anúncios | Protocolo do PDF (calendário na Fase 2/3) |

---

## Próximos passos

1. **Rony:** instalar Ollama no Windows (`ollama.com`) e baixar `qwen2.5:7b`
2. **Rony:** `pip install -r requirements.txt` e copiar `.env.example` → `.env`
3. **Rony:** rodar `python -m ia_financeira analyze PETR4` com Ollama ativo
4. **Produto:** ligar MT5 real (Fase 3) em conta demo, ainda em dry-run
5. **Decisão pendente:** modelo padrão (7B vs 14B) conforme GPU/RAM disponível
6. **Decisão pendente:** DuckDuckGo gratuito vs Tavily (qualidade vs custo)
7. **Decisão pendente:** quando ativar trading real (após Fase 4)

---

## Fora de escopo nesta entrega

- Ordens reais em conta live
- XGBoost / ML preditivo
- UI gráfica
- RAG vetorial completo (embeddings + vector DB)
- Calendário econômico completo automatizado
