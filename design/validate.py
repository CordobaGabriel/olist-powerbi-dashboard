"""Valida el proyecto PBIP antes de abrirlo en Power BI Desktop.

- Todos los JSON del reporte son válidos.
- Cada tabla, columna o medida que usan los visuales (incluidos los selectores por
  serie) existe en el modelo TMDL.
Sale con código 1 si encuentra problemas.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TABLES = ROOT / "Olist_Dashboard.SemanticModel" / "definition" / "tables"
PAGES = ROOT / "Olist_Dashboard.Report" / "definition" / "pages"


def model_objects():
    model = {}
    for f in TABLES.glob("*.tmdl"):
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
    for f in (ROOT / "Olist_Dashboard.Report").rglob("*.json"):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"JSON inválido: {f.relative_to(ROOT)}: {e}")
    model = model_objects()
    count = 0
    for f in PAGES.glob("*/visuals/*/visual.json"):
        text = f.read_text(encoding="utf-8")
        refs = list(references(json.loads(text)))
        refs += [tuple(sel.split(".", 1)) for sel in re.findall(r'"metadata": "([^"]+)"', text)]
        for entity, prop in refs:
            count += 1
            if prop not in model.get(entity, ()):
                problems.append(f"No existe {entity}[{prop}] ({f.parent.name})")
    print(f"referencias revisadas: {count}")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problemas")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
