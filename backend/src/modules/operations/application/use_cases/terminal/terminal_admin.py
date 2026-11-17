"""
Admin use cases for terminals. Listing is open to every signed-in user, but
only holders of manage:terminals see what identifies one device (the key
fingerprint, the client addresses, the serials and the hostname).
Approving, editing, revoking, the reload and identify requests, the display
override and deleting need manage:terminals. Approval needs the pairing code
the display shows. Approval, revocation, a screen reassignment and deletion
are written to the audit trail; every change reaches the display through the
live row sync of its own row.
"""

from src.modules.operations.application.dto.terminal_dto import ApproveTerminalCommand
from src.modules.operations.application.dto.terminal_dto import SetDisplayOverrideCommand
from src.modules.operations.application.dto.terminal_dto import TerminalResult
from src.modules.operations.application.dto.terminal_dto import UpdateTerminalCommand
from src.modules.operations.application.mappers.terminal_mapper import TerminalMapper
from src.modules.operations.application.services.display_calendar import DisplayCalendarReader
from src.modules.operations.application.services.terminal_audit import record_terminal_audit
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InfoscreenArchivedError
from src.modules.operations.domain.errors import InfoscreenNotFoundError
from src.modules.operations.domain.errors import TerminalNotFoundError
from src.modules.operations.domain.errors import TerminalNotReadyError
from src.modules.operations.domain.services import display_power_rules
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.display_schedule import DisplayPower
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _label(terminal: Terminal) -> str:
    name = f" {terminal.name!r}" if terminal.name else ""
    return f"terminal #{terminal.id}{name} ({terminal.public_key_fingerprint})"


async def _load(repo: ITerminalRepository, terminal_id: int) -> Terminal:
    """The terminal under its row lock, so the change an admin makes is made
    to the current row and a device request cannot write over it."""
    return found_or_raise(
        await repo.lock_for_update(terminal_id),
        TerminalNotFoundError,
        f"Terminal #{terminal_id} not found.",
    )


async def _assert_assignable(repo: IInfoscreenRepository, infoscreen_id: int | None) -> None:
    """A screen to assign must exist and be live; None unassigns."""
    if infoscreen_id is None:
        return
    screen = found_or_raise(
        await repo.get_by_id(infoscreen_id),
        InfoscreenNotFoundError,
        f"Infoscreen #{infoscreen_id} not found.",
    )
    if screen.archived:
        raise InfoscreenArchivedError(f"Infoscreen {screen.name!r} is archived.")


class ListTerminals:
    def __init__(self, terminal_repo: ITerminalRepository, calendar: DisplayCalendarReader) -> None:
        self._terminals = terminal_repo
        self._calendar = calendar

    async def execute(self, actor: User) -> list[TerminalResult]:
        now = now_utc()
        calendar = await self._calendar.read(now)
        identifying = terminal_rules.may_see_identifying_details(actor)
        return [
            TerminalMapper.to_result(
                t,
                power=display_power_rules.terminal_display_power(t, calendar, now),
                identifying=identifying,
            )
            for t in await self._terminals.get_visible(now)
        ]


