# Setup local — IA Financeira (Windows + Ollama + MT5 demo)

Guia curto para Rony Santos. Decisões travadas: **Ollama `qwen2.5:7b`**, busca **DuckDuckGo (`ddgs`)**, MT5 com **dry-run por padrão**.

---

## 1. Pré-requisitos

| Item | Detalhe |
|------|---------|
| SO | Windows 10/11 (MT5 oficial) |
| Python | 3.10+ |
| Ollama | [ollama.com](https://ollama.com) |
| MetaTrader 5 | Terminal da corretora + **conta DEMO** |
| Repo | clone de `ronnysanttos/santos`, branch do PR |

---

## 2. Ollama (`qwen2.5:7b`)

```powershell
# Após instalar o Ollama
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

Deixe o serviço Ollama rodando. API esperada: `http://localhost:11434`.

---

## 3. Python + projeto

```powershell
cd santos
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install MetaTrader5
copy .env.example .env
```

Edite `.env`:

- `OLLAMA_MODEL=qwen2.5:7b` (já default)
- `WEB_SEARCH_BACKEND=duckduckgo` (já default)
- `MARKET_DATA_MODE=auto` (tenta MT5; se falhar, usa stub)
- `MT5_DRY_RUN=true`
- `MT5_ALLOW_DEMO_ORDERS=false`
- Preencha `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` (conta **demo**)
- Opcional: `MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe`

---

## 4. MetaTrader 5 (demo)

1. Abra o terminal MT5 e faça login na **conta demonstração**.
2. Confirme o símbolo no Market Watch (ex.: `PETR4`, `WIN$`, `EURUSD` — use o nome exato do broker).
3. Em **Ferramentas → Opções → Expert Advisors**, permita trading automatizado **só** quando for testar envio real (ainda não necessário em dry-run).
4. Mantenha o terminal aberto enquanto roda o agente.

---

## 5. Comandos do dia a dia

```powershell
# Saúde: Ollama + MT5
python -m ia_financeira health

# Só notícias (DuckDuckGo)
python -m ia_financeira search PETR4 --pretty

# Fluxo completo: web + indicadores + LLM + guardrails + dry-run order
python -m ia_financeira analyze PETR4 --pretty
```

Em dry-run, a saída JSON inclui `order.status = "dry_run"` e o log da ordem **pretendida** (lado, volume, SL/TP) — nada é enviado ao MT5.

---

## 6. Dry-run vs envio em demo

| Modo | `.env` | Comportamento |
|------|--------|----------------|
| **Dry-run (default)** | `MT5_DRY_RUN=true` | Só registra intenção de ordem |
| **Demo send** | `MT5_DRY_RUN=false` **e** `MT5_ALLOW_DEMO_ORDERS=true` | Envia ordem a mercado na conta logada |
| Bloqueado | Qualquer outro combo | Continua dry-run |

Guardrails sempre ativos: confiança ≥ 70%, stop diário R$ 300, pausa em alto impacto.

**Nunca** use conta live nesta fase. Só demo, e só após revisar vários dry-runs.

---

## 7. Linux / CI

Sem terminal MT5: o agente usa stub de indicadores e dry-run. Testes:

```bash
pip install -r requirements.txt
pytest -q
```

---

## 8. Problemas comuns

| Sintoma | Ação |
|---------|------|
| `ollama_available: false` | Subir Ollama; `ollama pull qwen2.5:7b` |
| `MetaTrader5 package unavailable` | `pip install MetaTrader5` no Windows |
| Falha ao conectar MT5 | Terminal aberto + login demo + credenciais no `.env` |
| Símbolo não encontrado | Nome exato do broker no Market Watch |
| Ordem não sai | Confirme os **dois** flags de demo; confira `guardrails.allowed` |
