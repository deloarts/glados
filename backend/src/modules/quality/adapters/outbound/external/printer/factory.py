"""
Builds the printer gateway from the deployment config, so the request path
and the auto-print worker refuse the same internal subnets.
"""

from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.quality.adapters.outbound.external.printer.dispatching_printer_gateway import (
    DispatchingPrinterGateway,
)
from src.modules.quality.adapters.outbound.external.printer.guarded_printer_gateway import (
    GuardedPrinterGateway,
)
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway


def create_printer_gateway() -> IPrinterGateway:
    return GuardedPrinterGateway(DispatchingPrinterGateway(), cfg.network.internal_subnets)
