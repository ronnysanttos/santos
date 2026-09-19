# Santos — IA Financeira Local & Busca na Web

Agente financeiro **local-first** para Rony Santos: **Ollama `qwen2.5:7b`**, busca **DuckDuckGo**, indicadores/execução **MetaTrader 5** (dry-run por padrão).

Docs: `docs/plano-ia-financeira.md` · `docs/project-context.md` · **`docs/setup-local.md`**

## Fluxo (Fases 1–3)

```
ticker → DuckDuckGo → MT5 RSI/MA/ATR (ou stub) → Ollama → JSON → guardrails → dry-run order
```

## Instalação rápida (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install MetaTrader5
copy .env.example .env
ollama pull qwen2.5:7b
```

Abra o MT5 na **conta demo**, preencha credenciais no `.env`, mantenha `MT5_DRY_RUN=true`.

Guia completo: [`docs/setup-local.md`](docs/setup-local.md).

## Uso

```powershell
python -m ia_financeira health
python -m ia_financeira search PETR4 --pretty
python -m ia_financeira analyze PETR4 --pretty
pytest -q
```

## Segurança de ordens

| Flag | Default | Papel |
|------|---------|--------|
| `MT5_DRY_RUN` | `true` | Não envia ordens |
| `MT5_ALLOW_DEMO_ORDERS` | `false` | Trava extra; precisa `true` **e** dry-run `false` para demo |

Guardrails: confiança ≥ 70%, perda diária R$ 300, pausa alto impacto.

## Estrutura

```
src/ia_financeira/
  agent/analyzer.py
  llm/ollama.py
  tools/web_search.py
  tools/market_data.py
  mt5/client.py | indicators.py | execution.py
  risk/guardrails.py
  cli.py
```

## Relação com `mt5_ea`

O scaffold Dual EMA (`mt5_ea` em outro branch) é um EA clássico separado. Este pacote é o agente IA + web do plano diretor; compartilha ideias de conexão/indicadores, sem misturar os motores.
