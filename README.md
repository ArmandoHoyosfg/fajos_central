# Fajos Central — Sistema de Nóminas

**Versión:** 3.22.0  
**Licencia:** [GPL-3.0-or-later](LICENSE)  
**Entorno:** Windows 10/11 · PowerShell 7 · Python 3.12+ · MariaDB / HeidiSQL  

Sistema de nóminas del **Taller de Fajos Central** para las áreas **Plata**, **Pita** y **Taller**.  
Captura diaria, impresión de suministro, exportación formal, catálogos, semanas y herramientas de diagnóstico.

---

## Contenido

1. [Qué incluye](#qué-incluye)
2. [Requisitos](#requisitos)
3. [Instalación y arranque](#instalación-y-arranque)
4. [Uso diario](#uso-diario)
5. [Áreas de nómina](#áreas-de-nómina)
6. [Suministro del día](#suministro-del-día)
7. [Exportaciones](#exportaciones)
8. [Launcher y bandeja](#launcher-y-bandeja)
9. [Configuración](#configuración)
10. [Sección Dev](#sección-dev)
11. [Estructura del proyecto](#estructura-del-proyecto)
12. [Documentación](#documentación)
13. [Licencia](#licencia)

---

## Qué incluye

| Módulo | Descripción |
|--------|-------------|
| **Launcher** | Centro de control (Tk): una sola instancia, iniciar/detener servidor, BD, backup, bandeja del sistema |
| **Web local** | Interfaz en red local (`http://IP:8000`) + API REST |
| **Plata** | Folios, modelos, materiales, gramos por día, cierre de día/semana |
| **Pita** | Modelo distinto, material tipo PITA NxN, producto, pitas, efectivo |
| **Taller** | Sueldo fijo/variable, extras, torcedores (precio por pita), totales de gran total |
| **Suministro** | Hoja imprimible del día (ajustes de columnas, modo genérico, temas de tóner) |
| **Catálogos** | Materiales, tarifas y modelos: sugieren valores y tarifas; la captura admite texto libre |
| **Semanas** | Crear, duplicar (todas las áreas), alinear, editar, eliminar vacías |
| **Inteligencia ligera** | Folios inactivos, duplicados, rarezas, avisos de consistencia |
| **Dev** | Diagnóstico, sync, huérfanos, migraciones, aprendizaje |
| **Temas UI** | Oscuro · Claro · Taller |

---

## Requisitos

- **Windows** 10 u 11 (PowerShell 7 recomendado)
- **Python** 3.12 o superior (no uses el Python embebido de otras apps en el PATH)
- **MariaDB** (o MySQL compatible) con la base `fajos_central`
- Navegador moderno (Chrome, Edge, Firefox)

---

## Instalación y arranque

```powershell
cd ".\Documents\Proyectos Desarrollo\fajos_central\"

# Primera vez — crea venv e instala dependencias
pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
# Si el script no está firmado, el Bypass es necesario.
# Alternativa: doble clic en setup_windows.cmd (si existe)

# Configuración de base de datos
copy config.ini.example config.ini
# Edita host, usuario, contraseña y database en config.ini
# (también puedes editarlo desde el launcher)

# Acceso directo en el Escritorio (opcional)
pwsh -File .\scripts\create_desktop_shortcut.ps1

# Comprobar entorno
pwsh -File .\scripts\verify_env.ps1

# Abrir el centro de control
.\start.bat
# o:
python .\launcher.py
```

1. En el launcher: **Iniciar servidor** (debe pasar a verde).
2. Abre el navegador en la URL que muestra el launcher, por ejemplo:
   - Local: `http://127.0.0.1:8000`
   - Red: `http://192.168.x.x:8000` (otros equipos de la misma LAN)

> **Una sola instancia:** si abres el launcher dos veces, el segundo se cierra con un aviso.  
> Así se evitan dos iconos en la bandeja y dos servidores.

---

## Uso diario

1. **Abrir** el launcher → iniciar servidor (si no arranca solo).
2. Revisar el **Dashboard**: avisos del día, semana, folios sin avance.
3. **Plata / Pita / Taller:** capturar el día (gramos, efectivo, sueldos).
4. Opcional: imprimir **Suministro del día**, anotar a mano y digitalizar después.
5. Al terminar la jornada: **Cerrar hoy** (resumen de quién falta).
6. Al terminar la semana: **Cerrar semana** y exportar nómina formal para firmas.

### Atajos útiles en la web

| Acción | Dónde |
|--------|--------|
| Solo hoy | Filtro de captura del día actual |
| Un día | Alta rápida de gramos (varios avances que se suman) |
| Duplicar semana | Copia trabajos a la siguiente (todas las áreas) |
| Catálogos | Materiales, precios y modelos |
| Buscar | Trabajadores y líneas de nómina |

---

## Áreas de nómina

### Plata
- Columnas típicas: nombre, ubic, modelo, folio, material, gramos por día, total $, firma.
- Colores por material en pantalla y en export.
- Folios se pueden marcar terminados, reactivar o finalizar por lote si llevan semanas inactivos.

### Pita
- Modelo propio del área; material tipo `PITA 6X6`, etc.; producto (p. ej. Cinturón); pitas; efectivo.
- Solo se exportan filas con datos (regla: en 0 no sale en el Excel).

### Taller
- Sueldo **fijo** o **variable** (al duplicar semana, los fijos se copian; los variables quedan en blanco).
- Extras, total y firma.
- **Torcedores:** línea aparte; total según número de pitas × tarifa (p. ej. 3.2).
- El **gran total** de todo el taller va al pie de la exportación de taller.

Los trabajadores viven en un solo catálogo; las vistas se filtran por área.

---

## Suministro del día

Ruta: **Plata → Suministro día** o `/suministro`.

Formato para **anotar gramos a mano** (fecha y día ya van impresos).

### Opciones de la barra

| Opción | Valores |
|--------|---------|
| **Avances** | 2 a **10** columnas (Av1…Av10) |
| **Filas extra** | 0–4 filas en blanco por trabajador (folio nuevo) |
| **Papel** | Carta · Oficio · A4 (**vertical / retrato**) |
| **Letra** | Muy chica → Muy grande |
| **Colores / tóner** | Por material · Claro · Cian · Magenta · Amarillo · Verde · Gris |
| **Columnas** | Folio · Modelo · Material · Observaciones (mostrar/ocultar) |
| **Modo genérico** | Solo **UBIC + NOMBRE** rellenos; resto en blanco; cada nombre se repite **N** veces |
| **Repeticiones** | 1×–10× por nombre (solo modo genérico) |

**Imprimir** y **Descargar Excel** usan las mismas opciones.  
Las columnas UBIC / MAT / MODELO son compactas para dar más espacio a los avances.

---

## Exportaciones

- **Nómina formal** por área (Plata / Pita / Taller), lista para firma.
- **Captura manual** semanal en blanco (con precio/g y filas extra).
- **Suministro diario** (Excel o impresión desde el navegador).
- **Excel Master** de toda la base (trabajadores, producción, catálogos).
- Export de catálogo de **trabajadores**.

Regla fija: **filas en 0 no se exportan** (Pita y formales equivalentes). Antes de exportar puede mostrarse un aviso.

---

## Launcher y bandeja

- Iniciar / detener el servidor web.
- Probar conexión a la base de datos.
- Editar datos de conexión.
- Backup al cerrar (opcional).
- Minimizar a la **bandeja del sistema** (menú al hacer clic en el icono).
- Preferencia de mantener el icono en la barra de tareas.
- Muestra **versión** e **IP local** para otros equipos en la red.

`start.bat` / `start_startup.vbs` arrancan sin consola. **Inicio con Windows** usa `wscript` + `start_startup.vbs` (no un `.bat`, que abriría cmd).

---

## Configuración

Archivo principal: **`config.ini`** (copia desde `config.ini.example`).

```ini
[database]
host = localhost
port = 3306
user = root
password =
database = fajos_central

[app]
host = 0.0.0.0
port = 8000
```

También hay preferencias del launcher (bandeja, backup, etc.) en la misma config o en la UI del launcher.

Scripts útiles:

| Script | Uso |
|--------|-----|
| `setup_windows.ps1` | Entorno y dependencias |
| `scripts/verify_env.ps1` | Comprobar Python, venv, pip |
| `scripts/create_desktop_shortcut.ps1` | Acceso directo |
| `scripts/import_excel.py` | Importar datos desde Excel |
| `db/` o scripts SQL | Esquema / datos iniciales (HeidiSQL) |

---

## Sección Dev

Ruta: `/dev` (enlace **Dev** en la barra superior).

- Estado de BD y versión.
- Sync de nombres/ubic entre catálogo y nóminas.
- Huérfanos, desajustes, folios repetidos.
- Migraciones / columnas esperadas.
- Crear semana actual, reparar, aprendizaje ligero.
- Enlaces a la API (`/docs`).

---

## Estructura del proyecto

```
fajos_central/
├── launcher.py          # Centro de control (Tk)
├── start.bat / start.ps1
├── setup_windows.ps1
├── config.ini.example
├── VERSION
├── LICENSE              # GPL-3.0-or-later
├── app/
│   ├── main.py          # FastAPI
│   ├── api/             # Rutas web y API
│   ├── db/              # Conexión y repositorios
│   ├── services/        # Lógica (export, día, consistencia…)
│   ├── web/             # Plantillas, estáticos, Dev
│   └── core/            # Config, calendario, instancia única…
├── scripts/
├── docs/
├── tests/
└── db/                  # SQL de esquema / carga (si aplica)
```

---

## Documentación

| Archivo | Contenido |
|---------|-----------|
| [docs/USO.md](docs/USO.md) | Uso diario orientado al operador |
| [docs/ESQUEMA.md](docs/ESQUEMA.md) | Modelo de datos |
| [docs/ARCHIVOS_RAIZ.md](docs/ARCHIVOS_RAIZ.md) | Qué hace cada archivo de la raíz |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |
| [LICENSE](LICENSE) | Texto completo GPL-3.0 |

---

## Licencia

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la **GNU General Public License versión 3** o, a tu opción, cualquier versión posterior.

Ver [LICENSE](LICENSE) y <https://www.gnu.org/licenses/>.

```
SPDX-License-Identifier: GPL-3.0-or-later
```
