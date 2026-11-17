"""Adapter and service factories, and the services one process shares
between requests."""

from src.modules.quality.adapters.outbound.external.printer.factory import create_printer_gateway
from src.modules.quality.adapters.outbound.rendering.docket_renderer import DocketRenderer
from src.modules.quality.adapters.outbound.rendering.zpl_rasterizer import ZplRasterizer
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.zpl_rasterizer_port import IZplRasterizer


def get_printer_gateway() -> IPrinterGateway:
    return create_printer_gateway()


def get_zpl_rasterizer() -> IZplRasterizer:
    return ZplRasterizer()


def get_docket_renderer() -> IDocketRenderer:
    return DocketRenderer()
