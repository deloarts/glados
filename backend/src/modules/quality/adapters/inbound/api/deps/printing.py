"""Use case factories: printers, print templates, print documents/jobs."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_item_picture_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.fulfillment.adapters.inbound.api.deps.facades import get_lot_scrap_records
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.application.facade.lot_scrap_records import LotScrapRecords
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IProductionLotQueries
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.adapters.inbound.api.deps.bindings import get_print_root_resolver
from src.modules.quality.adapters.inbound.api.deps.repositories import get_calculation_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_checklist_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_print_job_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_print_template_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_printer_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_report_journal_repo
from src.modules.quality.adapters.inbound.api.deps.services import get_docket_renderer
from src.modules.quality.adapters.inbound.api.deps.services import get_printer_gateway
from src.modules.quality.adapters.inbound.api.deps.services import get_zpl_rasterizer
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.application.use_cases.print_document.download_print_document import (
    DownloadPrintDocument,
)
from src.modules.quality.application.use_cases.print_document.get_print_jobs import GetPrintJobs
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.application.use_cases.print_document.print_lot_scrap_tag import (
    PrintLotScrapTag,
)
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    PrintUploadedDocument,
)
from src.modules.quality.application.use_cases.print_template.get_print_templates import (
    GetPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.get_print_templates import (
    GetPrintTemplates,
)
from src.modules.quality.application.use_cases.print_template.preview_print_template import (
    PreviewPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.render_print_template_image import (
    RenderPrintTemplateImage,
)
from src.modules.quality.application.use_cases.print_template.reset_print_template import (
    ResetPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.update_print_template import (
    UpdatePrintTemplate,
)
from src.modules.quality.application.use_cases.printer.archive_printer import ArchivePrinter
from src.modules.quality.application.use_cases.printer.create_printer import CreatePrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinters
from src.modules.quality.application.use_cases.printer.get_printer_status import GetPrinterStatus
from src.modules.quality.application.use_cases.printer.restore_printer import RestorePrinter
from src.modules.quality.application.use_cases.printer.test_print_printer import TestPrintPrinter
from src.modules.quality.application.use_cases.printer.update_printer import UpdatePrinter
from src.modules.quality.application.use_cases.report_journal.get_report_journal import (
    GetReportJournal,
)
from src.modules.quality.application.use_cases.report_journal.record_report_download import (
    RecordReportDownload,
)
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.modules.quality.ports.outbound.zpl_rasterizer_port import IZplRasterizer
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_repo
from src.modules.workspace.ports.outbound.workspace_queries import IMeetingQueries

# ── Printer ──────────────────────────────────────────────────────────


def get_create_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreatePrinter:
    return CreatePrinter(
        printer_repo=printer_repo,
        bought_item_repo=bought_item_repo,
        event_bus=event_bus,
        uow=uow,
    )


def get_update_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdatePrinter:
    return UpdatePrinter(
        printer_repo=printer_repo,
        bought_item_repo=bought_item_repo,
        event_bus=event_bus,
        uow=uow,
    )


def get_archive_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchivePrinter:
    return ArchivePrinter(printer_repo=printer_repo, event_bus=event_bus, uow=uow)


def get_restore_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestorePrinter:
    return RestorePrinter(printer_repo=printer_repo, event_bus=event_bus, uow=uow)


def get_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
) -> GetPrinter:
    return GetPrinter(printer_repo=printer_repo)


def get_printers_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
) -> GetPrinters:
    return GetPrinters(printer_repo=printer_repo)


def get_test_print_printer_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    gateway: IPrinterGateway = Depends(get_printer_gateway),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> TestPrintPrinter:
    return TestPrintPrinter(printer_repo=printer_repo, gateway=gateway, uow=uow)


def get_printer_status_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    gateway: IPrinterGateway = Depends(get_printer_gateway),
) -> GetPrinterStatus:
    return GetPrinterStatus(printer_repo=printer_repo, gateway=gateway)


# ── Docket rendering support (part image + branding, any ipp_document
#    printer or no printer at all) ──────────────────────────────────────


def get_docket_asset_resolver(
    item_picture_repo: IItemPictureQueries = Depends(get_item_picture_repo),
    admin_settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> DocketAssetResolver:
    return DocketAssetResolver(
        item_picture_repo=item_picture_repo,
        admin_settings_repo=admin_settings_repo,
        storage=storage,
    )


# ── PrintTemplate (settings) ────────────────────────────────────────────


def get_print_templates_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
) -> GetPrintTemplates:
    return GetPrintTemplates(template_repo=template_repo)


def get_print_template_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
) -> GetPrintTemplate:
    return GetPrintTemplate(template_repo=template_repo)


def get_update_print_template_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdatePrintTemplate:
    return UpdatePrintTemplate(template_repo=template_repo, printer_repo=printer_repo, uow=uow)


def get_reset_print_template_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ResetPrintTemplate:
    return ResetPrintTemplate(template_repo=template_repo, uow=uow)


def get_preview_print_template_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    root_resolver: IPrintRootResolver = Depends(get_print_root_resolver),
) -> PreviewPrintTemplate:
    return PreviewPrintTemplate(
        template_repo=template_repo, root_resolver=root_resolver, domain_url=cfg.domain
    )


def get_render_print_template_image_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    root_resolver: IPrintRootResolver = Depends(get_print_root_resolver),
    preview: PreviewPrintTemplate = Depends(get_preview_print_template_use_case),
    rasterizer: IZplRasterizer = Depends(get_zpl_rasterizer),
    docket_renderer: IDocketRenderer = Depends(get_docket_renderer),
    asset_resolver: DocketAssetResolver = Depends(get_docket_asset_resolver),
) -> RenderPrintTemplateImage:
    return RenderPrintTemplateImage(
        template_repo=template_repo,
        printer_repo=printer_repo,
        root_resolver=root_resolver,
        preview=preview,
        rasterizer=rasterizer,
        docket_renderer=docket_renderer,
        asset_resolver=asset_resolver,
        domain_url=cfg.domain,
    )


# ── PrintDocument / PrintJob ─────────────────────────────────────────────


def get_print_document_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    job_repo: IPrintJobRepository = Depends(get_print_job_repo),
    root_resolver: IPrintRootResolver = Depends(get_print_root_resolver),
    gateway: IPrinterGateway = Depends(get_printer_gateway),
    docket_renderer: IDocketRenderer = Depends(get_docket_renderer),
    asset_resolver: DocketAssetResolver = Depends(get_docket_asset_resolver),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PrintDocument:
    return PrintDocument(
        template_repo=template_repo,
        printer_repo=printer_repo,
        job_repo=job_repo,
        root_resolver=root_resolver,
        gateway=gateway,
        docket_renderer=docket_renderer,
        asset_resolver=asset_resolver,
        domain_url=cfg.domain,
        uow=uow,
    )


def get_print_uploaded_document_use_case(
    printer_repo: IPrinterRepository = Depends(get_printer_repo),
    job_repo: IPrintJobRepository = Depends(get_print_job_repo),
    calculation_repo: ICalculationRepository = Depends(get_calculation_repo),
    checklist_repo: IChecklistRepository = Depends(get_checklist_repo),
    lot_repo: IProductionLotQueries | None = Depends(get_production_lot_repo),
    journal_repo: IReportJournalRepository = Depends(get_report_journal_repo),
    gateway: IPrinterGateway = Depends(get_printer_gateway),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PrintUploadedDocument:
    return PrintUploadedDocument(
        printer_repo=printer_repo,
        job_repo=job_repo,
        roots=UploadedDocumentRoots(
            calculation_repo=calculation_repo, checklist_repo=checklist_repo, lot_repo=lot_repo
        ),
        gateway=gateway,
        uow=uow,
        journal_repo=journal_repo,
    )


def get_record_report_download_use_case(
    calculation_repo: ICalculationRepository = Depends(get_calculation_repo),
    checklist_repo: IChecklistRepository = Depends(get_checklist_repo),
    lot_repo: IProductionLotQueries | None = Depends(get_production_lot_repo),
    journal_repo: IReportJournalRepository = Depends(get_report_journal_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RecordReportDownload:
    return RecordReportDownload(
        journal_repo=journal_repo,
        roots=UploadedDocumentRoots(
            calculation_repo=calculation_repo, checklist_repo=checklist_repo, lot_repo=lot_repo
        ),
        uow=uow,
    )


def get_report_journal_use_case(
    calculation_repo: ICalculationRepository = Depends(get_calculation_repo),
    checklist_repo: IChecklistRepository = Depends(get_checklist_repo),
    lot_repo: IProductionLotQueries | None = Depends(get_production_lot_repo),
    meeting_repo: IMeetingQueries = Depends(get_meeting_repo),
    journal_repo: IReportJournalRepository = Depends(get_report_journal_repo),
) -> GetReportJournal:
    return GetReportJournal(
        journal_repo=journal_repo,
        roots=UploadedDocumentRoots(
            calculation_repo=calculation_repo,
            checklist_repo=checklist_repo,
            lot_repo=lot_repo,
            meeting_repo=meeting_repo,
        ),
    )


def get_print_lot_scrap_tag_use_case(
    scrap_records: LotScrapRecords = Depends(get_lot_scrap_records),
    print_document: PrintDocument = Depends(get_print_document_use_case),
) -> PrintLotScrapTag:
    return PrintLotScrapTag(scrap_records=scrap_records, print_document=print_document)


def get_download_print_document_use_case(
    template_repo: IPrintTemplateRepository = Depends(get_print_template_repo),
    job_repo: IPrintJobRepository = Depends(get_print_job_repo),
    root_resolver: IPrintRootResolver = Depends(get_print_root_resolver),
    docket_renderer: IDocketRenderer = Depends(get_docket_renderer),
    asset_resolver: DocketAssetResolver = Depends(get_docket_asset_resolver),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadPrintDocument:
    return DownloadPrintDocument(
        template_repo=template_repo,
        job_repo=job_repo,
        root_resolver=root_resolver,
        docket_renderer=docket_renderer,
        asset_resolver=asset_resolver,
        domain_url=cfg.domain,
        uow=uow,
    )


def get_print_jobs_use_case(
    job_repo: IPrintJobRepository = Depends(get_print_job_repo),
) -> GetPrintJobs:
    return GetPrintJobs(job_repo=job_repo)
