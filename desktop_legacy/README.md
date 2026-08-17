# Fajos Central — Sistema de Nóminas

Aplicación de escritorio moderna para gestionar nóminas del **Taller de Fajos Central**.

- **Python 3.10+**
- **PySide6** (interfaz moderna oscura)
- **MariaDB / MySQL**
- Importar / Exportar Excel potenciado

## Instalación

```bash
cd fajos_app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Edita `config.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "TU_CLAVE",
    "database": "fajos_central",
    ...
}
```

Asegúrate de haber ejecutado antes el script SQL `fajos_central_mariadb.sql` en HeidiSQL.

## Ejecutar

```bash
python main.py
```

## Estructura del proyecto

```
fajos_app/
├── main.py                 # Punto de entrada
├── config.py               # Configuración
├── requirements.txt
├── db/
│   ├── connection.py       # Conexión singleton
│   └── repository.py       # Repositorios (CRUD)
├── services/
│   └── excel_service.py    # Import / Export Excel
└── ui/
    ├── main_window.py
    ├── styles.py           # Tema oscuro moderno
    ├── workers_widget.py
    ├── production_widget.py
    └── summary_widget.py
```

## Funcionalidades

| Módulo | Qué hace |
|--------|----------|
| **Trabajadores** | Alta, listado, desactivar. Mismo nombre + distinta Ubic = personas distintas |
| **Producción / Nómina** | Crear semanas, capturar gramos diarios, totales automáticos, importar CSV/Excel, exportar Nómina Formal y hoja de captura |
| **Resumen** | Totales PLT + PIT + TLL por semana |

## Flujo típico

1. Crear semana en **Producción**
2. Agregar líneas (trabajador, folio, modelo, gramos por día)
3. Exportar **Nómina Formal** para firmar
4. En **Resumen** → calcular PLT automático y guardar PIT/TLL
