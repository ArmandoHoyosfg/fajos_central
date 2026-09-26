# Mapa de código — Fajos Central

Actualizado: 3.28.0

```
fajos_central/
├── AGENTS.md                 ← léelo primero si eres una IA
├── VERSION
├── launcher.py               ← GUI Tkinter (Windows)
├── app/
│   ├── main.py               ← FastAPI, migraciones al arranque
│   ├── api/
│   │   ├── routes.py         ← reexporta routers
│   │   ├── helpers.py
│   │   └── routers/          ← UNA área por archivo
│   ├── db/
│   │   ├── connection.py
│   │   ├── migrate.py
│   │   ├── repository.py     ← reexporta repos
│   │   └── repos/            ← UNA tabla/dominio por archivo
│   ├── services/             ← lógica de negocio
│   └── web/
│       ├── templates/
│       ├── static/
│       │   ├── vendor/lucide.min.js  ← íconos OFFLINE
│       │   └── icons/*.svg
│       ├── jinja_ext.py
│       └── templating.py
└── db/schema/                ← migraciones SQL ordenadas
```

## Dependencias entre capas

```
HTML/JS  →  routers  →  services  →  repos  →  MariaDB
                ↓
            templates + static
```

No llames SQL desde templates. No crees tablas desde services (usar `db/schema/`).
