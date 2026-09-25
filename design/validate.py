"""Valida el proyecto PBIP antes de abrirlo en Power BI Desktop.

- Todos los JSON del reporte son válidos.
- Cada tabla, columna o medida que usan los visuales (incluidos los selectores por
  serie) existe en el modelo TMDL.

Uso: python design/validate.py   (sale con código 1 si encuentra problemas)
"""
import json
import re
import sys

from common import MODEL_TABLES, REPORT


def model_objects():
    """{tabla: {columnas y medidas}} leído de los archivos TMDL."""
    model = {}
    for f in MODEL_TABLES.glob("*.tmdl"):
        table, names = None, set()
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^table ('((?:[^']|'')+)'|(\S+))", line)
            if m:
                table = (m.group(2) or m.group(3)).replace("''", "'")
            m = re.match(r"^\t(column|measure) ('((?:[^']|'')+)'|([^\s=]+))", line)
            if m:
                names.add((m.group(3) or m.group(4)).replace("''", "'"))
        model[table] = names
    return model


def references(node):
    """Recorre un visual.json y devuelve (tabla, campo) de cada columna o medida referenciada."""
    if isinstance(node, dict):
        for kind in ("Column", "Measure"):
            ref = node.get(kind)
            if isinstance(ref, dict) and "Property" in ref:
                entity = ref.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if entity:
                    yield entity, ref["Property"]
        for value in node.values():
            yield from references(value)
    elif isinstance(node, list):
        for value in node:
            yield from references(value)


def main():
    problems = []
    for f in REPORT.rglob("*.json"):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"JSON inválido: {f.relative_to(REPORT)}: {e}")
    model = model_objects()
    count = 0
    for f in (REPORT / "definition" / "pages").glob("*/visuals/*/visual.json"):
        content = f.read_text(encoding="utf-8")
        refs = list(references(json.loads(content)))
        refs += [tuple(sel.split(".", 1)) for sel in re.findall(r'"metadata": "([^"]+)"', content)]
        for entity, prop in refs:
            count += 1
            if prop not in model.get(entity, ()):
                problems.append(f"No existe {entity}[{prop}] (visual {f.parent.name})")
    print(f"referencias revisadas: {count}")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problemas")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
