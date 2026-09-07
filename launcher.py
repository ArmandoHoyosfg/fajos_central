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
ICON_ICO = ROOT / "app" / "web" / "static" / "logo.ico"


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




def _launcher_prefs() -> dict:
    """Preferencias del launcher en config.ini [launcher]."""
    d = {
        "tray_on_minimize": True,
        "tray_notified": False,
    }
    if not CONFIG_INI.exists():
        return d
    cp = configparser.ConfigParser()
    try:
        cp.read(CONFIG_INI, encoding="utf-8")
        if cp.has_section("launcher"):
            sec = cp["launcher"]
            d["tray_on_minimize"] = sec.getboolean("tray_on_minimize", fallback=True)
            d["tray_notified"] = sec.getboolean("tray_notified", fallback=False)
    except Exception:
        pass
    return d


def _save_launcher_prefs(**kwargs) -> None:
    cp = configparser.ConfigParser()
    if CONFIG_INI.exists():
        try:
            cp.read(CONFIG_INI, encoding="utf-8")
        except Exception:
            pass
    if not cp.has_section("launcher"):
        cp.add_section("launcher")
    cur = _launcher_prefs()
    cur.update({k: v for k, v in kwargs.items() if v is not None})
    cp.set("launcher", "tray_on_minimize", "true" if cur.get("tray_on_minimize") else "false")
    cp.set("launcher", "tray_notified", "true" if cur.get("tray_notified") else "false")
    with CONFIG_INI.open("w", encoding="utf-8") as f:
        cp.write(f)

