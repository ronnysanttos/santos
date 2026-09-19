"""Double-click friendly GUI for IA Financeira (tkinter)."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from ia_financeira.assets.paths import icon_path as _icon_path
from ia_financeira import __version__
from ia_financeira.agent.analyzer import FinancialAnalyzer
from ia_financeira.config import settings
from ia_financeira.llm.ollama import OllamaClient
from ia_financeira.mt5.client import probe_mt5
from ia_financeira.tools.web_search import FinancialWebSearchTool


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"IA Financeira Local  ·  v{__version__}")
        self.geometry("820x640")
        self.minsize(640, 480)
        self.configure(bg="#0B3D3A")

        icon = _icon_path()
        if icon is not None:
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = tk.Frame(self, bg="#0B3D3A")
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(
            header,
            text="IA Financeira",
            font=("Segoe UI", 22, "bold"),
            fg="#F4F7F6",
            bg="#0B3D3A",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Ollama qwen2.5:7b  ·  DuckDuckGo  ·  MT5 dry-run",
            font=("Segoe UI", 10),
            fg="#A8C5C1",
            bg="#0B3D3A",
        ).pack(anchor="w")

        controls = tk.Frame(self, bg="#0F4A46")
        controls.pack(fill="x", padx=16, pady=8)

        tk.Label(controls, text="Ativo / ticker:", fg="#F4F7F6", bg="#0F4A46").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=10
        )
        self.ticker_var = tk.StringVar(value=settings.default_ticker)
        ttk.Entry(controls, textvariable=self.ticker_var, width=16).grid(
            row=0, column=1, padx=4, pady=10
        )

        self.btn_health = ttk.Button(controls, text="Health", command=self.run_health)
        self.btn_search = ttk.Button(controls, text="Buscar notícias", command=self.run_search)
        self.btn_analyze = ttk.Button(
            controls, text="Analisar (dry-run)", command=self.run_analyze
        )
        self.btn_health.grid(row=0, column=2, padx=6)
        self.btn_search.grid(row=0, column=3, padx=6)
        self.btn_analyze.grid(row=0, column=4, padx=6)

        self.status_var = tk.StringVar(value="Pronto. Dry-run ativo por padrão.")
        tk.Label(
            self, textvariable=self.status_var, fg="#C9E0DC", bg="#0B3D3A", anchor="w"
        ).pack(fill="x", padx=16)

        self.output = scrolledtext.ScrolledText(
            self,
            wrap="word",
            font=("Consolas", 10),
            bg="#102A28",
            fg="#E8F1EF",
            insertbackground="#E8F1EF",
        )
        self.output.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self._set_busy(False)
        self._writeln(
            "Onde roda o programa:\n"
            "  • CLI:  python -m ia_financeira <health|search|analyze>\n"
            "  • GUI:  python -m ia_financeira.gui\n"
            "  • Atalho: scripts\\launch_ia_financeira.bat "
            "(ícone via install_desktop_shortcut.ps1)\n"
        )

    def _writeln(self, text: str) -> None:
        self.output.insert("end", text.rstrip() + "\n")
        self.output.see("end")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for btn in (self.btn_health, self.btn_search, self.btn_analyze):
            btn.configure(state=state)
        self.status_var.set("Executando…" if busy else "Pronto. Dry-run ativo por padrão.")

    def _run_async(self, label: str, fn) -> None:
        def worker() -> None:
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._on_error(label, exc))
                return
            self.after(0, lambda: self._on_done(label, result))

        self._set_busy(True)
        threading.Thread(target=worker, daemon=True).start()

    def _on_error(self, label: str, exc: Exception) -> None:
        self._set_busy(False)
        self._writeln(f"\n=== ERRO ({label}) ===\n{exc}\n")
        messagebox.showerror("IA Financeira", f"{label} falhou:\n{exc}")

    def _on_done(self, label: str, result: str) -> None:
        self._set_busy(False)
        self._writeln(f"\n=== {label} ===\n{result}\n")

    def run_health(self) -> None:
        def job() -> str:
            ok = OllamaClient().is_available()
            payload = {
                "ollama_model": settings.ollama_model,
                "ollama_available": ok,
                "web_search_backend": settings.web_search_backend,
                "mt5": probe_mt5(),
                "mt5_dry_run": settings.mt5_dry_run,
                "mt5_allow_demo_orders": settings.mt5_allow_demo_orders,
                "can_send_mt5_orders": settings.can_send_mt5_orders(),
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)

        self._run_async("HEALTH", job)

    def run_search(self) -> None:
        ticker = self.ticker_var.get().strip() or settings.default_ticker

        def job() -> str:
            return FinancialWebSearchTool().buscar_noticias_ativo(ticker)

        self._run_async(f"BUSCA {ticker.upper()}", job)

    def run_analyze(self) -> None:
        ticker = self.ticker_var.get().strip() or settings.default_ticker

        def job() -> str:
            result = FinancialAnalyzer().analyze(ticker)
            steps = "\n".join(result.steps)
            body = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            return f"{steps}\n\n{body}"

        self._run_async(f"ANÁLISE {ticker.upper()}", job)


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
