"""Registers and includes all endpoint routers for the web API, ensuring
/users/me/* static routes are registered before the general /users route
to prevent parameter consumption.
"""

from fastapi import APIRouter

from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import article_groups
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import bought_item_files
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import bought_item_pictures
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import bought_items
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import bought_items_files_bulk
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import contacts
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import customers
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import data_import
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import fabrication_methods
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import inspection_methods
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import made_item_files
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import made_item_pictures
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import made_items
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import made_items_files_bulk
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import product_families
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import source_item_files
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import source_item_pictures
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import source_item_types
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import source_items
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import source_items_files_bulk
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints import suppliers
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    data_import as admin_settings_data_import,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    made_item_numbering as admin_settings_made_item_numbering,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    order_numbering as admin_settings_order_numbering,
)
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints import bought_items_edp
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints import bought_items_import
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints import pdm
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    eplan_data_portal as admin_settings_eplan_data_portal,
)
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    pdm as admin_settings_pdm,
)
from src.modules.external_data.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    stock as admin_settings_stock,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import bought_items_allocations
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import bought_items_demand
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import (
    bought_items_demand_buckets,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import dashboard
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import external_work
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import made_items_allocations
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import made_items_demand
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import made_items_demand_buckets
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import order_files
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import orders
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_exceptions
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_lots
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_machine_pools
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_machines
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_operators
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_order_files
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_orders
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_qa
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_schedule
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import production_wip
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import quote_request_files
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import quote_requests
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import source_item_allocations
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import source_item_demand_buckets
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import source_item_demands
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import todo
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    planning as admin_settings_planning,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    production_numbering as admin_settings_production_numbering,
)
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import infoscreens
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import terminal_broadcasts
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import terminal_device
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import terminal_keys
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import terminals
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import time_tracking
from src.modules.operations.adapters.inbound.api.v1.web.endpoints import (
    user_time_tracking_credentials,
)
from src.modules.operations.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    time_tracking as admin_settings_time_tracking,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import admin_acknowledgements
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import agent_calls
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import agent_consent
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import announcements
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import api_keys
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import live
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import logs
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import mail
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import notifications
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import passkeys
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import pats
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import resolve
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import sessions
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import tenant_holidays
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import totp
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import trusted_devices
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import user_groups
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import users
from src.modules.platform.adapters.inbound.api.v1.web.endpoints import webhooks
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    agents as admin_settings_agents,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    audit as admin_settings_audit,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    auth as admin_settings_auth,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    backup as admin_settings_backup,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    branding as admin_settings_branding,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    features as admin_settings_features,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    general as admin_settings_general,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    mail as admin_settings_mail,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    maintenance as admin_settings_maintenance,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    notifications as admin_settings_notifications,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    retention as admin_settings_retention,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    security as admin_settings_security,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    security_events as admin_settings_security_events,
)
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    storage as admin_settings_storage,
)
from src.modules.platform.const import API_WEB
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import calculations
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import checklists
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import lot_scrap_tags
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import print_action
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import print_jobs
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import print_templates
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import printers
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import production_kpi
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import report_journal
from src.modules.quality.adapters.inbound.api.v1.web.endpoints import sequences
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import contact_links
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import meeting_distribution
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import meeting_notes_drafts
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import meetings
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import plc_environments
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import product_device_resources
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import product_devices
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import product_files
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import product_variants
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import products
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import products_files_bulk
from src.modules.workspace.adapters.inbound.api.v1.web.endpoints import projects
from src.read.adapters.inbound.api.v1.web.endpoints import host
from src.read.adapters.inbound.api.v1.web.endpoints import search
from src.read.adapters.inbound.api.v1.web.endpoints import state_machines
from src.read.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    all_settings as admin_settings_all_settings,
)
from src.read.adapters.inbound.api.v1.web.endpoints.admin_settings import (
    integrations_overview as admin_settings_integrations_overview,
)

router = APIRouter()

