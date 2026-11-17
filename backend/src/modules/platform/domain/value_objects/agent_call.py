"""
Value objects of the agent call log: which kind of token an agent called
with and how a call ended.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class AgentTokenKind(StrValueEnum):
    """A personal access token acts as the human who created it; an API key
    acts as its own service account and reaches only the read tools."""

    PAT = "pat"
    API_KEY = "api_key"


@unique
class AgentCallOutcome(StrValueEnum):
    OK = "ok"
    # The tool ran and refused or failed, such as a missing permission or a
    # record that does not exist.
    ERROR = "error"
    # The call never ran: a budget was spent or the tool is not open to the
    # token, such as a draft tool for an API key.
    REFUSED = "refused"