class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        # Windows: desagrupar de python.exe e ícono propio en la barra de tareas
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "FajosPiteados.Central.Launcher"
                )
            except Exception:
                pass
        super().__init__()
        self.title(f"Fajos Piteados Central — Centro de control  ·  v{APP_VERSION}")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)
        self._tray = None
        self._tray_thread = None
        self._set_window_icon()

        self._server_proc: subprocess.Popen | None = None
        self._server_log = None
        self._poll_job: str | None = None
        self._logo_img = None

        self._apply_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)

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



    def _set_window_icon(self) -> None:
        """Ícono de ventana y barra de tareas (Windows)."""
        try:
            from PIL import Image, ImageTk
        except ImportError:
            Image = ImageTk = None  # type: ignore
        # .ico para barra de título / taskbar
        if ICON_ICO.exists():
            try:
                self.iconbitmap(default=str(ICON_ICO))
                self.wm_iconbitmap(str(ICON_ICO))
            except Exception:
                pass
        # iconphoto refuerza en algunos temas de Windows 11
        src = LOGO_PATH if LOGO_PATH.exists() else (ICON_ICO if ICON_ICO.exists() else None)
        if src is not None and Image is not None:
            try:
                img = Image.open(src).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                self._icon_photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._icon_photo)
            except Exception:
                pass

    def _tray_image(self):
        from PIL import Image
        if ICON_ICO.exists():
            return Image.open(ICON_ICO).resize((64, 64))
        if LOGO_PATH.exists():
            return Image.open(LOGO_PATH).resize((64, 64))
        # fallback generated
        img = Image.new("RGBA", (64, 64), (30, 41, 59, 255))
        return img

    def _start_tray(self) -> None:
        self._hide_to_tray(from_minimize=False)

    def _save_tray_pref(self) -> None:
        try:
            _save_launcher_prefs(tray_on_minimize=bool(self.var_tray_minimize.get()))
        except Exception:
            pass

    def _on_map(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        self._minimizing = False

    def _on_unmap(self, event=None) -> None:
        """Si el usuario minimiza y tiene la opción activa → bandeja."""
        if event is not None and event.widget is not self:
            return
        try:
            if self.state() != "iconic":
                return
        except Exception:
            return
        if getattr(self, "_force_iconic", False):
            return
        if not getattr(self, "var_tray_minimize", None):
            return
        if not self.var_tray_minimize.get():
            return
        # Evitar reentrada
        if getattr(self, "_minimizing", False):
            return
        self._minimizing = True
        self.after(80, lambda: self._hide_to_tray(from_minimize=True))

    def _ensure_tray_icon(self) -> bool:
        """Crea el icono de bandeja con menú amplio. True si ok."""
        try:
            import pystray
            from pystray import MenuItem as Item
            from pystray import Menu
        except ImportError:
            messagebox.showinfo(
                "Bandeja del sistema",
                "Falta el paquete pystray.\n\n"
                "En PowerShell:\n"
                "  .venv\\Scripts\\pip install pystray\n\n"
                "Mientras tanto se minimiza a la barra de tareas.",
            )
            return False

        if self._tray is not None:
            return True

        def show(icon=None, item=None):
            self.after(0, self._show_from_tray)

        def start_srv(icon=None, item=None):
            self.after(0, self._start_server)

        def stop_srv(icon=None, item=None):
            self.after(0, self._stop_server)

        def open_web(icon=None, item=None):
            self.after(0, self._open_browser)

        def open_api(icon=None, item=None):
            self.after(0, self._open_api_docs)

        def do_backup(icon=None, item=None):
            self.after(0, self._backup_now)

        def open_folder(icon=None, item=None):
            self.after(0, self._open_folder)

        def quit_app(icon=None, item=None):
            self.after(0, self._quit_from_tray)

        menu = Menu(
            Item("Mostrar centro de control", show, default=True),
            Menu.SEPARATOR,
            Item("Iniciar servidor web", start_srv),
            Item("Detener servidor web", stop_srv),
            Item("Abrir en el navegador", open_web),
            Item("Documentación API", open_api),
            Menu.SEPARATOR,
            Item("Backup ahora", do_backup),
            Item("Abrir carpeta del proyecto", open_folder),
            Menu.SEPARATOR,
            Item("Salir", quit_app),
        )
        icon = pystray.Icon(
            "fajos_central",
            self._tray_image(),
            "Fajos Central v%s" % APP_VERSION,
            menu,
        )
        self._tray = icon

        def run_tray():
            try:
                icon.run()
            except Exception:
                pass

        self._tray_thread = threading.Thread(target=run_tray, daemon=True)
        self._tray_thread.start()
        return True

    def _hide_to_tray(self, from_minimize: bool = False) -> None:
        """Oculta el launcher en la bandeja del sistema."""
        if not self._ensure_tray_icon():
            if from_minimize:
                # Preferencia activa pero sin pystray: dejar minimizado en barra
                return
            self.iconify()
            return

        # Aviso la primera vez
        prefs = _launcher_prefs()
        if not prefs.get("tray_notified"):
            try:
                messagebox.showinfo(
                    "Fajos Central — Bandeja",
                    "La ventana quedará en el área de notificación "
                    "(flecha ^ junto al reloj).\n\n"
                    "• Clic en el icono o clic derecho → menú\n"
                    "• «Mostrar centro de control» para volver\n\n"
                    "Si prefieres que al minimizar siga en la barra de tareas,\n"
                    "desmarca la opción en Sistema.",
                )
                _save_launcher_prefs(tray_notified=True)
            except Exception:
                pass

        self.withdraw()

    def _show_from_tray(self) -> None:
        self._minimizing = False
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.state("normal")
        except Exception:
            pass

    def _quit_from_tray(self) -> None:
        try:
            if self._tray is not None:
                self._tray.stop()
        except Exception:
            pass
        self._tray = None
        self._on_close()

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
        prefs = _launcher_prefs()
        self.var_backup = tk.BooleanVar(value=True)
        self.var_startup = tk.BooleanVar(value=self._startup_enabled())
        self.var_tray_minimize = tk.BooleanVar(value=bool(prefs.get("tray_on_minimize", True)))
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
        ttk.Checkbutton(
            sysf,
            text="Al minimizar → bandeja (desmarca para dejar en la barra de tareas)",
            variable=self.var_tray_minimize,
            command=self._save_tray_pref,
        ).pack(anchor=tk.W, pady=(4, 0))

        sys_btns = ttk.Frame(sysf)
        sys_btns.pack(fill=tk.X, pady=(10, 0))
        for txt, cmd in (
            ("📌 Acceso directo", self._create_desktop_shortcut),
            ("🔽 Bandeja", self._hide_to_tray),
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
        """Proceso hijo vivo (no implica que el puerto responda)."""
        return self._server_proc is not None and self._server_proc.poll() is None

    def _server_healthy(self) -> bool:
        """Verde solo si el proceso vive y el puerto acepta conexiones."""
        if not self._is_running():
            return False
        return self._port_open()

    def _kill_port_occupants(self, port: int) -> None:
        """Libera el puerto de instancias previas (Windows/Linux)."""
        try:
            if sys.platform == "win32":
                # netstat -ano | findstr :PORT
                r = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                pids = set()
                for line in (r.stdout or "").splitlines():
                    if f":{port}" not in line:
                        continue
                    if "LISTENING" not in line.upper() and "ESCUCHA" not in line.upper():
                        # también conexiones en algunos locales
                        if "LISTEN" not in line.upper():
                            continue
                    parts = line.split()
                    if not parts:
                        continue
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) > 0:
                        pids.add(pid)
                for pid in pids:
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
            else:
                subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True,
                    check=False,
                )
        except Exception:
            pass

    def _refresh_lan_label(self) -> None:
        try:
            port = _port()
            scheme = "https" if _ssl_files() else "http"
            ip = _local_ip()
            url = f"{scheme}://{ip}:{port}"
            local = f"{scheme}://127.0.0.1:{port}"
            self.lbl_lan.configure(text=f"Red local (otros equipos):  {url}")
            self._lan_url = url
            self._local_url = local
            if hasattr(self, "lbl_url"):
                try:
                    self.lbl_url.configure(text=f"URL: {local}")
                except Exception:
                    pass
        except Exception:
            self.lbl_lan.configure(text="Red local: —")
            self._lan_url = ""
            self._local_url = ""

    def _copy_lan_url(self) -> None:
        url = getattr(self, "_lan_url", "") or getattr(self, "_local_url", "") or ""
        if not url:
            messagebox.showinfo("URL", "No hay URL disponible. Inicia el servidor primero.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()
            messagebox.showinfo("URL", f"Copiada:\n{url}")
        except Exception as e:
            messagebox.showerror("URL", str(e))

    def _start_server(self) -> None:
        if self._server_healthy():
            messagebox.showinfo("Servidor", "Ya está en ejecución y respondiendo.")
            return
        # Limpiar proceso zombie o puerto ocupado
        if self._is_running():
            self._stop_server()
        else:
            self._server_proc = None

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

        port = _port()
        self.lbl_status.configure(text="● Liberando puerto…", foreground="#f9e2af")
        self.update_idletasks()
        self._kill_port_occupants(port)
        time.sleep(0.4)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        d = _read_db_ini()
        env["FAJOS_DB_HOST"] = str(d["host"])
        env["FAJOS_DB_PORT"] = str(d["port"])
        env["FAJOS_DB_USER"] = str(d["user"])
        env["FAJOS_DB_PASSWORD"] = str(d["password"])
        env["FAJOS_DB_NAME"] = str(d["database"])
        env["FAJOS_APP_HOST"] = str(d["app_host"])
        env["FAJOS_APP_PORT"] = str(d["app_port"])

        # Sin --reload desde el launcher: más estable en Windows
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            _host_bind(),
            "--port",
            str(port),
        ]
        ssl = _ssl_files()
        if ssl:
            cmd.extend(["--ssl-certfile", ssl[0], "--ssl-keyfile", ssl[1]])
            env["FAJOS_FORCE_HTTPS"] = "true"

        try:
            log_path = ROOT / "logs" / "server_launcher.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_f = open(log_path, "a", encoding="utf-8")
            log_f.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_f.write("cmd: " + " ".join(cmd) + "\n")
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
            self._update_status()
            return

        self.lbl_status.configure(text="● Arrancando…", foreground="#f9e2af")
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self._refresh_lan_label()
        threading.Thread(target=self._wait_until_ready, daemon=True).start()

    def _wait_until_ready(self) -> None:
        """Espera salud real; si falla, limpia y avisa."""
        ok = False
        for _ in range(60):  # ~15 s
            if self._server_proc is not None and self._server_proc.poll() is not None:
                break
            if self._port_open():
                ok = True
                break
            time.sleep(0.25)

        def finish() -> None:
            if ok:
                self._update_status()
                self._open_browser()
            else:
                # proceso muerto o puerto sin respuesta
                log_tail = self._read_log_tail()
                self._stop_server()
                msg = (
                    "El servidor no respondió a tiempo en el puerto "
                    f"{_port()}.\n\nRevisa logs/server_launcher.log"
                )
                if log_tail:
                    msg += "\n\nÚltimas líneas:\n" + log_tail[-800:]
                messagebox.showerror("Servidor", msg)
                self._update_status()

        self.after(0, finish)

    def _read_log_tail(self, lines: int = 25) -> str:
        try:
            p = ROOT / "logs" / "server_launcher.log"
            if not p.exists():
                return ""
            data = p.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(data[-lines:])
        except Exception:
            return ""

    def _port_open(self) -> bool:
        import socket

        try:
            with socket.create_connection(("127.0.0.1", _port()), timeout=0.4):
                return True
        except OSError:
            return False

    def _stop_server(self) -> None:
        proc = self._server_proc
        port = _port()
        try:
            if proc is not None and proc.poll() is None:
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
            messagebox.showwarning("Aviso", str(e))
        finally:
            if self._server_log:
                try:
                    self._server_log.close()
                except Exception:
                    pass
                self._server_log = None
            self._server_proc = None
            # Por si quedó huérfano en el puerto
            self._kill_port_occupants(port)
            self._update_status()

    def _open_browser(self) -> None:
        # Preferir 127.0.0.1 (misma máquina); no "localhost" ambiguo
        url = getattr(self, "_local_url", None) or _base_url()
        if not self._port_open():
            messagebox.showwarning(
                "Navegador",
                "El servidor no está respondiendo aún.\n"
                f"Prueba manualmente: {url}",
            )
            return
        webbrowser.open(url)

    def _open_api_docs(self) -> None:
        url = (getattr(self, "_local_url", None) or _base_url()) + "/docs"
        if not self._port_open():
            messagebox.showwarning("API", "Inicia el servidor primero.")
            return
        webbrowser.open(url)

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
                messagebox.showinfo("Inicio", "Se agregó Fajos Central al inicio de Windows (sin consola).\nSi antes veías una ventana negra, desactiva y vuelve a activar esta opción.")
            else:
                p = self._startup_lnk_path()
                if p.exists():
                    p.unlink()
                messagebox.showinfo("Inicio", "Se quitó del inicio de Windows.")
        except Exception as e:
            self.var_startup.set(self._startup_enabled())
            messagebox.showerror("Inicio", str(e))

    def _create_startup_shortcut(self) -> None:
        """Acceso en Startup sin consola: wscript → start_startup.vbs → pythonw."""
        startup = self._startup_lnk_path()
        startup.parent.mkdir(parents=True, exist_ok=True)

        def esc_ps(s: str) -> str:
            """Escape for PowerShell single-quoted string."""
            return str(s).replace("'", "''")

        ico = ROOT / "app" / "web" / "static" / "logo.ico"
        vbs = ROOT / "start_startup.vbs"
        silent = ROOT / "start_silent.vbs"
        venv_w = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        launcher = ROOT / "launcher.py"

        # Construir TargetPath + Arguments sin romper comillas de Python
        if vbs.exists():
            target = "wscript.exe"
            arguments = "//nologo " + str(vbs)
        elif silent.exists() and venv_w.exists():
            target = "wscript.exe"
            arguments = "//nologo {0} {1} {2}".format(silent, venv_w, launcher)
        elif venv_w.exists():
            target = str(venv_w)
            arguments = str(launcher)
        else:
            exe = sys.executable
            if exe.lower().endswith("python.exe"):
                cand = Path(exe).with_name("pythonw.exe")
                if cand.exists():
                    exe = str(cand)
            target = exe
            arguments = str(launcher)

        # Shortcut WindowStyle: 1=normal, 3=max, 7=minimized
        lines = [
            "$W = New-Object -ComObject WScript.Shell",
            "$S = $W.CreateShortcut('{0}')".format(esc_ps(startup)),
            "$S.TargetPath = '{0}'".format(esc_ps(target)),
            "$S.Arguments = '{0}'".format(esc_ps(arguments)),
            "$S.WorkingDirectory = '{0}'".format(esc_ps(ROOT)),
            "$S.WindowStyle = 7",
            "$S.Description = 'Fajos Central (sin consola)'",
        ]
        if ico.exists():
            lines.append("$S.IconLocation = '{0},0'".format(esc_ps(ico)))
        lines.append("$S.Save()")
        ps = "; ".join(lines)
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
        healthy = False
        try:
            healthy = self._server_healthy()
        except Exception:
            healthy = False

        if healthy:
            self.lbl_status.configure(text="● En ejecución", foreground="#a6e3a1")
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
            self._refresh_lan_label()
        elif self._is_running():
            self.lbl_status.configure(text="● Arrancando…", foreground="#f9e2af")
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.lbl_status.configure(text="● Detenido", foreground="#f38ba8")
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            if self._server_proc is not None and self._server_proc.poll() is not None:
                self._server_proc = None
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
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
    from app.core.single_instance import acquire_lock

    # Solo un launcher a la vez (evita dos iconos en bandeja / dos centros de control)
    if not acquire_lock("launcher"):
        try:
            import tkinter as _tk
            from tkinter import messagebox as _mb
            root = _tk.Tk()
            root.withdraw()
            _mb.showinfo(
                "Fajos Central ya está abierto",
                "Ya hay un launcher en ejecución.\n\n"
                "Revisa la bandeja de iconos (junto al reloj) o la barra de tareas.\n"
                "Si no lo ves, cierra procesos huérfanos desde el Administrador de tareas\n"
                "o reinicia el equipo.",
            )
            root.destroy()
        except Exception:
            print("Fajos Central: ya hay un launcher en ejecución.", file=sys.stderr)
        sys.exit(0)

    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