# Static /users/me/* segments registered before users.router so nothing in
# there can ever consume them as a path parameter.
router.include_router(
    sessions.router, prefix=f"{API_WEB}/users/me/sessions", tags=["web/users/sessions"]
)
router.include_router(
    trusted_devices.router,
    prefix=f"{API_WEB}/users/me/trusted-devices",
    tags=["web/users/trusted-devices"],
)
router.include_router(
    passkeys.router, prefix=f"{API_WEB}/users/me/passkeys", tags=["web/users/passkeys"]
)
router.include_router(
    agent_consent.router,
    prefix=f"{API_WEB}/users/me/agent-consent",
    tags=["web/users/agent-consent"],
)
router.include_router(users.router, prefix=f"{API_WEB}/users", tags=["web/users"])
router.include_router(user_groups.router, prefix=f"{API_WEB}/user-groups", tags=["web/user-groups"])
router.include_router(
    user_time_tracking_credentials.router, prefix=f"{API_WEB}/users", tags=["web/users"]
)
router.include_router(totp.router, prefix=f"{API_WEB}/users/me/totp", tags=["web/users/2fa"])
router.include_router(logs.router, prefix=f"{API_WEB}/logs", tags=["web/logs"])
router.include_router(customers.router, prefix=f"{API_WEB}/customers", tags=["web/customers"])
router.include_router(contacts.router, prefix=f"{API_WEB}/contacts", tags=["web/contacts"])
router.include_router(products.router, prefix=f"{API_WEB}/products", tags=["web/products"])
router.include_router(
    product_files.router,
    prefix=f"{API_WEB}/products",
    tags=["web/products/files"],
)
router.include_router(
    products_files_bulk.router,
    prefix=f"{API_WEB}/products-files",
    tags=["web/products/files"],
)
router.include_router(
    product_devices.router, prefix=f"{API_WEB}/products", tags=["web/products/devices"]
)
router.include_router(
    product_devices.manual_tag_router,
    prefix=f"{API_WEB}/plc-manual-tags",
    tags=["web/plc-environments"],
)
router.include_router(
    product_devices.device_router,
    prefix=f"{API_WEB}/product-devices",
    tags=["web/products/devices"],
)
router.include_router(
    product_variants.router, prefix=f"{API_WEB}/products", tags=["web/products/variants"]
)
router.include_router(
    contact_links.product_router, prefix=f"{API_WEB}/products", tags=["web/products/contacts"]
)
router.include_router(
    contact_links.project_router, prefix=f"{API_WEB}/projects", tags=["web/projects/contacts"]
)
router.include_router(
    contact_links.usage_router, prefix=f"{API_WEB}/contact-usage", tags=["web/contacts"]
)
router.include_router(
    product_device_resources.router,
    prefix=f"{API_WEB}/product-device-resources",
    tags=["web/product-device-resources"],
)
router.include_router(
    plc_environments.router,
    prefix=f"{API_WEB}/product-device-resources",
    tags=["web/plc-environments"],
)
router.include_router(projects.router, prefix=f"{API_WEB}/projects", tags=["web/projects"])
router.include_router(meetings.router, prefix=f"{API_WEB}/meetings", tags=["web/meetings"])
router.include_router(
    meeting_distribution.router, prefix=f"{API_WEB}/meetings", tags=["web/meetings"]
)
router.include_router(
    meetings.scope_router, prefix=f"{API_WEB}/meeting-scopes", tags=["web/meetings"]
)
router.include_router(meetings.tag_router, prefix=f"{API_WEB}/meeting-tags", tags=["web/meetings"])
router.include_router(
    meeting_notes_drafts.router,
    prefix=f"{API_WEB}/meeting-notes-drafts",
    tags=["web/meetings"],
)
router.include_router(
    calculations.router, prefix=f"{API_WEB}/calculations", tags=["web/calculations"]
)
router.include_router(checklists.router, prefix=f"{API_WEB}/checklists", tags=["web/checklists"])
router.include_router(sequences.router, prefix=f"{API_WEB}/sequences", tags=["web/sequences"])
router.include_router(
    report_journal.router, prefix=f"{API_WEB}/report-journal", tags=["web/report-journal"]
)
router.include_router(suppliers.router, prefix=f"{API_WEB}/suppliers", tags=["web/suppliers"])
router.include_router(
    article_groups.router, prefix=f"{API_WEB}/article-groups", tags=["web/article-groups"]
)
router.include_router(
    product_families.router, prefix=f"{API_WEB}/product-families", tags=["web/product-families"]
)
router.include_router(
    fabrication_methods.router,
    prefix=f"{API_WEB}/fabrication-methods",
    tags=["web/fabrication-methods"],
)
router.include_router(
    inspection_methods.router,
    prefix=f"{API_WEB}/inspection-methods",
    tags=["web/inspection-methods"],
)
router.include_router(
    source_items.router, prefix=f"{API_WEB}/source-items", tags=["web/source-items"]
)
router.include_router(
    source_item_files.router,
    prefix=f"{API_WEB}/source-items",
    tags=["web/source-items/files"],
)
router.include_router(
    source_items_files_bulk.router,
    prefix=f"{API_WEB}/source-items-files",
    tags=["web/source-items/files"],
)
router.include_router(
    source_item_pictures.router,
    prefix=f"{API_WEB}/source-items",
    tags=["web/source-items/pictures"],
)
router.include_router(
    source_item_pictures.bulk_router,
    prefix=f"{API_WEB}/source-items-pictures",
    tags=["web/source-items/pictures"],
)
router.include_router(
    source_item_types.router, prefix=f"{API_WEB}/source-item-types", tags=["web/source-item-types"]
)
router.include_router(
    source_item_demands.router,
    prefix=f"{API_WEB}/source-item-demands",
    tags=["web/source-item-demands"],
)
router.include_router(
    source_item_demand_buckets.router,
    prefix=f"{API_WEB}/source-item-demand-buckets",
    tags=["web/source-item-demand-buckets"],
)
router.include_router(
    source_item_allocations.router,
    prefix=f"{API_WEB}/source-item-allocations",
    tags=["web/source-item-allocations"],
)
router.include_router(
    bought_items.router, prefix=f"{API_WEB}/bought-items", tags=["web/bought-items"]
)
router.include_router(
    bought_items_edp.router,
    prefix=f"{API_WEB}/bought-items-edp",
    tags=["web/bought-items-edp"],
)
router.include_router(
    bought_items_import.router,
    prefix=f"{API_WEB}/bought-items-import",
    tags=["web/bought-items-import"],
)
router.include_router(
    bought_item_files.router,
    prefix=f"{API_WEB}/bought-items",
    tags=["web/bought-items/files"],
)
router.include_router(
    bought_items_files_bulk.router,
    prefix=f"{API_WEB}/bought-items-files",
    tags=["web/bought-items/files"],
)
router.include_router(
    bought_item_pictures.router,
    prefix=f"{API_WEB}/bought-items",
    tags=["web/bought-items/pictures"],
)
router.include_router(
    bought_item_pictures.bulk_router,
    prefix=f"{API_WEB}/bought-items-pictures",
    tags=["web/bought-items/pictures"],
)
router.include_router(
    bought_items_allocations.router,
    prefix=f"{API_WEB}/bought-items-allocations",
    tags=["web/bought-items/allocations"],
)
router.include_router(
    bought_items_demand.router,
    prefix=f"{API_WEB}/bought-items-demands",
    tags=["web/bought-items/demand"],
)
router.include_router(
    bought_items_demand_buckets.router,
    prefix=f"{API_WEB}/bought-items-demand-buckets",
    tags=["web/bought-items-demand-buckets"],
)
router.include_router(made_items.router, prefix=f"{API_WEB}/made-items", tags=["web/made-items"])
router.include_router(
    made_item_files.router,
    prefix=f"{API_WEB}/made-items",
    tags=["web/made-items/files"],
)
router.include_router(
    made_items_files_bulk.router,
    prefix=f"{API_WEB}/made-items-files",
    tags=["web/made-items/files"],
)
router.include_router(
    made_item_pictures.router,
    prefix=f"{API_WEB}/made-items",
    tags=["web/made-items/pictures"],
)
router.include_router(
    made_item_pictures.bulk_router,
    prefix=f"{API_WEB}/made-items-pictures",
    tags=["web/made-items/pictures"],
)
router.include_router(
    made_items_allocations.router,
    prefix=f"{API_WEB}/made-items-allocations",
    tags=["web/made-items/allocations"],
)
router.include_router(
    made_items_demand.router,
    prefix=f"{API_WEB}/made-items-demands",
    tags=["web/made-items/demand"],
)
router.include_router(
    made_items_demand_buckets.router,
    prefix=f"{API_WEB}/made-items-demand-buckets",
    tags=["web/made-items-demand-buckets"],
)
router.include_router(
    orders.router,
    prefix=f"{API_WEB}/orders",
    tags=["web/orders"],
)
router.include_router(
    quote_requests.router,
    prefix=f"{API_WEB}/quote-requests",
    tags=["web/quote-requests"],
)
router.include_router(
    external_work.router,
    prefix=f"{API_WEB}/external-work",
    tags=["web/external-work"],
)
router.include_router(
    quote_request_files.router,
    prefix=f"{API_WEB}/quote-request-suppliers",
    tags=["web/quote-request-files"],
)
router.include_router(
    production_lots.router,
    prefix=f"{API_WEB}/production-lots",
    tags=["web/production-lots"],
)
router.include_router(
    lot_scrap_tags.router,
    prefix=f"{API_WEB}/production-lots",
    tags=["web/production-lots"],
)
router.include_router(
    production_machines.router,
    prefix=f"{API_WEB}/production-machines",
    tags=["web/production-machines"],
)
router.include_router(
    production_machine_pools.router,
    prefix=f"{API_WEB}/production-machine-pools",
    tags=["web/production-machine-pools"],
)
router.include_router(tenant_holidays.router, prefix=f"{API_WEB}/holidays", tags=["web/holidays"])
router.include_router(
    production_orders.router,
    prefix=f"{API_WEB}/production-orders",
    tags=["web/production-orders"],
)
router.include_router(
    production_order_files.router,
    prefix=f"{API_WEB}/production-orders",
    tags=["web/production-orders/files"],
)
router.include_router(
    production_operators.router,
    prefix=f"{API_WEB}/production-operators",
    tags=["web/production-operators"],
)
router.include_router(
    production_wip.router,
    prefix=f"{API_WEB}/production-wip",
    tags=["web/production-wip"],
)
router.include_router(
    dashboard.router,
    prefix=f"{API_WEB}/dashboard",
    tags=["web/dashboard"],
)
router.include_router(
    todo.router,
    prefix=f"{API_WEB}/todo",
    tags=["web/todo"],
)
router.include_router(
    production_exceptions.router,
    prefix=f"{API_WEB}/production-exceptions",
    tags=["web/production-exceptions"],
)
router.include_router(
    production_qa.router,
    prefix=f"{API_WEB}/production-qa",
    tags=["web/production-qa"],
)
router.include_router(
    production_schedule.router,
    prefix=f"{API_WEB}/production-schedule",
    tags=["web/production-schedule"],
)
router.include_router(
    production_kpi.router,
    prefix=f"{API_WEB}/production-kpi",
    tags=["web/production-kpi"],
)
router.include_router(
    order_files.router,
    prefix=f"{API_WEB}/orders",
    tags=["web/orders/files"],
)
router.include_router(host.router, prefix=f"{API_WEB}/host", tags=["web/host"])
router.include_router(live.router, prefix=f"{API_WEB}/live", tags=["web/live"])
router.include_router(
    terminal_device.router,
    prefix=f"{API_WEB}/terminal-device",
    tags=["web/terminal-device"],
)
router.include_router(terminals.router, prefix=f"{API_WEB}/terminals", tags=["web/terminals"])
router.include_router(
    terminal_broadcasts.router,
    prefix=f"{API_WEB}/terminal-broadcasts",
    tags=["web/terminal-broadcasts"],
)
router.include_router(infoscreens.router, prefix=f"{API_WEB}/infoscreens", tags=["web/infoscreens"])
# The admin settings tabs, in the order their routes are matched.
for admin_settings_tab in (
    admin_settings_all_settings,
    admin_settings_integrations_overview,
    admin_settings_general,
    admin_settings_auth,
    admin_settings_mail,
    admin_settings_storage,
    admin_settings_backup,
    admin_settings_security,
    admin_settings_agents,
    admin_settings_features,
    admin_settings_branding,
    admin_settings_notifications,
    admin_settings_maintenance,
    admin_settings_retention,
    admin_settings_order_numbering,
    admin_settings_made_item_numbering,
    admin_settings_production_numbering,
    admin_settings_planning,
    admin_settings_pdm,
    admin_settings_time_tracking,
    admin_settings_data_import,
    admin_settings_eplan_data_portal,
    admin_settings_stock,
    admin_settings_audit,
    admin_settings_security_events,
):
    router.include_router(
        admin_settings_tab.router,
        prefix=f"{API_WEB}/admin/settings",
        tags=["web/admin/settings"],
    )
