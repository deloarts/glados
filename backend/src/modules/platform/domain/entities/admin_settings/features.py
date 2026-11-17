"""
Domain entity for the feature flag settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminFeatureSettings(Entity):
    """Feature flags, toggle modules without redeployment."""

    # Gates the queued-notification mailer (send_pending_notifications).
    enable_email_notifications: bool
    # Off hides every internal-production surface from the UI: the Production
    # section, machines, lots, production orders and the project time budget.
    # Enforcement is presentational, the API keeps serving those endpoints.
    enable_production_planning: bool
    # Lets webhook URLs resolve to private ranges such as RFC 1918 and
    # unique local IPv6, on by default since another host on the company
    # network is a normal receiver. Loopback, link-local, cloud metadata and
    # the stack's own network stay refused either way (see
    # adapters/outbound/external/webhook/webhook_target_guard.py).
    allow_private_webhooks: bool
    # Each of these hides one optional module from the UI when off: its
    # navigation entries, tabs and the buttons that lead into it. Like
    # enable_production_planning the gate is presentational, the API keeps
    # serving the module's endpoints and its stored records stay untouched.
    enable_calculations: bool = True
    enable_checklists: bool = True
    enable_devices: bool = True
    enable_sequences: bool = True
    enable_todos: bool = True
