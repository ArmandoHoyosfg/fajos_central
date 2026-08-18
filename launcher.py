#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher GUI — Fajos Central
Centro de control: servidor web, app de escritorio, import Excel, documentación.
Orientado a Windows + PowerShell 7 (también funciona en otros SO).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fajos Central — Centro de control")
        self.geometry("480x560")
        self.minsize(460, 520)
        self.configure(bg="#1e1e2e")

        self._server_proc: subprocess.Popen | None = None
        self._server_log = None
        self._poll_job: str | None = None
        self._desktop_proc: subprocess.Popen | None = None

        self._build_ui()
        self._apply_style()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_status()

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        bg, fg, accent = "#1e1e2e", "#cdd6f4", "#89b4fa"
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground=accent)
        style.configure("Section.TLabel", font=("Segoe UI", 9, "bold"), foreground="#a6adc8")
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=7)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=accent, font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Fajos Central", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(main, text="Centro de control del sistema de nóminas").pack(anchor=tk.W, pady=(0, 8))

        # Estado
        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(status_frame, text="Servidor web:").pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(status_frame, text="● Detenido", style="Status.TLabel", foreground="#f38ba8")
        self.lbl_status.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(main, text=f"URL: {LOCAL_URL}", foreground="#a6adc8").pack(anchor=tk.W, pady=(0, 10))

        # --- Web ---
        web = ttk.LabelFrame(main, text="  Aplicación web (red local)  ", padding=8)
        web.pack(fill=tk.X, pady=4)
        self.btn_start = ttk.Button(web, text="▶  Iniciar servidor web", command=self._start_server)
        self.btn_start.pack(fill=tk.X, pady=2)
        self.btn_stop = ttk.Button(web, text="■  Detener servidor", command=self._stop_server, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=2)
        ttk.Button(web, text="🌐  Abrir en el navegador", command=self._open_browser).pack(fill=tk.X, pady=2)
        ttk.Button(web, text="📖  Abrir documentación API (/docs)", command=self._open_api_docs).pack(fill=tk.X, pady=2)

        # --- Escritorio ---
        desk = ttk.LabelFrame(main, text="  Aplicación de escritorio (PySide6)  ", padding=8)
        desk.pack(fill=tk.X, pady=4)
        ttk.Button(desk, text="🖥  Abrir app de escritorio", command=self._run_desktop).pack(fill=tk.X, pady=2)
        ttk.Label(
            desk,
            text="Requiere: pip install PySide6  (y conexión a MariaDB en config)",
            font=("Segoe UI", 8),
            foreground="#6c7086",
        ).pack(anchor=tk.W)

        # --- Datos ---
        data = ttk.LabelFrame(main, text="  Datos y Excel  ", padding=8)
        data.pack(fill=tk.X, pady=4)
        ttk.Button(data, text="📊  Abrir Excel de nóminas", command=self._open_excel).pack(fill=tk.X, pady=2)
        ttk.Button(data, text="🔍  Importar Excel (simulación)", command=lambda: self._run_import(apply=False)).pack(fill=tk.X, pady=2)
        ttk.Button(data, text="⬇  Importar Excel a la BD (aplicar)", command=lambda: self._run_import(apply=True)).pack(fill=tk.X, pady=2)

        # --- Utilidades ---
        util = ttk.LabelFrame(main, text="  Utilidades  ", padding=8)
        util.pack(fill=tk.X, pady=4)
        row = ttk.Frame(util)
        row.pack(fill=tk.X)
        ttk.Button(row, text="📁 Carpeta proyecto", command=self._open_folder).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(row, text="📘 Guía de uso", command=self._open_uso).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))
        row2 = ttk.Frame(util)
        row2.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(row2, text="🗄 Scripts SQL (schema)", command=self._open_schema).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(row2, text="Salir", command=self._on_close).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        ttk.Label(
            main,
            text="Tip: usa la web en la red local; la app de escritorio es opcional (legacy).",
            font=("Segoe UI", 8),
            foreground="#6c7086",
        ).pack(anchor=tk.W, pady=(10, 0))

    # ----- Servidor -----
    def _is_running(self) -> bool:
        return self._server_proc is not None and self._server_proc.poll() is None

    def _start_server(self) -> None:
        if self._is_running():
            messagebox.showinfo("Servidor", "El servidor ya está en ejecución.")
            return
        try:
            import fastapi  # noqa: F401
            import uvicorn  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Dependencias",
                "Faltan paquetes.\n\nEn PowerShell:\n"
                "  .\\.venv\\Scripts\\Activate.ps1\n"
                "  pip install -r requirements.txt",
            )
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        cmd = [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", HOST, "--port", str(PORT),
        ]
        if os.environ.get("FAJOS_DEBUG", "true").lower() in ("1", "true", "yes"):
            cmd.append("--reload")

        try:
            log_path = ROOT / "logs" / "server_launcher.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_f = open(log_path, "a", encoding="utf-8")
            log_f.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_f.flush()
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore
            self._server_proc = subprocess.Popen(
                cmd, cwd=str(ROOT), env=env,
                stdout=log_f, stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            self._server_log = log_f
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor:\n{e}")
            self._server_proc = None
            return

        self._update_status()
        threading.Thread(target=self._wait_and_maybe_open, daemon=True).start()

    def _wait_and_maybe_open(self) -> None:
        for _ in range(40):
            if not self._is_running():
                return
            if self._port_open():
                self.after(0, self._open_browser)
                return
            time.sleep(0.25)

    def _port_open(self) -> bool:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.35):
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
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, check=False,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as e:
            messagebox.showwarning("Aviso", f"Al detener:\n{e}")
        finally:
            if self._server_log:
                try:
                    self._server_log.close()
                except Exception:
                    pass
                self._server_log = None
            self._server_proc = None
            self._update_status()

    def _open_browser(self) -> None:
        webbrowser.open(LOCAL_URL)

    def _open_api_docs(self) -> None:
        webbrowser.open(f"{LOCAL_URL}/docs")

    # ----- Escritorio -----
    def _run_desktop(self) -> None:
        desktop_main = ROOT / "desktop_legacy" / "main.py"
        if not desktop_main.exists():
            messagebox.showinfo("Escritorio", "No se encontró desktop_legacy/main.py")
            return
        # Comprobar PySide6
        try:
            import PySide6  # noqa: F401
        except ImportError:
            if not messagebox.askyesno(
                "PySide6",
                "No está instalado PySide6.\n\n"
                "¿Quieres que intente instalarlo ahora?\n"
                "(pip install PySide6)",
            ):
                return
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo instalar PySide6:\n{e}")
                return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "desktop_legacy") + os.pathsep + env.get("PYTHONPATH", "")
        try:
            self._desktop_proc = subprocess.Popen(
                [sys.executable, str(desktop_main)],
                cwd=str(ROOT / "desktop_legacy"),
                env=env,
            )
            messagebox.showinfo("Escritorio", "Aplicación de escritorio iniciada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la app de escritorio:\n{e}")

    # ----- Excel / Import -----
    def _open_excel(self) -> None:
        xlsx = ROOT / "templates_excel" / "NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"
        if not xlsx.exists():
            messagebox.showwarning("Excel", f"No se encuentra:\n{xlsx}")
            return
        self._open_path(xlsx)

    def _run_import(self, apply: bool) -> None:
        default = ROOT / "templates_excel" / "NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"
        path = filedialog.askopenfilename(
            title="Seleccionar Excel de nóminas",
            initialdir=str(ROOT / "templates_excel"),
            initialfile=default.name if default.exists() else "",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
        )
        if not path:
            return
        if apply:
            if not messagebox.askyesno(
                "Confirmar importación",
                "Se ESCRIBIRÁN datos nuevos en MariaDB.\n"
                "No se borran registros existentes.\n\n"
                "¿Continuar?",
            ):
                return

        cmd = [sys.executable, str(ROOT / "scripts" / "import_excel.py"), path]
        if apply:
            cmd.append("--apply")

        # Ventana de salida
        win = tk.Toplevel(self)
        win.title("Importación Excel")
        win.geometry("640x400")
        txt = tk.Text(win, wrap=tk.WORD, bg="#11111b", fg="#cdd6f4", font=("Consolas", 9))
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, f"Ejecutando...\n{' '.join(cmd)}\n\n")
        win.update()

        def worker():
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
                proc = subprocess.run(
                    cmd, cwd=str(ROOT), env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                self.after(0, lambda: self._show_import_result(txt, out, proc.returncode))
            except Exception as e:
                self.after(0, lambda: self._show_import_result(txt, str(e), 1))

        threading.Thread(target=worker, daemon=True).start()

    def _show_import_result(self, txt: tk.Text, out: str, code: int) -> None:
        txt.insert(tk.END, out)
        txt.insert(tk.END, f"\n\n--- Fin (código {code}) ---\n")
        txt.see(tk.END)

    # ----- Utilidades -----
    def _open_path(self, path: Path) -> None:
        path = Path(path)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir:\n{path}\n{e}")

    def _open_folder(self) -> None:
        self._open_path(ROOT)

    def _open_uso(self) -> None:
        uso = ROOT / "docs" / "USO.md"
        archivos = ROOT / "docs" / "ARCHIVOS_RAIZ.md"
        if uso.exists():
            self._open_path(uso)
        elif archivos.exists():
            self._open_path(archivos)
        else:
            messagebox.showinfo("Docs", "Consulta README.md en la carpeta del proyecto.")

    def _open_schema(self) -> None:
        self._open_path(ROOT / "db" / "schema")

    def _update_status(self) -> None:
        if self._is_running():
            self.lbl_status.configure(text="● En ejecución", foreground="#a6e3a1")
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.lbl_status.configure(text="● Detenido", foreground="#f38ba8")
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            if self._server_proc is not None and self._server_proc.poll() is not None:
                self._server_proc = None
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(1500, self._update_status)

    def _on_close(self) -> None:
        if self._is_running():
            if not messagebox.askyesno("Salir", "El servidor sigue activo.\n¿Detenerlo y salir?"):
                return
            self._stop_server()
        self.destroy()


def main() -> None:
    app = LauncherApp()
    app.update_idletasks()
    w, h = 480, 560
    x = (app.winfo_screenwidth() // 2) - (w // 2)
    y = (app.winfo_screenheight() // 2) - (h // 2)
    app.geometry(f"{w}x{h}+{x}+{y}")
    app.mainloop()


if __name__ == "__main__":
    main()
