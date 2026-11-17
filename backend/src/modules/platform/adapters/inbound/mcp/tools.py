"""
The building blocks every module uses to offer tools, prompts and resources
to AI agents through the MCP surface (`/mcp`).

A module declares its tools in its own `adapters/inbound/mcp/` package, each
as an `AgentTool` whose handler builds the module's use case through the
use-case factory of the matching web route (`ctx.use_case(...)`) and calls
it with the caller as actor. The composition root collects the tools of
every module and serves them (`server.py`), so a module never sees the
others' tools and a tool never checks less than the web route it mirrors.

A tool is a read tool or a draft tool. A read tool changes nothing. A draft
tool creates only records that wait for a person in the web app, such as a
draft purchase order, and is open to personal access tokens only, never to
an API key. A draft tool's input carries an optional idempotency key, so an
agent that repeats a call gets the first call's records back.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
from typing import Any
from typing import overload

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.mcp.resolve import DependencyResolver
from src.modules.platform.application.dto.agent_dto import AgentPrincipal
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.user import User


class ToolKind(StrEnum):
    READ = "read"
    DRAFT = "draft"


class ToolInput(BaseModel):
    """Base of every tool's input. Unknown arguments are refused, so a typo
    in an argument name is an error the agent sees instead of a silently
    ignored filter."""

    model_config = ConfigDict(extra="forbid")


class DraftToolInput(ToolInput):
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Any unique string for this one action. Repeating the call with the same key "
            "returns the records the first call created instead of creating them again."
        ),
    )


@dataclass
class ToolOutput:
    """What a handler returns: the result, JSON shaped or a Pydantic model,
    and the public references of the records a draft tool created, such as
    `order:<public id>`, which the agent call log keeps."""

    data: Any
    created_refs: list[str] = field(default_factory=list)


class AgentToolContext:
    """One tool call: who calls, on which session, under which settings."""

    def __init__(
        self,
        principal: AgentPrincipal,
        db: AsyncSession,
        settings: AdminAgentSettings,
        overrides: Mapping[Callable[..., Any], Callable[..., Any]] | None = None,
    ) -> None:
        self.principal = principal
        self.db = db
        self.settings = settings
        self._overrides = overrides

    @property
    def actor(self) -> User:
        return self.principal.user

    @overload
    async def use_case[T](self, factory: Callable[..., Awaitable[T]]) -> T: ...

    @overload
    async def use_case[T](self, factory: Callable[..., T]) -> T: ...

    async def use_case(self, factory: Callable[..., Any]) -> Any:
        """The use case `factory` builds, wired as for its web route. An
        async factory is awaited, so the use case comes back either way.

        Every call gets wiring of its own on the call's session, as every
        web request does, so two use cases never share a reconciler or a
        lock plan. A tool that runs one use case per transaction builds it
        again for each transaction."""
        return await DependencyResolver(self.db, self._overrides).build(factory)


@dataclass(frozen=True)
class AgentTool:
    name: str
    title: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[AgentToolContext, Any], Awaitable[ToolOutput]]
    kind: ToolKind = ToolKind.READ
    # Permissions the caller must hold for the tool to be listed and run.
    # The use case checks its own permissions as well; this only keeps a
    # token from seeing tools it can never use.
    requires: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is ToolKind.DRAFT and not issubclass(self.input_model, DraftToolInput):
            raise TypeError(f"Draft tool {self.name!r} must take a DraftToolInput.")


@dataclass(frozen=True)
class PromptArgument:
    name: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class AgentPrompt:
    """A ready-made instruction the client offers its user, often as a slash
    command. `render` turns the arguments into the user message."""

    name: str
    title: str
    description: str
    arguments: tuple[PromptArgument, ...]
    render: Callable[[Mapping[str, str]], str]


@dataclass(frozen=True)
class AgentResource:
    """A record an agent can attach as context, read through a tool. The URI
    template names one parameter, such as `glados://lot/{number}`, which is
    passed to the tool as `argument`."""

    uri_template: str
    name: str
    title: str
    description: str
    tool: str
    argument: str

    @property
    def prefix(self) -> str:
        return self.uri_template.split("{", 1)[0]


@dataclass(frozen=True)
class AgentCatalog:
    """What one module offers agents."""

    tools: tuple[AgentTool, ...] = ()
    prompts: tuple[AgentPrompt, ...] = ()
    resources: tuple[AgentResource, ...] = ()


def ref(kind: str, public_id: object) -> str:
    """The reference of a created record for the agent call log."""
    return f"{kind}:{public_id}"
