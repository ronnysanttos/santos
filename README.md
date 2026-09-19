# Santos — IA Financeira Local & Busca na Web

Agente financeiro **local-first** para Rony Santos: **Ollama `qwen2.5:7b`**, busca **DuckDuckGo**, indicadores/execução **MetaTrader 5** (dry-run por padrão).

Docs: `docs/plano-ia-financeira.md` · `docs/project-context.md` · **`docs/setup-local.md`**

## Fluxo (Fases 1–3)

```
ticker → DuckDuckGo → MT5 RSI/MA/ATR (ou stub) → Ollama → JSON → guardrails → dry-run order
```

## Onde roda / atalho Windows

| Item | Caminho |
|------|---------|
| CLI | `python -m ia_financeira` |
| GUI | `python -m ia_financeira.gui` |
| Launcher | `scripts/launch_ia_financeira.bat` |
| Ícone | `assets/ia_financeira.ico` |
| Atalho Desktop | `powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1` |

Guia completo: [`docs/setup-local.md`](docs/setup-local.md).

## Instalação rápida (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install MetaTrader5
copy .env.example .env
ollama pull qwen2.5:7b
powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1
```

Abra o MT5 na **conta demo**, preencha credenciais no `.env`, mantenha `MT5_DRY_RUN=true`. Duplo clique em **IA Financeira** na Área de Trabalho.

## Uso

```powershell
.\scripts\launch_ia_financeira.bat
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
assets/ia_financeira.ico          # ícone do atalho Windows
scripts/launch_ia_financeira.bat  # duplo clique → GUI
scripts/install_desktop_shortcut.ps1
src/ia_financeira/
  gui.py                # interface tkinter
  agent/analyzer.py
  llm/ollama.py
  tools/web_search.py
  tools/market_data.py
  mt5/client.py | indicators.py | execution.py
  risk/guardrails.py
  cli.py
  assets/ia_financeira.ico
```

## Relação com `mt5_ea`

O scaffold Dual EMA (`mt5_ea` em outro branch) é um EA clássico separado. Este pacote é o agente IA + web do plano diretor; compartilha ideias de conexão/indicadores, sem misturar os motores.
