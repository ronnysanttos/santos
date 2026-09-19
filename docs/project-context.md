# Contexto do Projeto — IA Financeira Local & Busca na Web

Documento durável de contexto. Fonte: [plano-projeto-ia-financeira.pdf](./plano-projeto-ia-financeira.pdf). Plano: [plano-ia-financeira.md](./plano-ia-financeira.md). Setup: [setup-local.md](./setup-local.md).

---

## Metas

- Agente financeiro **local-first**: LLM via Ollama no PC.
- **Web search** em tempo real (notícias / macro).
- Padrão **ReAct**: ferramentas (busca, MT5) → decisão JSON.
- **MetaTrader 5** para indicadores e execução (demo primeiro, dry-run default).
- **Proteção de capital**: confiança ≥ 70%, stop diário R$ 300, filtro alto impacto.

## Decisões travadas (não reabrir sem Rony)

| Item | Valor |
|------|--------|
| Modelo | `qwen2.5:7b` |
| Busca | DuckDuckGo (`ddgs`) |
| MT5 ordens | Dry-run por padrão; demo só com `MT5_DRY_RUN=false` + `MT5_ALLOW_DEMO_ORDERS=true` |
| Fase 3 | Código de integração pronto; validação no Windows do Rony |

## Constraints

| Constraint | Detalhe |
|------------|---------|
| SO do MT5 | Pacote oficial Windows-first |
| Linux/CI | Stub de indicadores + dry-run |
| Live trading | Fora de escopo até Fase 4 |
| Idioma docs | Português |

## Stack

- Python 3.10+, Ollama `qwen2.5:7b`, `ddgs`, `requests`, `python-dotenv`
- Opcional Windows: `MetaTrader5`
- Pacote: `src/ia_financeira` (`mt5/`, `agent/`, `tools/`, `risk/`, `llm/`)

## Onde roda

- CLI: `python -m ia_financeira`
- GUI: `python -m ia_financeira.gui` · launcher `scripts/launch_ia_financeira.bat`
- Ícone/atalho: `assets/ia_financeira.ico` · `scripts/install_desktop_shortcut.ps1`

```powershell
python -m ia_financeira health
python -m ia_financeira analyze PETR4 --pretty
powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1
pytest -q
```

## Preferências

- Temperatura LLM ~0.2
- Saída: `acao`, `confianca`, `sentimento`, `justificativa` + bloco `order`
- Nunca enviar ordem se guardrails falharem ou se dry-run estiver ativo
