#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher GUI — Fajos Central
Permite iniciar/detener el servidor web y abrir la aplicación.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Cargar .env si existe (sin depender de pydantic al inicio)
def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


_load_dotenv()

HOST = os.environ.get("FAJOS_APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("FAJOS_APP_PORT", "8000"))
LOCAL_URL = f"http://127.0.0.1:{PORT}"


# ---------------------------------------------------------------------------
# GUI (tkinter — sin dependencias extra)
# ---------------------------------------------------------------------------
import tkinter as tk
from tkinter import messagebox, ttk


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fajos Central — Launcher")
        self.geometry("420x380")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self._server_proc: subprocess.Popen | None = None
        self._poll_job: str | None = None

        self._build_ui()
        self._apply_style()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_status()

    # ----- UI -----
    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#89b4fa")
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Fajos Central", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(main, text="Launcher del sistema de nóminas").pack(anchor=tk.W, pady=(0, 12))

        # Estado
        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(0, 16))
        ttk.Label(status_frame, text="Estado del servidor:").pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(status_frame, text="● Detenido", style="Status.TLabel", foreground="#f38ba8")
        self.lbl_status.pack(side=tk.LEFT, padx=(8, 0))

        self.lbl_url = ttk.Label(main, text=f"URL local: {LOCAL_URL}", foreground="#a6adc8")
        self.lbl_url.pack(anchor=tk.W, pady=(0, 16))

        # Botones principales
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=4)

        self.btn_start = ttk.Button(btn_frame, text="▶  Iniciar servidor web", command=self._start_server)
        self.btn_start.pack(fill=tk.X, pady=4)

        self.btn_stop = ttk.Button(btn_frame, text="■  Detener servidor", command=self._stop_server, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=4)

        self.btn_open = ttk.Button(btn_frame, text="🌐  Abrir en el navegador", command=self._open_browser)
        self.btn_open.pack(fill=tk.X, pady=4)

        # Separador visual
        ttk.Label(main, text="").pack(pady=4)

        # App de escritorio (legacy)
        self.btn_desktop = ttk.Button(
            main,
            text="🖥  Abrir app de escritorio (legacy)",
            command=self._run_desktop,
        )
        self.btn_desktop.pack(fill=tk.X, pady=4)

        # Utilidades
        util = ttk.Frame(main)
        util.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(util, text="Abrir carpeta del proyecto", command=self._open_folder).pack(side=tk.LEFT)
        ttk.Button(util, text="Salir", command=self._on_close).pack(side=tk.RIGHT)

        self.lbl_hint = ttk.Label(
            main,
            text=("Tip: con el servidor activo, otros PCs en la red pueden entrar a\nhttp://TU_IP:{}  |  Windows: pwsh -File .\\start.ps1".format(PORT)),
            foreground="#6c7086",
            font=("Segoe UI", 8),
            justify=tk.LEFT,
        )
        self.lbl_hint.pack(anchor=tk.W, pady=(16, 0))

    # ----- Servidor -----
    def _is_running(self) -> bool:
        if self._server_proc is None:
            return False
        return self._server_proc.poll() is None

    def _start_server(self) -> None:
        if self._is_running():
            messagebox.showinfo("Servidor", "El servidor ya está en ejecución.")
            return

        # Verificar dependencias básicas
        try:
            import uvicorn  # noqa: F401
            import fastapi  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Dependencias",
                "Faltan paquetes de Python.\n\n"
                "En la carpeta del proyecto ejecuta:\n"
                "  pip install -r requirements.txt",
            )
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
        ]
        if os.environ.get("FAJOS_DEBUG", "true").lower() in ("1", "true", "yes"):
            cmd.append("--reload")

        try:
            # En Windows: CREATE_NEW_PROCESS_GROUP ayuda a matar el árbol
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

            log_path = ROOT / "logs" / "server_launcher.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_f = open(log_path, "a", encoding="utf-8")
            log_f.write(f"\n--- start {time.strftime("%Y-%m-%d %H:%M:%S")} ---\n")
            log_f.flush()
            self._server_proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            self._server_log = log_f
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor:\n{e}")
            self._server_proc = None
            return

        self._update_status()
        # Esperar un momento y abrir navegador si responde
        threading.Thread(target=self._wait_and_maybe_open, daemon=True).start()

    def _wait_and_maybe_open(self) -> None:
        for _ in range(30):
            if not self._is_running():
                return
            if self._port_open():
                self.after(0, self._open_browser)
                return
            time.sleep(0.3)

    def _port_open(self) -> bool:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.4):
                return True
        except OSError:
            return False

    def _stop_server(self) -> None:
        if not self._is_running() or self._server_proc is None:
            self._server_proc = None
            self._update_status()
            return
        proc = self._server_proc
        try:
            if sys.platform == "win32":
                # Terminar árbol de procesos en Windows
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as e:
            messagebox.showwarning("Aviso", f"Al detener el servidor:\n{e}")
        finally:
            if getattr(self, "_server_log", None):
                try:
                    self._server_log.close()
                except Exception:
                    pass
                self._server_log = None
            self._server_proc = None
            self._update_status()

    def _open_browser(self) -> None:
        webbrowser.open(LOCAL_URL)

    def _run_desktop(self) -> None:
        desktop_main = ROOT / "desktop_legacy" / "main.py"
        if not desktop_main.exists():
            messagebox.showinfo(
                "App de escritorio",
                "No se encontró desktop_legacy/main.py.\n"
                "La interfaz principal es la web (Iniciar servidor).",
            )
            return
        try:
            subprocess.Popen(
                [sys.executable, str(desktop_main)],
                cwd=str(ROOT / "desktop_legacy"),
            )
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"No se pudo abrir la app de escritorio:\n{e}\n\n"
                "¿Tienes PySide6 instalado?\n  pip install PySide6",
            )

    def _open_folder(self) -> None:
        path = str(ROOT)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")

    def _update_status(self) -> None:
        running = self._is_running()
        if running:
            self.lbl_status.configure(text="● En ejecución", foreground="#a6e3a1")
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.lbl_status.configure(text="● Detenido", foreground="#f38ba8")
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            if self._server_proc is not None and self._server_proc.poll() is not None:
                self._server_proc = None

        # Reprogramar poll
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(1500, self._update_status)

    def _on_close(self) -> None:
        if self._is_running():
            if not messagebox.askyesno(
                "Salir",
                "El servidor web sigue en ejecución.\n¿Detenerlo y salir?",
            ):
                return
            self._stop_server()
        self.destroy()


def main() -> None:
    app = LauncherApp()
    # Centrar ventana
    app.update_idletasks()
    w, h = 420, 380
    x = (app.winfo_screenwidth() // 2) - (w // 2)
    y = (app.winfo_screenheight() // 2) - (h // 2)
    app.geometry(f"{w}x{h}+{x}+{y}")
    app.mainloop()


if __name__ == "__main__":
    main()
