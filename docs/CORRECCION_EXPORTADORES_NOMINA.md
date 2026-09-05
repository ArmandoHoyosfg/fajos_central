# Correccion de exportadores de nomina

## Objetivo

Eliminar los errores JavaScript registrados al usar las paginas `/nomina-pita` y `/nomina-taller`:

```text
Uncaught ReferenceError: exportFormalPita is not defined
Uncaught ReferenceError: exportFormalTaller is not defined
```

La guia describe exactamente que revisar y cambiar para repetir la correccion en otra copia del proyecto.

## Causa raiz

Las plantillas usan herencia Jinja:

```jinja2
{% extends "base.html" %}
...
{% block scripts %}
<script>
// funciones de la pagina
</script>
{% endblock %}
```

En las dos plantillas afectadas, las funciones de exportacion estaban despues de `{% endblock %}`. Ese contenido no formaba parte del bloque `scripts` que `base.html` inserta en el documento final. Por tanto:

1. El boton HTML si se renderizaba.
2. El boton ejecutaba `onclick="exportFormalPita(...)"` o `onclick="exportFormalTaller(...)"`.
3. La funcion no existia en el HTML servido.
4. El navegador producia `ReferenceError` al pulsar el boton.

El mismo problema afectaba a `tllPuestoHint`, usado por `oninput="tllPuestoHint()"` en la pagina de Taller.

## Archivos corregidos

### `app/web/templates/nomina_pita.html`

Cambios realizados:

- Se movio `async function exportFormalPita(semanaId)` al interior de `{% block scripts %}`.
- Se elimino la copia que estaba despues de `{% endblock %}`.
- Se conservaron sin cambios la logica de negocio y los endpoints:
  - Vista previa: `/api/export/nomina-pita/{semana_id}/preview`
  - Descarga: `/api/export/nomina-pita/{semana_id}`
- Se conservaron las reglas existentes:
  - Mostrar cuantas lineas existen.
  - Exportar solo lineas con `efectivo > 0`.
  - Avisar si no hay lineas exportables.
  - Pedir confirmacion antes de descargar.

La correccion no consistia en renombrar la funcion ni en cambiar el boton: consistia en colocar la definicion en el bloque que realmente se renderiza.

### `app/web/templates/nomina_taller.html`

Cambios realizados:

- Se movio `function tllPuestoHint()` al interior de `{% block scripts %}`.
- Se movio `async function exportFormalTaller(semanaId)` al interior de `{% block scripts %}`.
- Se eliminaron las copias que estaban despues de `{% endblock %}`.
- Se conservaron sin cambios la logica de negocio y los endpoints:
  - Vista previa: `/api/export/nomina-taller/{semana_id}/preview`
  - Descarga: `/api/export/nomina-taller/{semana_id}`
- Se conservaron las reglas existentes:
  - Exportar solo filas con monto mayor que cero.
  - Mostrar las filas totales, exportables y omitidas.
  - Pedir confirmacion antes de descargar.
  - Resaltar el campo de pitas cuando el puesto contiene `torcedor`.

## Procedimiento para repetir la correccion

1. Buscar los nombres de las funciones y sus usos:

   ```text
   exportFormalPita
   exportFormalTaller
   tllPuestoHint
   ```

2. Abrir la plantilla que contiene cada funcion.

3. Localizar `{% block scripts %}` y su `{% endblock %}` correspondiente.

4. Confirmar que cada funcion usada por un atributo inline (`onclick`, `oninput`, `onsubmit`, `onchange`) esta dentro de ese bloque o dentro de un archivo JavaScript cargado por la pagina.

5. Si una funcion esta despues de `{% endblock %}`:
   - Mover su definicion al bloque `scripts`.
   - Mantener la funcion una sola vez.
   - No cambiar sus endpoints, parametros ni reglas de negocio.
   - No dejar una copia fuera del bloque.

6. Revisar las plantillas hermanas para detectar el mismo patron. En esta revision se encontraron y corrigieron tres funciones en total:
   - `exportFormalPita`.
   - `exportFormalTaller`.
   - `tllPuestoHint`.

7. No incluir en el commit archivos generados o no relacionados, como backups creados durante la ejecucion de la aplicacion.

## Auditoria adicional realizada

Se revisaron las plantillas HTML en busca de scripts colocados despues de un `{% endblock %}`. El unico caso restante fue el script propio de `base.html`, que es intencional porque pertenece a la plantilla base y no a una plantilla hija.

Tambien se revisaron los manejadores inline de las paginas, incluyendo:

- `onclick`.
- `onsubmit`.
- `oninput`.
- `onchange`.

No se encontro otro caso equivalente de una funcion de pagina declarada fuera de su bloque de scripts.

## Validaciones ejecutadas

### Suite de pruebas

Desde la raiz del proyecto:

```powershell
pytest -q
```

Resultado de la correccion original:

```text
19 passed
```

### Sintaxis Jinja

Se cargaron y analizaron las 16 plantillas HTML con Jinja. Todas se pudieron parsear correctamente.

### HTML renderizado

Se renderizaron las dos plantillas afectadas y se comprobo que las funciones aparecieran en el HTML final:

```text
nomina_pita.html OK
nomina_taller.html OK
```

La comprobacion importante es que el nombre de cada funcion exista en la respuesta servida, no solo en el archivo fuente.

### Diff

Tambien se ejecuto:

```powershell
git diff --check
```

Sin errores de formato.

## Commit de referencia

La correccion se publico originalmente con:

```text
a3cc4de Fix payroll export handlers
```

Archivos incluidos en ese commit:

```text
app/web/templates/nomina_pita.html
app/web/templates/nomina_taller.html
```

## Criterio de aceptacion

La correccion se considera completa cuando:

- `/nomina-pita` ya no produce `exportFormalPita is not defined`.
- `/nomina-taller` ya no produce `exportFormalTaller is not defined`.
- El campo de puesto de Taller puede llamar a `tllPuestoHint` sin `ReferenceError`.
- Las funciones aparecen en el HTML renderizado dentro de los scripts de la pagina.
- `pytest -q` termina correctamente.
- El commit contiene solo las plantillas relacionadas, sin backups ni archivos generados.