class _TerminalWrite:
    def __init__(
        self,
        terminal_repo: ITerminalRepository,
        infoscreen_repo: IInfoscreenRepository,
        settings_repo: IOperationsSettingsRepository,
        calendar: DisplayCalendarReader,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._terminals = terminal_repo
        self._screens = infoscreen_repo
        self._settings = settings_repo
        self._calendar = calendar
        self._uow = uow

    async def _save(self, terminal: Terminal) -> TerminalResult:
        """Saves and commits. The caller holds manage:terminals, so the
        result shows every detail."""
        now = now_utc()
        terminal.changed = now
        saved = await self._terminals.save(terminal)
        await self._uow.commit()
        power = display_power_rules.terminal_display_power(
            saved, await self._calendar.read(now), now
        )
        return TerminalMapper.to_result(saved, power=power, identifying=True)


class ApproveTerminal(_TerminalWrite):
    async def execute(
        self, actor: User, terminal_id: int, cmd: ApproveTerminalCommand
    ) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        await _assert_assignable(self._screens, cmd.infoscreen_id)
        terminal_rules.approve(
            terminal,
            pairing_code=cmd.pairing_code,
            name=cmd.name.strip(),
            mode=TerminalMode(cmd.mode),
            infoscreen_id=cmd.infoscreen_id,
            actor=actor,
            now=now_utc(),
            location=cmd.location,
        )
        await record_terminal_audit(
            self._settings, actor, f"Approved {_label(terminal)} by {actor.username}."
        )
        result = await self._save(terminal)
        log.info(f"Approved {_label(terminal)}.")
        return result


class UpdateTerminal(_TerminalWrite):
    async def execute(
        self, actor: User, terminal_id: int, cmd: UpdateTerminalCommand
    ) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        if cmd.name is not None:
            terminal.name = cmd.name.strip()
        if cmd.mode is not None:
            terminal_rules.assert_mode_supported(cmd.mode)
            terminal.mode = TerminalMode(cmd.mode)
        if "location" in cmd.fields_set:
            terminal.location = terminal_rules.normalise_location(cmd.location)
        if "infoscreen_id" in cmd.fields_set and cmd.infoscreen_id != terminal.infoscreen_id:
            await _assert_assignable(self._screens, cmd.infoscreen_id)
            previous = terminal.infoscreen_id
            terminal.infoscreen_id = cmd.infoscreen_id
            await record_terminal_audit(
                self._settings,
                actor,
                f"Reassigned {_label(terminal)} from infoscreen #{previous} to "
                f"#{cmd.infoscreen_id} by {actor.username}.",
            )
            log.info(
                f"Reassigned {_label(terminal)} from infoscreen #{previous} to "
                f"#{cmd.infoscreen_id}."
            )
        return await self._save(terminal)


class RevokeTerminal(_TerminalWrite):
    async def execute(self, actor: User, terminal_id: int) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        terminal_rules.revoke(terminal, now_utc())
        await record_terminal_audit(
            self._settings, actor, f"Revoked {_label(terminal)} by {actor.username}."
        )
        result = await self._save(terminal)
        log.info(f"Revoked {_label(terminal)}.")
        return result


class RequestTerminalReload(_TerminalWrite):
    """The display reloads its page once it sees the new timestamp."""

    async def execute(self, actor: User, terminal_id: int) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        terminal.reload_requested_at = now_utc()
        log.info(f"Requested a reload of {_label(terminal)}.")
        return await self._save(terminal)


class RequestTerminalIdentify(_TerminalWrite):
    """The display shows its name and fingerprint for a moment once it sees
    the new timestamp, so it can be found on the wall."""

    async def execute(self, actor: User, terminal_id: int) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        terminal.identify_requested_at = now_utc()
        log.info(f"Requested {_label(terminal)} to identify itself.")
        return await self._save(terminal)


class SetTerminalDisplayOverride(_TerminalWrite):
    """Forces an approved terminal's display on or off until a given moment,
    by default until the next change of its screen's schedule. The display
    picks it up through the live row sync of its own row."""

    async def execute(
        self, actor: User, terminal_id: int, cmd: SetDisplayOverrideCommand
    ) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        if terminal.status != TerminalStatus.APPROVED:
            raise TerminalNotReadyError(
                f"Terminal #{terminal.id} is not approved, so its display is always on."
            )
        now = now_utc()
        until = cmd.until
        if until is None:
            until = display_power_rules.default_override_end(
                terminal, await self._calendar.read(now), now
            )
        display_power_rules.set_override(terminal, DisplayPower(cmd.power), until, now)
        log.info(f"Set the display of {_label(terminal)} {cmd.power} until {until}.")
        return await self._save(terminal)


class ClearTerminalDisplayOverride(_TerminalWrite):
    """Hands the display back to its screen's schedule."""

    async def execute(self, actor: User, terminal_id: int) -> TerminalResult:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        display_power_rules.clear_override(terminal)
        log.info(f"Cleared the display override of {_label(terminal)}.")
        return await self._save(terminal)


class DeleteTerminal(_TerminalWrite):
    """Removes the terminal. Its next sign-in counts as an unknown device and
    needs a terminal key again."""

    async def execute(self, actor: User, terminal_id: int) -> None:
        terminal_rules.assert_can_manage(actor)
        terminal = await _load(self._terminals, terminal_id)
        await record_terminal_audit(
            self._settings, actor, f"Deleted {_label(terminal)} by {actor.username}."
        )
        await self._terminals.delete(terminal)
        await self._uow.commit()
        log.info(f"Deleted {_label(terminal)}.")
