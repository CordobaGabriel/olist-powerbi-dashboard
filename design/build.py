"""Regenera todo en orden: medidas del modelo -> fondos -> páginas del reporte -> validación.

Uso: python design/build.py [--forzar]
Requiere Power BI Desktop cerrado (--forzar lo saltea, por ejemplo sobre una copia).
"""
import build_backgrounds
import build_model_extras
import build_report
import validate
from common import ensure_power_bi_closed

if __name__ == "__main__":
    ensure_power_bi_closed()
    build_model_extras.main()
    build_backgrounds.main()
    build_report.main()
    validate.main()
