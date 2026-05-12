"""
Pragma - Django OCR Invoice Processing System
Author: Pragma Team
Date: 2026-05-11
Description: Protocol definitions (structural interfaces) for service-layer dependencies.
             New services for Entrega 2 must define their signatures here before implementing.
"""

from typing import Any, Protocol


class FacturaQueryable(Protocol):
    """Contrato para buscar facturas por filtros. Cumplido por Factura.objects y mocks."""

    def filter(self, **kwargs) -> Any: ...


class CertificadoQueryable(Protocol):
    """Contrato para buscar certificados bancarios por filtros."""

    def filter(self, **kwargs) -> Any: ...


class DetallePagoManager(Protocol):
    """Contrato para persistir y consultar detalles de pago."""

    def update_or_create(self, **kwargs) -> tuple[Any, bool]: ...


class FacturaDashboardQueryable(Protocol):
    """Contrato mínimo para métricas de facturas en el dashboard."""

    def count(self) -> int: ...


class DetallePagoDashboardQueryable(Protocol):
    """Contrato para métricas agregadas de detalles de pago en el dashboard."""

    def filter(self, **kwargs) -> Any: ...
    def exclude(self, **kwargs) -> Any: ...
    def count(self) -> int: ...
    def values(self, *fields: str) -> Any: ...
    def select_related(self, *fields: str) -> Any: ...
