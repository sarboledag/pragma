"""
Pragma - Django OCR Invoice Processing System
Author: Pragma Team
Date: 2026-03-18
Description: Unit tests for OCR, matching, dashboard, and export services
"""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from pragma.core.models import CertificadoBancario, Cliente, DetallePago, Factura
from pragma.core.services.comparador_pagos import (
    buscar_certificado_candidato,
    buscar_factura_candidata,
    comparar_pagos,
    crear_o_actualizar_detalle_pago,
)
from pragma.core.services.dashboard_service import get_dashboard_metrics
from pragma.core.services.export_service import exportar_excel, exportar_pdf
from pragma.core.services.ocr_service import parse_invoice_text, extract_invoice_data


class ServiceLayerTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nit="1234567-8",
            nombre="Cliente Demo",
            contacto="demo@example.com",
        )
        self.factura = Factura.objects.create(
            numero_factura="FAC-1001",
            monto=Decimal("1500.00"),
            fecha=date(2026, 3, 18),
            cliente_nit="1234567-8",
            cliente=self.cliente,
            archivo=SimpleUploadedFile("factura.pdf", b"%PDF-1.4 fake"),
            ocr_data={},
        )
        self.certificado = CertificadoBancario.objects.create(
            numero_referencia="REF-2001",
            monto=Decimal("1500.00"),
            fecha=date(2026, 3, 18),
            cliente_nit="1234567-8",
            cliente=self.cliente,
            archivo=SimpleUploadedFile("certificado.pdf", b"%PDF-1.4 fake"),
        )

    def test_parse_invoice_text_extracts_fields(self):
        text = (
            "Factura: FAC-9001\n"
            "NIT: 999999-1\n"
            "Total: Q 2500.50\n"
            "Fecha: 18/03/2026\n"
        )
        result = parse_invoice_text(text)
        self.assertEqual(result["numero_factura"], "FAC-9001")
        self.assertEqual(result["cliente_nit"], "999999-1")
        self.assertEqual(result["monto"], Decimal("2500.50"))
        self.assertEqual(str(result["fecha"]), "2026-03-18")
        self.assertEqual(result["errors"], [])

    def test_parse_invoice_text_with_complex_labels(self):
        text = (
            "DOCUMENTO TRIBUTARIO ELECTRÓNICO\n"
            "Serie: 1A2B3C4D\n"
            "Identificación Tributaria: 8888888-8\n"
            "Gran Total a Pagar: $ 1,234.56\n"
            "Fecha de Emisión: 2026-12-31\n"
        )
        result = parse_invoice_text(text)
        self.assertEqual(result["numero_factura"], "1A2B3C4D")
        self.assertEqual(result["cliente_nit"], "8888888-8")
        self.assertEqual(result["monto"], Decimal("1234.56"))
        self.assertEqual(str(result["fecha"]), "2026-12-31")
        self.assertEqual(result["errors"], [])

    def test_parse_invoice_text_with_spanish_long_date(self):
        text = (
            "VALOR TOTAL: Q 5.000,00\n"
            "EMISION: 24 de Marzo de 2026\n"
            "NIT: 1234567-8\n"
        )
        result = parse_invoice_text(text)
        self.assertEqual(result["monto"], Decimal("5000.00"))
        self.assertEqual(str(result["fecha"]), "2026-03-24")
        self.assertEqual(result["cliente_nit"], "1234567-8")

    def test_extract_invoice_data_with_unsupported_format(self):
        csv_file = SimpleUploadedFile("invoice.csv", b"dummy content", content_type="text/csv")
        result = extract_invoice_data(csv_file)
        self.assertTrue(any("Formato no soportado" in error for error in result["errors"]))
        self.assertIsNone(result["numero_factura"])

    def test_comparar_pagos_full_match(self):
        result = comparar_pagos(self.factura, self.certificado)
        self.assertEqual(result["estado_match"], "match")
        self.assertEqual(result["match_score"], Decimal("100.00"))

    def test_comparar_pagos_no_match(self):
        self.certificado.monto = Decimal("99.00")
        self.certificado.cliente_nit = "0000000-0"
        self.certificado.fecha = date(2026, 1, 1)
        result = comparar_pagos(self.factura, self.certificado)
        self.assertEqual(result["estado_match"], "no_match")
        self.assertTrue(result["diferencias"])

    def test_dashboard_metrics(self):
        crear_o_actualizar_detalle_pago(self.factura, self.certificado)
        Factura.objects.create(
            numero_factura="FAC-1002",
            monto=Decimal("500.00"),
            fecha=date(2026, 3, 19),
            cliente_nit="1234567-8",
            cliente=self.cliente,
            archivo=SimpleUploadedFile("factura2.pdf", b"%PDF-1.4 fake"),
            ocr_data={},
        )
        metrics = get_dashboard_metrics()
        self.assertEqual(metrics["total_facturas_procesadas"], 2)
        self.assertEqual(metrics["validaciones_pendientes"], 1)
        self.assertGreaterEqual(metrics["tasa_match_exitoso"], 0)

    def test_export_services_generate_bytes(self):
        detalle = crear_o_actualizar_detalle_pago(self.factura, self.certificado)
        pdf_bytes = exportar_pdf(detalle).getvalue()
        excel_bytes = exportar_excel([detalle]).getvalue()
        self.assertGreater(len(pdf_bytes), 100)
        self.assertGreater(len(excel_bytes), 100)

    def test_crear_o_actualizar_detalle_pago_is_idempotent(self):
        detalle_1 = crear_o_actualizar_detalle_pago(self.factura, self.certificado)
        detalle_2 = crear_o_actualizar_detalle_pago(self.factura, self.certificado)
        self.assertEqual(detalle_1.id, detalle_2.id)
        self.assertEqual(DetallePago.objects.count(), 1)

    def test_buscar_certificado_candidato(self):
        best_cert = buscar_certificado_candidato(self.factura)
        self.assertEqual(best_cert.id, self.certificado.id)


