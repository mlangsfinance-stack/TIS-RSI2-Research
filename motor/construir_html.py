"""
Construye las dos páginas de la guía a partir de resultados/metricas.json y resultados/graficos/*.png:
  guia/rsi2-ficha.html        → la estrategia explicada de principio a fin (para el alumno)
  guia/rsi2-validacion.html   → manual avanzado: evolución, método TIS con las fases, robustez, drawdowns, glosario

Antes de construir corre motor/test_resultados.py: si las cifras no son coherentes o falta algo, no se construye.
Uso: python motor/construir_html.py          (--sin-tests para saltarse las pruebas; no recomendado)
"""
import subprocess, sys
from pathlib import Path

if "--sin-tests" not in sys.argv:
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("test_resultados.py"))])
    if r.returncode != 0:
        print("\nNo se construye el HTML: corrige los fallos de arriba (o vuelve a correr el motor)."); sys.exit(1)

from comun import GUIA
from pagina_ficha import ficha
from pagina_manual import manual

if __name__ == "__main__":
    GUIA.mkdir(exist_ok=True)
    (GUIA / "rsi2-ficha.html").write_text(ficha(), encoding="utf-8")
    (GUIA / "rsi2-validacion.html").write_text(manual(), encoding="utf-8")
    for p in GUIA.glob("rsi2-*.html"):
        print(f"{p.name}: {p.stat().st_size/1024:.0f} KB")
