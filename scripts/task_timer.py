"""
Cronómetro de tarea para medir el tiempo real de una unidad de trabajo.

Uso rápido (una línea, sin cambiar nada más):

    python scripts/task_timer.py --task "Bloque 1: refrescar PROJECT_STATE"

Uso programático (arranque al importarse, detención al terminar):

    from scripts.task_timer import TaskTimer
    t = TaskTimer("Bloque 1: refrescar PROJECT_STATE")
    ...  # tu trabajo aquí ...
    t.stop()          # imprime el resumen
    t.save("logs")    # opcional: persiste el registro en logs/task_timer_YYYYmmdd.jsonl

Salida (stdout), ejemplo:

    ┌──────────────────────────────────────────────────────────┐
    │  Tarea   : Bloque 1: refrescar PROJECT_STATE
    │  Inicio  : 2026-09-22 10:00:00
    │  Fin     : 2026-09-22 10:03:42
    │  Duración: 3m 42s (222.35 s)
    └──────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# Windows consolas (cp1252) no soportan caracteres unicode de caja/bordes.
# Forzamos UTF-8 en stdout/stderr para que el resumen siempre se imprima bien.
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


def _now() -> datetime:
    return datetime.now().astimezone()


@dataclass
class TaskTimer:
    """Cronómetro de una tarea. Arranca al crearse; se detiene con .stop()."""

    name: str
    # Se inicializa en __post_init__ para que el arranque sea exactamente "ahora".
    _start_perf: float = field(default=None, init=False)
    _start_wall: datetime = field(default=None, init=False)
    _end_perf: float | None = field(default=None, init=False)
    _end_wall: datetime | None = field(default=None, init=False)
    _stopped: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._start_perf = time.perf_counter()
        self._start_wall = _now()

    def stop(self) -> float:
        """Detiene el cronómetro y devuelve la duración en segundos."""
        if not self._stopped:
            self._end_perf = time.perf_counter()
            self._end_wall = _now()
            self._stopped = True
        return self.duration_seconds

    @property
    def duration_seconds(self) -> float:
        end = self._end_perf if self._end_perf is not None else time.perf_counter()
        return max(0.0, end - self._start_perf)

    def report(self) -> str:
        """Devuelve el resumen formateado como cadena (sin imprimir)."""
        dur = self.duration_seconds
        minutes, sec = divmod(int(dur), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            human = f"{hours}h {minutes}m {sec:.0f}s"
        elif minutes:
            human = f"{minutes}m {sec:.0f}s"
        else:
            human = f"{sec:.2f} s"
        bar = "─" * 54
        return (
            "┌" + bar + "┐\n"
            f"│  Tarea   : {self.name}\n"
            f"│  Inicio  : {self._start_wall:%Y-%m-%d %H:%M:%S}\n"
            f"│  Fin     : {(self._end_wall or self._start_wall):%Y-%m-%d %H:%M:%S}\n"
            f"│  Duración: {human} ({dur:.2f} s)\n"
            "└" + bar + "┘"
        )

    def print(self) -> None:
        """Imprime el resumen al stdout."""
        print(self.report())

    def save(self, target_dir: str | Path = "logs") -> Path | None:
        """
        Persiste una línea JSON en <target_dir>/task_timer_YYYYmmdd.jsonl.
        Crea el directorio si no existe. Devuelve la ruta escrita (o None).
        """
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        path = target / f"task_timer_{stamp}.jsonl"
        record = {
            "task": self.name,
            "start": self._start_wall.isoformat(),
            "end": (self._end_wall or _now()).isoformat(),
            "duration_seconds": round(self.duration_seconds, 3),
            "ts": _now().isoformat(),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path


# --- CLI -------------------------------------------------------------------

def _cli(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Mide la duración de una tarea (arranque/detención).",
    )
    p.add_argument("--task", required=True, help="Nombre/etiqueta de la tarea.")
    p.add_argument(
        "--body",
        action="store_true",
        help="Simula un cuerpo de trabajo (para medir overhead real).",
    )
    p.add_argument(
        "--save",
        default=None,
        help="Directorio donde guardar el JSONL (por defecto no guarda).",
    )
    args = p.parse_args(argv)

    t = TaskTimer(args.task)
    if args.body:
        # Mide el overhead de arranque de Python + import de un módulo del proyecto.
        import time as _t
        _t.sleep(0.2)
        try:
            import app.main  # noqa: F401
        except Exception:
            pass  # no importa: solo medimos el tiempo
    t.stop()
    t.print()
    if args.save:
        path = t.save(args.save)
        if path:
            print(f"  registro → {path}")
    return 0


def main() -> int:
    return _cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())