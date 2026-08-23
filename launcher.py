#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher — Fajos Piteados Central
Centro de control compacto (Windows + PowerShell 7).
La config de BD usa solo config.ini (stdlib); no requiere pydantic.
"""
from __future__ import annotations

import configparser
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

def _app_version() -> str:
    vf = Path(__file__).resolve().parent / 'VERSION'
    try:
        return vf.read_text(encoding='utf-8').strip() or '0.0.0'
    except Exception:
        return '0.0.0'

APP_VERSION = _app_version()


def _local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_INI = ROOT / "config.ini"
LOGO_PATH = ROOT / "app" / "web" / "static" / "logo.png"


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


def _read_db_ini() -> dict:
    d = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "fajos_central",
        "app_host": "0.0.0.0",
        "app_port": 8000,
        "debug": True,
        "force_https": False,
        "ssl_certfile": "certs/cert.pem",
        "ssl_keyfile": "certs/key.pem",
    }
    if not CONFIG_INI.exists():
        # env overrides
        d["host"] = os.environ.get("FAJOS_DB_HOST", d["host"])
        d["port"] = int(os.environ.get("FAJOS_DB_PORT", d["port"]))
        d["user"] = os.environ.get("FAJOS_DB_USER", d["user"])
        d["password"] = os.environ.get("FAJOS_DB_PASSWORD", d["password"])
        d["database"] = os.environ.get("FAJOS_DB_NAME", d["database"])
        d["app_port"] = int(os.environ.get("FAJOS_APP_PORT", d["app_port"]))
        return d
    cp = configparser.ConfigParser()
    cp.read(CONFIG_INI, encoding="utf-8")
    if cp.has_section("database"):
        db = cp["database"]
        d["host"] = db.get("host", d["host"])
        try:
            d["port"] = int(db.get("port", str(d["port"])))
        except ValueError:
            pass
        d["user"] = db.get("user", d["user"])
        d["password"] = db.get("password", d["password"])
        d["database"] = db.get("database", d["database"])
    if cp.has_section("server"):
        srv = cp["server"]
        d["app_host"] = srv.get("host", d["app_host"])
        try:
            d["app_port"] = int(srv.get("port", str(d["app_port"])))
        except ValueError:
            pass
        d["debug"] = srv.get("debug", "true").lower() in ("1", "true", "yes")
        d["force_https"] = srv.get("force_https", "false").lower() in ("1", "true", "yes")
        d["ssl_certfile"] = srv.get("ssl_certfile", d["ssl_certfile"])
        d["ssl_keyfile"] = srv.get("ssl_keyfile", d["ssl_keyfile"])
    return d


def _save_db_ini(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> Path:
    cp = configparser.ConfigParser()
    if CONFIG_INI.exists():
        cp.read(CONFIG_INI, encoding="utf-8")
    if not cp.has_section("database"):
        cp.add_section("database")
    if not cp.has_section("server"):
        cp.add_section("server")
        cur = _read_db_ini()
        cp.set("server", "host", cur["app_host"])
        cp.set("server", "port", str(cur["app_port"]))
        cp.set("server", "debug", "true" if cur["debug"] else "false")
        cp.set("server", "force_https", "true" if cur["force_https"] else "false")
        cp.set("server", "ssl_certfile", cur["ssl_certfile"])
        cp.set("server", "ssl_keyfile", cur["ssl_keyfile"])
    cp.set("database", "host", host)
    cp.set("database", "port", str(port))
    cp.set("database", "user", user)
    cp.set("database", "password", password)
    cp.set("database", "database", database)
    with open(CONFIG_INI, "w", encoding="utf-8") as f:
        f.write("; Fajos Piteados Central — configuración local (no subir a Git)\n")
        cp.write(f)
    return CONFIG_INI


def _ssl_files():
    cfg = _read_db_ini()
    cert = (cfg.get("ssl_certfile") or "").strip()
    key = (cfg.get("ssl_keyfile") or "").strip()
    if not cert or not key:
        c, k = ROOT / "certs" / "cert.pem", ROOT / "certs" / "key.pem"
        return (str(c), str(k)) if c.exists() and k.exists() else None
    pc, pk = Path(cert), Path(key)
    if not pc.is_absolute():
        pc = ROOT / pc
    if not pk.is_absolute():
        pk = ROOT / pk
    return (str(pc), str(pk)) if pc.exists() and pk.exists() else None


def _port() -> int:
    return int(_read_db_ini().get("app_port") or 8000)


def _host_bind() -> str:
    return _read_db_ini().get("app_host") or "0.0.0.0"


def _base_url() -> str:
    scheme = "https" if _ssl_files() else "http"
    return f"{scheme}://127.0.0.1:{_port()}"


def _center(win, w: int | None = None, h: int | None = None) -> None:
    win.update_idletasks()
    if w is None:
        w = win.winfo_width()
    if h is None:
        h = win.winfo_height()
    if w <= 1:
        w = win.winfo_reqwidth()
    if h <= 1:
        h = win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw // 2) - (w // 2))
    y = max(0, (sh // 2) - (h // 2))
    win.geometry(f"{w}x{h}+{x}+{y}")


import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Fajos Piteados Central — Centro de control  ·  v{APP_VERSION}")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)

        self._server_proc: subprocess.Popen | None = None
        self._server_log = None
        self._poll_job: str | None = None
        self._logo_img = None

        self._apply_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Tamaño exacto al contenido (sin scroll ni ventana sobrada)
        self.update_idletasks()
        w = max(460, self.winfo_reqwidth())
        h = self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Si por DPI no cabe, reducir padding no aplica; limitar al 90% pantalla
        h = min(h, int(sh * 0.9))
        w = min(w, sw - 20)
        _center(self, w, h)
        self._update_status()


    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        bg, surface, text, muted, accent = "#11111b", "#1e1e2e", "#cdd6f4", "#a6adc8", "#cba6f7"
        self.configure(bg=bg)
        style.configure(".", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("TLabelframe", background=bg, foreground=muted)
        style.configure("TLabelframe.Label", background=bg, foreground=muted, font=("Segoe UI", 9, "bold"))
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.map("TButton", background=[("active", "#313244")])
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground=accent)
        style.configure("Muted.TLabel", foreground=muted, font=("Segoe UI", 9))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=(16, 12))
        main.pack(fill=tk.BOTH, expand=True)

        # Cabecera
        head = ttk.Frame(main)
        head.pack(fill=tk.X, pady=(0, 8))
        if LOGO_PATH.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(LOGO_PATH).resize((40, 40))
                self._logo_img = ImageTk.PhotoImage(img)
                ttk.Label(head, image=self._logo_img).pack(side=tk.LEFT, padx=(0, 10))
            except Exception:
                pass
        titles = ttk.Frame(head)
        titles.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(titles, text="Fajos Central", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            titles,
            text=f"Nóminas · v{APP_VERSION}",
            style="Muted.TLabel",
        ).pack(anchor=tk.W)
        self.lbl_lan = ttk.Label(titles, text="", style="Muted.TLabel")
        self.lbl_lan.pack(anchor=tk.W)

        # Estado + acción principal
        status_box = ttk.LabelFrame(main, text=" Servidor web ", padding=10)
        status_box.pack(fill=tk.X, pady=4)
        row = ttk.Frame(status_box)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Estado:").pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(row, text="● Detenido", style="Status.TLabel", foreground="#f38ba8")
        self.lbl_status.pack(side=tk.LEFT, padx=8)
        self.lbl_url = ttk.Label(status_box, text=f"URL: {_base_url()}", style="Muted.TLabel")
        self.lbl_url.pack(anchor=tk.W, pady=(6, 8))

        actions = ttk.Frame(status_box)
        actions.pack(fill=tk.X)
        self.btn_start = ttk.Button(actions, text="▶  Iniciar", style="Accent.TButton", command=self._start_server)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(actions, text="■  Detener", command=self._stop_server, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="🌐 Abrir", command=self._open_browser).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="📋 URL", command=self._copy_lan_url).pack(side=tk.LEFT)

        # Base de datos
        db = ttk.LabelFrame(main, text=" Base de datos ", padding=10)
        db.pack(fill=tk.X, pady=4)
        self.lbl_db = ttk.Label(db, text="", style="Muted.TLabel")
        self.lbl_db.pack(anchor=tk.W)
        db_btns = ttk.Frame(db)
        db_btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(db_btns, text="⚙ Configurar", command=self._config_db).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(db_btns, text="🔌 Probar", command=self._test_db).pack(side=tk.LEFT)

        # Sistema (compacto)
        sysf = ttk.LabelFrame(main, text=" Sistema ", padding=10)
        sysf.pack(fill=tk.X, pady=4)
        self.var_backup = tk.BooleanVar(value=True)
        self.var_startup = tk.BooleanVar(value=self._startup_enabled())
        ttk.Checkbutton(
            sysf,
            text="Backup al cerrar (Excel Master + config)",
            variable=self.var_backup,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            sysf,
            text="Iniciar con Windows",
            variable=self.var_startup,
            command=self._toggle_startup,
        ).pack(anchor=tk.W, pady=(4, 0))

        sys_btns = ttk.Frame(sysf)
        sys_btns.pack(fill=tk.X, pady=(10, 0))
        for txt, cmd in (
            ("📌 Acceso directo", self._create_desktop_shortcut),
            ("✅ Verificar", self._verify_env),
            ("💾 Backup ahora", self._backup_now),
            ("📁 Carpeta", self._open_folder),
        ):
            ttk.Button(sys_btns, text=txt, command=cmd).pack(side=tk.LEFT, padx=(0, 4))

        # Más (colapsado en una fila secundaria)
        more = ttk.Frame(main)
        more.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(more, text="📊 Excel", command=self._open_excel).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(more, text="Importar…", command=lambda: self._run_import(False)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(more, text="🗄 SQL", command=self._open_schema).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(more, text="API", command=self._open_api_docs).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(more, text="Salir", command=self._on_close).pack(side=tk.RIGHT)

        self._refresh_db_label()
        self._refresh_lan_label()
        self._update_status()

    def _refresh_db_label(self) -> None:
        d = _read_db_ini()
        src = "config.ini" if CONFIG_INI.exists() else "por defecto"
        self.lbl_db.configure(
            text=f"{d['user']}@{d['host']}:{d['port']}/{d['database']}  [{src}]"
        )

    def _config_db(self) -> None:
        data = _read_db_ini()
        win = tk.Toplevel(self)
        win.title("Conexión MariaDB")
        win.configure(bg="#1e1e2e")
        win.transient(self)
        win.grab_set()
        _center(win, 400, 300)

        frm = ttk.Frame(win, padding=14)
        frm.pack(fill=tk.BOTH, expand=True)
        fields = {}
        specs = [
            ("host", "Servidor", data["host"]),
            ("port", "Puerto", str(data["port"])),
            ("user", "Usuario", data["user"]),
            ("password", "Contraseña", data["password"]),
            ("database", "Base de datos", data["database"]),
        ]
        for i, (key, label, val) in enumerate(specs):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            ent = ttk.Entry(frm, width=28, show="*" if key == "password" else "")
            ent.insert(0, val)
            ent.grid(row=i, column=1, sticky=tk.EW, pady=4, padx=(8, 0))
            fields[key] = ent
        frm.columnconfigure(1, weight=1)

        def guardar():
            try:
                port = int(fields["port"].get().strip() or "3306")
            except ValueError:
                messagebox.showerror("Datos", "Puerto inválido", parent=win)
                return
            path = _save_db_ini(
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
            self._refresh_db_label()
            messagebox.showinfo(
                "Guardado",
                f"Guardado en:\n{path}\n\nReinicia el servidor web si ya estaba activo.",
                parent=win,
            )
            win.destroy()

        ttk.Button(frm, text="Guardar", command=guardar).grid(
            row=len(specs), column=0, columnspan=2, sticky=tk.EW, pady=(12, 4)
        )
        ttk.Button(frm, text="Cancelar", command=win.destroy).grid(
            row=len(specs) + 1, column=0, columnspan=2, sticky=tk.EW
        )

    def _test_db(self) -> None:
        d = _read_db_ini()
        try:
            import mysql.connector
        except ImportError:
            messagebox.showerror(
                "Dependencia",
                "Falta mysql-connector-python.\n\n"
                "En PowerShell:\n"
                "  .\\.venv\\Scripts\\Activate.ps1\n"
                "  pip install -r requirements.txt\n\n"
                "Luego vuelve a abrir el launcher desde el venv:\n"
                "  python launcher.py",
            )
            return
        try:
            conn = mysql.connector.connect(
                host=d["host"],
                port=d["port"],
                user=d["user"],
                password=d["password"],
                database=d["database"],
                connection_timeout=5,
            )
            conn.close()
            messagebox.showinfo(
                "Conexión OK",
                f"Conectado a\n{d['user']}@{d['host']}:{d['port']}/{d['database']}",
            )
        except Exception as e:
            messagebox.showerror(
                "Conexión fallida",
                f"No se pudo conectar.\n\n{e}\n\n"
                "Revisa usuario/contraseña y que MariaDB esté activo.",
            )

    def _is_running(self) -> bool:
        return self._server_proc is not None and self._server_proc.poll() is None

    def _refresh_lan_label(self) -> None:
        try:
            cfg = _read_db_ini()
            port = int(cfg.get("app_port") or 8000)
            https = bool(cfg.get("force_https"))
            scheme = "https" if https else "http"
            ip = _local_ip()
            url = f"{scheme}://{ip}:{port}"
            self.lbl_lan.configure(
                text=f"Red local (otros equipos):  {url}"
            )
            self._lan_url = url
            if hasattr(self, 'lbl_url'):
                try:
                    self.lbl_url.configure(text=f'URL: {url}')
                except Exception:
                    pass
        except Exception:
            self.lbl_lan.configure(text="Red local: —")
            self._lan_url = ""

    def _copy_lan_url(self) -> None:
        url = getattr(self, "_lan_url", "") or ""
        if not url:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()
            self._log(f"URL copiada: {url}")
        except Exception as e:
            self._log(f"No se pudo copiar: {e}")

    def _start_server(self) -> None:
        if self._is_running():
            messagebox.showinfo("Servidor", "Ya está en ejecución.")
            return
        try:
            import fastapi  # noqa: F401
            import uvicorn  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Dependencias",
                "Faltan paquetes del proyecto.\n\n"
                "  .\\.venv\\Scripts\\Activate.ps1\n"
                "  pip install -r requirements.txt\n"
                "  python launcher.py",
            )
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        # Pasar BD desde config.ini al proceso del servidor
        d = _read_db_ini()
        env["FAJOS_DB_HOST"] = str(d["host"])
        env["FAJOS_DB_PORT"] = str(d["port"])
        env["FAJOS_DB_USER"] = str(d["user"])
        env["FAJOS_DB_PASSWORD"] = str(d["password"])
        env["FAJOS_DB_NAME"] = str(d["database"])
        env["FAJOS_APP_HOST"] = str(d["app_host"])
        env["FAJOS_APP_PORT"] = str(d["app_port"])

        cmd = [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", _host_bind(),
            "--port", str(_port()),
        ]
        ssl = _ssl_files()
        if ssl:
            cmd.extend(["--ssl-certfile", ssl[0], "--ssl-keyfile", ssl[1]])
            env["FAJOS_FORCE_HTTPS"] = "true"
        elif d.get("debug", True):
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
            messagebox.showerror("Error", f"No se pudo iniciar:\n{e}")
            self._server_proc = None
            return

        self.lbl_url.configure(text=f"URL: {_base_url()}")
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
            with socket.create_connection(("127.0.0.1", _port()), timeout=0.35):
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
            messagebox.showwarning("Aviso", str(e))
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
        webbrowser.open(_base_url())

    def _open_api_docs(self) -> None:
        webbrowser.open(_base_url() + "/docs")

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
            subprocess.Popen(
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

        # 1) Siempre simular primero y mostrar vista previa
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        d = _read_db_ini()
        env["FAJOS_DB_HOST"] = str(d["host"])
        env["FAJOS_DB_PORT"] = str(d["port"])
        env["FAJOS_DB_USER"] = str(d["user"])
        env["FAJOS_DB_PASSWORD"] = str(d["password"])
        env["FAJOS_DB_NAME"] = str(d["database"])

        script = ROOT / "scripts" / "import_excel.py"
        if not script.exists():
            script = ROOT / "scripts" / "importar_excel.py"

        win = tk.Toplevel(self)
        win.title("Vista previa — Importación Excel")
        win.configure(bg="#1e1e2e")
        try:
            win.state("zoomed")
        except Exception:
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{min(900, sw)}x{min(600, sh)}")
        _center(win, min(900, win.winfo_screenwidth()), min(560, win.winfo_screenheight()))

        frm = ttk.Frame(win, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frm,
            text="Simulación (no escribe en BD). Revisa el resumen y confirma si aplica.",
            foreground="#a6adc8",
        ).pack(anchor=tk.W)

        txt = tk.Text(frm, wrap=tk.WORD, bg="#11111b", fg="#cdd6f4", font=("Consolas", 10), height=24)
        txt.pack(fill=tk.BOTH, expand=True, pady=6)
        txt.insert(tk.END, f"Archivo: {path}\nEjecutando simulación...\n\n")
        win.update()

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X)
        btn_apply = ttk.Button(btn_row, text="⬇  Aplicar a la base de datos", state=tk.DISABLED)
        btn_apply.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cerrar", command=win.destroy).pack(side=tk.RIGHT, padx=4)

        def run_cmd(do_apply: bool):
            cmd = [sys.executable, str(script)]
            # import_excel.py uses positional excel; importar_excel uses --excel
            if script.name == "importar_excel.py":
                cmd += ["--excel", path]
                if do_apply:
                    cmd.append("--aplicar")
            else:
                cmd.append(path)
                if do_apply:
                    cmd.append("--apply")
            try:
                proc = subprocess.run(
                    cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                return proc.returncode, out
            except Exception as e:
                return 1, str(e)

        def after_preview(code: int, out: str):
            txt.insert(tk.END, out + f"\n\nCódigo {code}\n")
            txt.see(tk.END)
            if code == 0:
                btn_apply.configure(state=tk.NORMAL)
            else:
                txt.insert(tk.END, "\n⚠ Simulación con errores — no se habilita aplicar.\n")

        def worker_preview():
            code, out = run_cmd(False)
            self.after(0, lambda: after_preview(code, out))

        def do_apply():
            if not messagebox.askyesno(
                "Confirmar",
                "Se escribirán datos en MariaDB.\n"
                "Trabajadores nuevos se insertan; producción de la semana se agrega "
                "(duplicados se omiten).\n¿Continuar?",
                parent=win,
            ):
                return
            btn_apply.configure(state=tk.DISABLED)
            txt.insert(tk.END, "\n--- APLICANDO ---\n")
            win.update()

            def worker_apply():
                code, out = run_cmd(True)
                def done():
                    txt.insert(tk.END, out + f"\n\nCódigo {code}\n")
                    txt.see(tk.END)
                    if code == 0:
                        messagebox.showinfo("Importación", "Datos aplicados correctamente.", parent=win)
                    else:
                        messagebox.showerror("Importación", "Hubo errores al aplicar. Revisa el log.", parent=win)
                self.after(0, done)

            threading.Thread(target=worker_apply, daemon=True).start()

        btn_apply.configure(command=do_apply)
        # Si el usuario eligió "aplicar" desde el menú, tras preview puede confirmar
        if apply:
            txt.insert(tk.END, "(Solicitaste aplicar: primero verás la simulación.)\n\n")
        threading.Thread(target=worker_preview, daemon=True).start()




    def _startup_lnk_path(self) -> Path:
        startup = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
        return startup / "Fajos Central.lnk"

    def _startup_enabled(self) -> bool:
        try:
            return self._startup_lnk_path().exists()
        except Exception:
            return False

    def _toggle_startup(self) -> None:
        if sys.platform != "win32":
            messagebox.showinfo("Inicio", "Solo disponible en Windows.")
            self.var_startup.set(False)
            return
        try:
            if self.var_startup.get():
                self._create_startup_shortcut()
                messagebox.showinfo("Inicio", "Se agregó Fajos Central al inicio de Windows.")
            else:
                p = self._startup_lnk_path()
                if p.exists():
                    p.unlink()
                messagebox.showinfo("Inicio", "Se quitó del inicio de Windows.")
        except Exception as e:
            self.var_startup.set(self._startup_enabled())
            messagebox.showerror("Inicio", str(e))

    def _create_startup_shortcut(self) -> None:
        startup = self._startup_lnk_path()
        startup.parent.mkdir(parents=True, exist_ok=True)

        def esc(s: str) -> str:
            return s.replace("'", "''")

        start_bat = ROOT / "start.bat"
        ico = ROOT / "app" / "web" / "static" / "logo.ico"
        parts = [
            "$W = New-Object -ComObject WScript.Shell",
            "$S = $W.CreateShortcut('%s')" % esc(str(startup)),
        ]
        if start_bat.exists():
            parts.append("$S.TargetPath = '%s'" % esc(str(start_bat)))
            parts.append("$S.Arguments = ''")
        else:
            venv_w = ROOT / ".venv" / "Scripts" / "pythonw.exe"
            venv_c = ROOT / ".venv" / "Scripts" / "python.exe"
            if venv_w.exists():
                target = str(venv_w)
            elif venv_c.exists():
                target = str(venv_c)
            else:
                target = sys.executable
            args = '"' + str(ROOT / "launcher.py") + '"'
            parts.append("$S.TargetPath = '%s'" % esc(target))
            parts.append("$S.Arguments = '%s'" % esc(args))
        parts.append("$S.WorkingDirectory = '%s'" % esc(str(ROOT)))
        parts.append("$S.Description = 'Fajos Central'")
        if ico.exists():
            parts.append("$S.IconLocation = '%s,0'" % esc(str(ico)))
        parts.append("$S.Save()")
        ps = "; ".join(parts)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def _run_backup(self, silent: bool = False) -> dict:
        try:
            from app.services.backup_service import BackupService
            cfg = _read_db_ini()
            result = BackupService().backup_cierre(incluir_master=True, db_cfg=cfg)
            if not silent:
                files = ", ".join(result.get("files") or []) or "(ninguno)"
                err = result.get("errors") or []
                msg = "Carpeta:\n%s\n\nArchivos: %s" % (result.get("folder"), files)
                if err:
                    msg += "\n\nAvisos:\n" + "\n".join(str(x) for x in err[:5])
                messagebox.showinfo("Backup", msg)
            return result
        except Exception as e:
            if not silent:
                messagebox.showerror("Backup", str(e))
            return {"ok": False, "errors": [str(e)]}

    def _backup_now(self) -> None:
        self._run_backup(silent=False)

    def _create_desktop_shortcut(self) -> None:
        """Crea acceso directo en el Escritorio (Windows)."""
        if sys.platform != "win32":
            messagebox.showinfo(
                "Acceso directo",
                "Pensado para Windows. En otros sistemas crea un acceso a launcher.py.",
            )
            return
        ps1 = ROOT / "scripts" / "create_desktop_shortcut.ps1"
        try:
            if not ps1.exists():
                messagebox.showerror("Acceso directo", f"No existe:\n{ps1}")
                return
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps1),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = ((r.stdout or "") + (r.stderr or "")).strip()
            if r.returncode == 0:
                messagebox.showinfo(
                    "Acceso directo",
                    "Se creo Fajos Central en el Escritorio.\n\n" + (out or "OK"),
                )
            else:
                messagebox.showerror("Acceso directo", out or f"Codigo {r.returncode}")
        except Exception as e:
            messagebox.showerror("Acceso directo", str(e))

    def _verify_env(self) -> None:
        """Checklist minimo del entorno."""
        lines = [
            ("venv", (ROOT / ".venv" / "Scripts" / "python.exe").exists()),
            ("config.ini", (ROOT / "config.ini").exists()),
            ("app/main.py", (ROOT / "app" / "main.py").exists()),
            ("schema SQL", (ROOT / "db" / "schema").is_dir()),
        ]
        miss = [n for n, ok in lines if not ok]
        msg = "\n".join(("%s  %s" % ("OK" if ok else "FALTA", n)) for n, ok in lines)
        if miss:
            msg += "\n\nPendiente: " + ", ".join(miss)
            if "venv" in miss:
                msg += "\n-> Ejecuta setup_windows.ps1"
            if "config.ini" in miss:
                msg += "\n-> Copia config.ini.example como config.ini"
            messagebox.showwarning("Verificar entorno", msg)
        else:
            messagebox.showinfo("Verificar entorno", msg + "\n\nEntorno basico listo.")

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
            self._refresh_lan_label()
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
        # Backup al cerrar (opcional)
        try:
            if getattr(self, "var_backup", None) and self.var_backup.get():
                self._run_backup(silent=True)
        except Exception:
            pass
        self.destroy()


def main() -> None:
    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
