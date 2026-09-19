# Contexto do Projeto — IA Financeira Local & Busca na Web

Documento durável de contexto para agentes e para Rony Santos. Fonte canônica do plano: [plano-projeto-ia-financeira.pdf](./plano-projeto-ia-financeira.pdf). Plano operacional: [plano-ia-financeira.md](./plano-ia-financeira.md).

---

## Metas

- Agente financeiro **local-first**: LLM via Ollama no PC, sem dependência obrigatória de API de modelo paga.
- Capacidade de **web search** em tempo real (notícias, macro, resultados corporativos).
- Padrão **ReAct**: raciocinar em etapas, chamar ferramentas (busca, MT5), decidir em JSON.
- Integração futura com **MetaTrader 5** para indicadores e execução (conta demo primeiro).
- **Proteção de capital** obrigatória (confiança mínima, stop diário, filtro de notícias de alto impacto).

## Não-metas (por enquanto)

- Substituição completa de um EA clássico de médias móveis (existe scaffold separado `mt5_ea` no repo).
- Trading live sem validação em demo.
- Dependência exclusiva de APIs cloud de LLM (OpenAI etc.) — opcional só como fallback explícito, não como default.

## Constraints

| Constraint | Detalhe |
|------------|---------|
| Privacidade / custo | Preferir execução no hardware do Rony |
| SO do MT5 | Pacote oficial `MetaTrader5` é Windows-first |
| Risco | Dry-run default; ordens só com confiança > 70% |
| Drawdown | Suspender operações após perda diária parametrizada (default R$ 300) |
| Alto impacto | Pausar ±15 min em eventos (Payroll, FOMC, Copom) |
| Idioma docs | Português para documentação voltada ao usuário |
| Repo | `github.com/ronnysanttos/santos` — produto em `src/ia_financeira` |

## Stack decidida (MVP)

- **Python 3.10+**
- **Ollama** — `http://localhost:11434` — modelo default `qwen2.5:7b`
- **ddgs** — busca gratuita (DuckDuckGo)
- **requests** — cliente HTTP Ollama
- **python-dotenv** — configuração
- **pytest** — testes unitários sem Ollama/MT5 obrigatórios
- Evolução: LangChain/Smolagents, Newspaper3k, Tavily, XGBoost, `MetaTrader5`

## Pacote no repositório

```
src/ia_financeira/
  config.py          # env / guardrails
  llm/ollama.py      # cliente generate
  tools/web_search.py
  tools/market_data.py  # stub MT5 / indicadores mock
  agent/analyzer.py  # vertical slice: busca → contexto → decisão
  risk/guardrails.py
  cli.py / __main__.py
```

## Comandos úteis

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m ia_financeira analyze PETR4
python -m ia_financeira search PETR4
pytest -q
```

## Preferências do produto

- Temperatura baixa do LLM (~0.2) para decisões mais estáveis.
- Saída sempre estruturada: `acao` ∈ {COMPRA, VENDA, AGUARDAR}, `confianca` 0–100, `justificativa`, `sentimento`.
- Logs legíveis do raciocínio (auditoria Fase 4).
- Nunca enviar ordem se guardrails falharem.