router.include_router(
    webhooks.router, prefix=f"{API_WEB}/admin/webhooks", tags=["web/admin/webhooks"]
)
router.include_router(
    admin_acknowledgements.router,
    prefix=f"{API_WEB}/admin/acknowledgements",
    tags=["web/admin/acknowledgements"],
)
router.include_router(
    announcements.router, prefix=f"{API_WEB}/announcements", tags=["web/announcements"]
)
router.include_router(
    api_keys.router, prefix=f"{API_WEB}/admin/api-keys", tags=["web/admin/api-keys"]
)
router.include_router(
    terminal_keys.router, prefix=f"{API_WEB}/admin/api-keys", tags=["web/admin/api-keys"]
)
router.include_router(
    pats.router,
    prefix=f"{API_WEB}/users/me/personal-access-tokens",
    tags=["web/users/me/pats"],
)
router.include_router(agent_calls.router, prefix=f"{API_WEB}/agent-calls", tags=["web/agent-calls"])
router.include_router(pdm.router, prefix=f"{API_WEB}/pdm", tags=["web/pdm"])
router.include_router(data_import.router, prefix=f"{API_WEB}/data-import", tags=["web/data-import"])
router.include_router(
    time_tracking.router, prefix=f"{API_WEB}/time-tracking", tags=["web/time-tracking"]
)
router.include_router(
    notifications.router, prefix=f"{API_WEB}/notifications", tags=["web/notifications"]
)
router.include_router(mail.router, prefix=f"{API_WEB}/mail", tags=["web/mail"])
router.include_router(resolve.router, prefix=f"{API_WEB}/resolve", tags=["web/resolve"])
router.include_router(search.router, prefix=f"{API_WEB}/search", tags=["web/search"])
router.include_router(
    state_machines.router, prefix=f"{API_WEB}/state-machines", tags=["web/state-machines"]
)
router.include_router(printers.router, prefix=f"{API_WEB}/printers", tags=["web/printers"])
router.include_router(
    print_templates.router, prefix=f"{API_WEB}/print-templates", tags=["web/print-templates"]
)
router.include_router(print_action.router, prefix=f"{API_WEB}/print", tags=["web/print"])
router.include_router(print_jobs.router, prefix=f"{API_WEB}/print-jobs", tags=["web/print-jobs"])