class DependencyInjectionTests(unittest.TestCase):
    """
    Verifica que los servicios aceptan repositorios inyectados.
    No requiere base de datos — demuestra el principio de inversión de dependencias.
    """

    def test_buscar_factura_candidata_usa_repositorio_inyectado(self):
        certificado = MagicMock()
        certificado.cliente_nit = "9999-9"
        certificado.monto = Decimal("1000.00")
        certificado.fecha = date(2026, 1, 1)

        factura_candidata = MagicMock()
        factura_candidata.monto = Decimal("1000.00")
        factura_candidata.fecha = date(2026, 1, 1)

        mock_qs = MagicMock()
        mock_qs.filter.return_value.order_by.return_value = [factura_candidata]

        resultado = buscar_factura_candidata(certificado, factura_qs=mock_qs)

        self.assertEqual(resultado, factura_candidata)
        mock_qs.filter.assert_called_once_with(cliente_nit="9999-9")

    def test_buscar_certificado_candidato_usa_repositorio_inyectado(self):
        factura = MagicMock()
        factura.cliente_nit = "1111-1"
        factura.monto = Decimal("500.00")
        factura.fecha = date(2026, 2, 1)

        cert_candidato = MagicMock()
        cert_candidato.monto = Decimal("500.00")
        cert_candidato.fecha = date(2026, 2, 1)

        mock_qs = MagicMock()
        mock_qs.filter.return_value.order_by.return_value = [cert_candidato]

        resultado = buscar_certificado_candidato(factura, certificado_qs=mock_qs)

        self.assertEqual(resultado, cert_candidato)
        mock_qs.filter.assert_called_once_with(cliente_nit="1111-1")

    def test_crear_o_actualizar_detalle_pago_usa_manager_inyectado(self):
        factura = MagicMock()
        factura.monto = Decimal("800.00")
        factura.cliente_nit = "2222-2"
        factura.fecha = date(2026, 3, 1)

        certificado = MagicMock()
        certificado.monto = Decimal("800.00")
        certificado.cliente_nit = "2222-2"
        certificado.fecha = date(2026, 3, 1)

        mock_detalle = MagicMock()
        mock_manager = MagicMock()
        mock_manager.update_or_create.return_value = (mock_detalle, True)

        resultado = crear_o_actualizar_detalle_pago(
            factura, certificado, detalle_pago_manager=mock_manager
        )

        self.assertEqual(resultado, mock_detalle)
        mock_manager.update_or_create.assert_called_once()

    def test_get_dashboard_metrics_usa_querysets_inyectados(self):
        mock_factura_qs = MagicMock()
        mock_factura_qs.count.return_value = 5

        mock_detalle_qs = MagicMock()
        mock_detalle_qs.count.return_value = 4
        mock_detalle_qs.filter.return_value.count.return_value = 3
        mock_detalle_qs.values.return_value.distinct.return_value.count.return_value = 4

        metrics = get_dashboard_metrics(
            factura_qs=mock_factura_qs,
            detalle_pago_qs=mock_detalle_qs,
        )

        self.assertEqual(metrics["total_facturas_procesadas"], 5)
        self.assertEqual(metrics["validaciones_pendientes"], 1)
        mock_factura_qs.count.assert_called_once()
        mock_detalle_qs.filter.assert_called()
