# Fajos Central — Sistema de Nóminas

**Versión:** 3.21.1  
**Licencia:** [GPL-3.0-or-later](LICENSE)  
**Entorno:** Windows + PowerShell 7 + MariaDB/HeidiSQL  

Sistema de nóminas del **Taller de Fajos Central** (áreas **Plata**, **Pita** y **Taller**).

## Qué incluye

- **Launcher** Windows (una sola instancia): iniciar/detener servidor, BD, backup, bandeja, acceso directo
- Interfaz **web** en red local + API REST
- Captura diaria (gramos Plata, efectivo Pita, sueldos Taller)
- **Suministro del día**: hoja tipo papel (fecha/día impresos, avances configurables, filas extra para folio nuevo)
- Export formal Excel/CSV/PDF, captura manual semanal, Excel Master
- Catálogos de materiales/tarifas y modelos desde la BD
- Gestión de **semanas**, avisos, rarezas, temas Oscuro / Claro / Taller
- Sección **Dev** de diagnóstico

---

## Arranque rápido (tu PC)

```powershell
cd .\Documents\Proyectos Desarrollo\fajos_central\

# Primera vez
pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
# Si sale 'not digitally signed', ese Bypass es obligatorio.
# Alternativa: doble clic en setup_windows.cmd
copy config.ini.example config.ini
# Edita usuario/clave de MariaDB en config.ini o en el launcher

# Acceso directo en el Escritorio
pwsh -File .\scripts\create_desktop_shortcut.ps1

# Verificar entorno
pwsh -File .\scripts\verify_env.ps1

# Abrir centro de control (cualquiera)
.\start.bat
python .\launcher.py
```

> Solo puede haber **un launcher** a la vez. Si abres otro, verás un aviso y se cerrará.

Abre en el navegador: `http://127.0.0.1:8000` (o la IP LAN que muestra el launcher).

---

## Suministro diario (Plata)

1. En **Plata** → **Suministro día** (o `/suministro`).
2. Ajusta en la barra:
   - **Avances** (2–6 columnas para gramos del día)
   - **Filas extra** por trabajador (folio nuevo)
   - **Papel**: Carta / Oficio / A4 (**vertical**)
   - **Colores** orientados a tóner (cian, magenta, amarillo, etc.)
   - Máximo 10 columnas en la hoja
   - **Letra**: chica / normal / grande
   - **Colores**: por material o claro (ahorro de tóner)
   - Mostrar u ocultar Modelo / Material / Observaciones
3. **Imprimir** o **Descargar Excel** (mismas opciones).

Los gramos se digitalizan después con **＋ Un día** o en las celdas de la tabla.

---

## Configuración

- `config.ini` — conexión MariaDB y preferencias del launcher  
- `config.ini.example` — plantilla  

## Documentación útil

- `docs/USO.md` — uso diario  
- `CHANGELOG.md` — historial de versiones  
- `LICENSE` — GNU GPL v3 o posterior  

## Licencia

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la **GNU General Public License v3** o, a tu opción, cualquier versión posterior.  
Ver el archivo [LICENSE](LICENSE) y <https://www.gnu.org/licenses/>.

```
SPDX-License-Identifier: GPL-3.0-or-later
```
