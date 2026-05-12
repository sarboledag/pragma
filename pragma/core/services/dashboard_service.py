"""
Pragma - Django OCR Invoice Processing System
Author: Pragma Team
Date: 2026-03-18
Description: Dashboard metrics aggregation service
"""

from decimal import Decimal
from typing import Optional

from django.db.models import Count

from pragma.core.models import DetallePago, Factura
from pragma.core.services.protocols import (
    DetallePagoDashboardQueryable,
    FacturaDashboardQueryable,
)


def get_dashboard_metrics(
    factura_qs: Optional[FacturaDashboardQueryable] = None,
    detalle_pago_qs: Optional[DetallePagoDashboardQueryable] = None,
):
    if factura_qs is None:
        factura_qs = Factura.objects
    if detalle_pago_qs is None:
        detalle_pago_qs = DetallePago.objects

    total_facturas = factura_qs.count()
    total_matches = detalle_pago_qs.filter(estado_match="match").count()
    total_comparaciones = detalle_pago_qs.count()

    if total_comparaciones > 0:
        tasa_match_exitoso = round((total_matches / total_comparaciones) * 100, 2)
    else:
        tasa_match_exitoso = 0

    facturas_con_validacion = detalle_pago_qs.values("factura").distinct().count()
    validaciones_pendientes = max(total_facturas - facturas_con_validacion, 0)

    # Estimación: proceso manual ~3h por cliente/factura, automatizado ~0.25h.
    tiempo_ahorrado_horas = Decimal(max(total_facturas * 2.75, 0)).quantize(Decimal("0.01"))

    inconsistencias_recientes = (
        detalle_pago_qs.exclude(estado_match="match")
        .select_related("factura", "certificado")
        .order_by("-created_at")[:5]
    )

    estado_breakdown = (
        detalle_pago_qs.values("estado_match")
        .annotate(total=Count("id"))
        .order_by("estado_match")
    )

    return {
        "total_facturas_procesadas": total_facturas,
        "tasa_match_exitoso": tasa_match_exitoso,
        "validaciones_pendientes": validaciones_pendientes,
        "tiempo_ahorrado_horas": tiempo_ahorrado_horas,
        "inconsistencias_recientes": inconsistencias_recientes,
        "estado_breakdown": estado_breakdown,
    }
