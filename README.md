# Santos — IA Financeira Local & Busca na Web

Agente financeiro **local-first** para Rony Santos: LLM via [Ollama](https://ollama.com), busca de notícias (DuckDuckGo), guardrails de risco e preparação para MetaTrader 5.

Plano e contexto (Project Context):

- `docs/plano-ia-financeira.md`
- `docs/project-context.md`
- Fonte PDF: `docs/plano-projeto-ia-financeira.pdf`

## O que este MVP faz (Fases 1–2)

```
ticker → busca web → snapshot de mercado (stub) → Ollama (ou fallback) → JSON → guardrails
```

Saída estruturada: `acao` (COMPRA/VENDA/AGUARDAR), `confianca`, `sentimento`, `justificativa`, com trava de confiança mínima (70%) e dry-run.

## Requisitos

- Python 3.10+
- Ollama no PC (recomendado: `qwen2.5:7b`)
- Conta **demo** MT5 apenas na Fase 3 (Windows)

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# ou: pip install -e .
cp .env.example .env
```

Baixe o modelo:

```bash
ollama run qwen2.5:7b
```

## Uso

```bash
# Saúde do ambiente
python -m ia_financeira health

# Só busca de notícias
python -m ia_financeira search PETR4 --pretty

# Vertical slice completo
python -m ia_financeira analyze PETR4 --pretty
```

Com `OLLAMA_ALLOW_FALLBACK=true` (default), o agente ainda roda sem Ollama usando uma heurística determinística — útil para CI/demo. Em produção local, prefira Ollama ativo.

## Testes

```bash
pytest -q
```

## Estrutura

```
src/ia_financeira/
  agent/analyzer.py     # ReAct slice
  llm/ollama.py         # cliente + fallback
  tools/web_search.py   # DuckDuckGo
  tools/market_data.py  # stub (MT5 na Fase 3)
  risk/guardrails.py    # confiança / loss diário / alto impacto
  cli.py
```

## Segurança

- Dry-run ligado por padrão (`MT5_DRY_RUN=true`)
- Ordens (futuras) só com confiança ≥ `MIN_CONFIDENCE`
- Limite de perda diária: `DAILY_LOSS_LIMIT_BRL`
- Janela de pausa em notícias de alto impacto (flag + calendário na evolução)

**Nunca** use conta live antes da Fase 4 (validação em demo).

## Relação com o scaffold MT5 EA

Há um branch/scaffold `mt5_ea` (Dual EMA) no repositório. Este pacote `ia_financeira` é o produto do plano diretor de IA + web; a integração MT5 real entra na Fase 3 sem misturar os dois motores prematuramente.
