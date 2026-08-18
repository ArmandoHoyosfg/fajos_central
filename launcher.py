#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher GUI — Fajos Central / Fajos Piteados Central
Centro de control: servidor web, escritorio, import, config BD.
Windows + PowerShell 7.
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
LOGO_PATH = ROOT / "app" / "web" / "static" / "logo.png"

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fajos Piteados Central — Centro de control")
        self.geometry("500x700")
        self.minsize(480, 600)
        self.configure(bg="#1e1e2e")

        self._server_proc: subprocess.Popen | None = None
        self._server_log = None
        self._poll_job: str | None = None
        self._desktop_proc: subprocess.Popen | None = None
        self._logo_img = None

        self._apply_style()
        self._build_ui()
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
        style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground=accent)
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure(
            "TLabelframe.Label",
            background=bg,
            foreground=accent,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("TEntry", fieldbackground="#313244", foreground=fg)

    def _build_ui(self) -> None:
        # Canvas + scrollbar para que todo sea visible en pantallas pequeñas
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg="#1e1e2e", highlightthickness=0)
        sb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        main = ttk.Frame(canvas, padding=16)

        main.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=main, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Logo + título
        head = ttk.Frame(main)
        head.pack(fill=tk.X, pady=(0, 8))
        if LOGO_PATH.exists():
            try:
                from PIL import Image, ImageTk
                im = Image.open(LOGO_PATH)
                im.thumbnail((72, 72))
                self._logo_img = ImageTk.PhotoImage(im)
                tk.Label(head, image=self._logo_img, bg="#1e1e2e").pack(side=tk.LEFT, padx=(0, 12))
            except Exception:
                try:
                    self._logo_img = tk.PhotoImage(file=str(LOGO_PATH))
                    # subsample if huge
                    w = self._logo_img.width()
                    if w > 80:
                        f = max(1, w // 72)
                        self._logo_img = self._logo_img.subsample(f, f)
                    tk.Label(head, image=self._logo_img, bg="#1e1e2e").pack(side=tk.LEFT, padx=(0, 12))
                except Exception:
                    pass
        titles = ttk.Frame(head)
        titles.pack(side=tk.LEFT, fill=tk.X)
        ttk.Label(titles, text="Fajos Piteados Central", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(titles, text="Centro de control — nóminas y producción").pack(anchor=tk.W)

        # Estado servidor
        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(8, 4))
        ttk.Label(status_frame, text="Servidor web:").pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(
            status_frame, text="● Detenido", style="Status.TLabel", foreground="#f38ba8"
        )
        self.lbl_status.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(main, text=f"URL: {LOCAL_URL}", foreground="#a6adc8").pack(anchor=tk.W, pady=(0, 8))

        # --- BD PRIMERO (visible sin scroll) ---
        dbframe = ttk.LabelFrame(main, text="  Base de datos (MariaDB)  ", padding=10)
        dbframe.pack(fill=tk.X, pady=6)
        ttk.Button(
            dbframe,
            text="⚙  Configurar conexión (usuario / contraseña)",
            command=self._config_db,
        ).pack(fill=tk.X, pady=3)
        ttk.Button(dbframe, text="🔌  Probar conexión", command=self._test_db).pack(fill=tk.X, pady=3)
        self.lbl_db = ttk.Label(dbframe, text="", font=("Segoe UI", 8), foreground="#a6adc8")
        self.lbl_db.pack(anchor=tk.W, pady=(4, 0))
        self._refresh_db_label()

        # --- Web ---
        web = ttk.LabelFrame(main, text="  Aplicación web (red local)  ", padding=10)
        web.pack(fill=tk.X, pady=6)
        self.btn_start = ttk.Button(web, text="▶  Iniciar servidor web", command=self._start_server)
        self.btn_start.pack(fill=tk.X, pady=3)
        self.btn_stop = ttk.Button(
            web, text="■  Detener servidor", command=self._stop_server, state=tk.DISABLED
        )
        self.btn_stop.pack(fill=tk.X, pady=3)
        ttk.Button(web, text="🌐  Abrir en el navegador", command=self._open_browser).pack(
            fill=tk.X, pady=3
        )
        ttk.Button(web, text="📖  Documentación API (/docs)", command=self._open_api_docs).pack(
            fill=tk.X, pady=3
        )

        # --- Escritorio ---
        desk = ttk.LabelFrame(main, text="  Aplicación de escritorio  ", padding=10)
        desk.pack(fill=tk.X, pady=6)
        ttk.Button(desk, text="🖥  Abrir app de escritorio", command=self._run_desktop).pack(
            fill=tk.X, pady=3
        )

        # --- Datos ---
        data = ttk.LabelFrame(main, text="  Datos y Excel  ", padding=10)
        data.pack(fill=tk.X, pady=6)
        ttk.Button(data, text="📊  Abrir Excel de nóminas", command=self._open_excel).pack(
            fill=tk.X, pady=3
        )
        ttk.Button(
            data, text="🔍  Importar Excel (simulación)", command=lambda: self._run_import(False)
        ).pack(fill=tk.X, pady=3)
        ttk.Button(
            data, text="⬇  Importar Excel a la BD (aplicar)", command=lambda: self._run_import(True)
        ).pack(fill=tk.X, pady=3)

        # --- Utilidades ---
        util = ttk.LabelFrame(main, text="  Utilidades  ", padding=10)
        util.pack(fill=tk.X, pady=6)
        row = ttk.Frame(util)
        row.pack(fill=tk.X)
        ttk.Button(row, text="📁 Carpeta", command=self._open_folder).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4)
        )
        ttk.Button(row, text="📘 Guía de uso", command=self._open_uso).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=4
        )
        ttk.Button(row, text="🗄 SQL", command=self._open_schema).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0)
        )
        ttk.Button(util, text="Salir", command=self._on_close).pack(fill=tk.X, pady=(8, 0))

    # ----- BD -----
    def _refresh_db_label(self) -> None:
        try:
            from app.core.config import CONFIG_INI, load_ini_database

            d = load_ini_database()
            src = "config.ini" if CONFIG_INI.exists() else "por defecto (sin config.ini)"
            self.lbl_db.configure(
                text=f"{d['user']}@{d['host']}:{d['port']}/{d['database']}  [{src}]"
            )
        except Exception as e:
            self.lbl_db.configure(text=f"Config no leída: {e}")

    def _config_db(self) -> None:
        try:
            from app.core.config import load_ini_database, save_database_config
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar config:\n{e}")
            return

        data = load_ini_database()
        win = tk.Toplevel(self)
        win.title("Conexión a MariaDB")
        win.geometry("420x340")
        win.configure(bg="#1e1e2e")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)

        fields = {}
        specs = [
            ("host", "Servidor (host)", data["host"]),
            ("port", "Puerto", str(data["port"])),
            ("user", "Usuario", data["user"]),
            ("password", "Contraseña", data["password"]),
            ("database", "Base de datos", data["database"]),
        ]
        for i, (key, label, val) in enumerate(specs):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            ent = ttk.Entry(frm, width=30, show="*" if key == "password" else "")
            ent.insert(0, val)
            ent.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            fields[key] = ent
        frm.columnconfigure(1, weight=1)

        def guardar():
            try:
                port = int(fields["port"].get().strip() or "3306")
            except ValueError:
                messagebox.showerror("Datos", "Puerto inválido", parent=win)
                return
            path = save_database_config(
                host=fields["host"].get().strip() or "localhost",
                port=port,
                user=fields["user"].get().strip() or "root",
                password=fields["password"].get(),
                database=fields["database"].get().strip() or "fajos_central",
            )
            os.environ["FAJOS_DB_HOST"] = fields["host"].get().strip() or "localhost"
            os.environ["FAJOS_DB_PORT"] = str(port)
            os.environ["FAJOS_DB_USER"] = fields["user"].get().strip() or "root"
            os.environ["FAJOS_DB_PASSWORD"] = fields["password"].get()
            os.environ["FAJOS_DB_NAME"] = fields["database"].get().strip() or "fajos_central"
            try:
                from app.core.config import get_settings

                get_settings.cache_clear()
            except Exception:
                pass
            self._refresh_db_label()
            messagebox.showinfo(
                "Guardado",
                f"Guardado en:\n{path}\n\n"
                "Si el servidor web está activo, deténlo e inícialo de nuevo.",
                parent=win,
            )
            win.destroy()

        ttk.Button(frm, text="Guardar conexión", command=guardar).grid(
            row=len(specs), column=0, columnspan=2, sticky=tk.EW, pady=(16, 4)
        )
        ttk.Button(frm, text="Cancelar", command=win.destroy).grid(
            row=len(specs) + 1, column=0, columnspan=2, sticky=tk.EW
        )

    def _test_db(self) -> None:
        try:
            from app.core.config import _read_ini, get_settings

            for k, v in _read_ini().items():
                os.environ[f"FAJOS_{k.upper()}"] = str(v)
            get_settings.cache_clear()
            settings = get_settings()
            import mysql.connector

            conn = mysql.connector.connect(**settings.db_config)
            conn.close()
            messagebox.showinfo(
                "Conexión OK",
                f"Conectado a\n{settings.db_user}@{settings.db_host}:{settings.db_port}/{settings.db_name}",
            )
        except Exception as e:
            messagebox.showerror(
                "Conexión fallida",
                f"No se pudo conectar.\n\n{e}\n\n"
                "Usa «Configurar conexión» y comprueba que MariaDB esté en marcha.",
            )

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
                "Faltan paquetes.\n\n"
                "  .\\.venv\\Scripts\\Activate.ps1\n"
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
            log_path = ROOT / "logs" / "server_launcher.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_f = open(log_path, "a", encoding="utf-8")
            log_f.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_f.flush()
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore
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
            messagebox.showerror("Error", f"No se pudo iniciar:\n{e}")
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

    def _run_desktop(self) -> None:
        desktop_main = ROOT / "desktop_legacy" / "main.py"
        if not desktop_main.exists():
            messagebox.showinfo("Escritorio", "No se encontró desktop_legacy/main.py")
            return
        try:
            import PySide6  # noqa: F401
        except ImportError:
            if not messagebox.askyesno("PySide6", "¿Instalar PySide6 ahora?"):
                return
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "desktop_legacy") + os.pathsep + env.get("PYTHONPATH", "")
        try:
            self._desktop_proc = subprocess.Popen(
                [sys.executable, str(desktop_main)],
                cwd=str(ROOT / "desktop_legacy"),
                env=env,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_excel(self) -> None:
        xlsx = ROOT / "templates_excel" / "NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"
        if xlsx.exists():
            self._open_path(xlsx)
        else:
            messagebox.showwarning("Excel", f"No encontrado:\n{xlsx}")

    def _run_import(self, apply: bool) -> None:
        path = filedialog.askopenfilename(
            title="Excel de nóminas",
            initialdir=str(ROOT / "templates_excel"),
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
        )
        if not path:
            return
        if apply and not messagebox.askyesno(
            "Confirmar", "Se escribirán datos nuevos en MariaDB.\n¿Continuar?"
        ):
            return
        cmd = [sys.executable, str(ROOT / "scripts" / "import_excel.py"), path]
        if apply:
            cmd.append("--apply")
        win = tk.Toplevel(self)
        win.title("Importación")
        win.geometry("640x400")
        txt = tk.Text(win, wrap=tk.WORD, bg="#11111b", fg="#cdd6f4", font=("Consolas", 9))
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, "Ejecutando...\n\n")
        win.update()

        def worker():
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
                proc = subprocess.run(
                    cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                self.after(0, lambda: (txt.insert(tk.END, out + f"\n\nCódigo {proc.returncode}\n"), txt.see(tk.END)))
            except Exception as e:
                self.after(0, lambda: txt.insert(tk.END, str(e)))

        threading.Thread(target=worker, daemon=True).start()

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
            messagebox.showerror("Error", str(e))

    def _open_folder(self) -> None:
        self._open_path(ROOT)

    def _open_uso(self) -> None:
        for name in ("USO.md", "ARCHIVOS_RAIZ.md"):
            p = ROOT / "docs" / name
            if p.exists():
                self._open_path(p)
                return
        messagebox.showinfo("Docs", "Consulta README.md")

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
            if not messagebox.askyesno("Salir", "¿Detener servidor y salir?"):
                return
            self._stop_server()
        self.destroy()


def main() -> None:
    app = LauncherApp()
    app.update_idletasks()
    w, h = 500, 700
    x = (app.winfo_screenwidth() // 2) - (w // 2)
    y = max(0, (app.winfo_screenheight() // 2) - (h // 2))
    app.geometry(f"{w}x{h}+{x}+{y}")
    app.mainloop()


if __name__ == "__main__":
    main()
