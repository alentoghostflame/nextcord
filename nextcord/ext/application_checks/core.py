"""
The MIT License (MIT)

Copyright (c) 2015-present Rapptz
Copyright (c) 2021-present tag-epic

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Optional, Type, Any, TYPE_CHECKING, TypeVar, Union, Callable
from typing_extensions import Concatenate, ParamSpec

import nextcord
from nextcord.application_command import ApplicationSubcommand, Interaction, AppCmdCallbackWrapper, BaseApplicationCommand, BaseApplicationSubcommand
from .errors import (
    ApplicationCheckAnyFailure,
    ApplicationCheckFailure,
    ApplicationNoPrivateMessage,
    ApplicationMissingRole,
    ApplicationMissingAnyRole,
    ApplicationBotMissingRole,
    ApplicationBotMissingAnyRole,
    ApplicationMissingPermissions,
    ApplicationBotMissingPermissions,
    ApplicationPrivateMessageOnly,
    ApplicationNotOwner,
    ApplicationNSFWChannelRequired,
    ApplicationCheckForBotOnly,
    ApplicationCommandOnCooldown,
    ApplicationMaxConcurrencyReached,
)
from .cooldowns import (
    ApplicationBucketType,
    ApplicationCooldown, 
    ApplicationCooldownMapping, 
    ApplicationDynamicCooldownMapping, 
    ApplicationMaxConcurrency,
)
from nextcord.ext.commands import Cog
from nextcord.utils import MISSING, maybe_coroutine
try:
    from nextcord.ext.commands._types import _BaseCommand
except:
    class _BaseCommand:
        __slots__ = ()

__all__ = (
    "check",
    "check_any",
    "has_role",
    "has_any_role",
    "bot_has_role",
    "bot_has_any_role",
    "has_permissions",
    "bot_has_permissions",
    "has_guild_permissions",
    "bot_has_guild_permissions",
    "cooldown",
    "dynamic_cooldown",
    "max_concurrency",
    "dm_only",
    "guild_only",
    "is_owner",
    "is_nsfw",
    "application_command_before_invoke",
    "application_command_after_invoke",
)

T = TypeVar('T')
CogT = TypeVar('CogT', bound='Cog')
ApplicationCommandT = TypeVar('ApplicationCommandT', bound='ApplicationCooldowns')
InteractionT = TypeVar('InteractionT', bound='Interaction')

if TYPE_CHECKING:
    from nextcord.types.checks import ApplicationCheck, CoroFunc
    P = ParamSpec('P')
else:
    P = TypeVar('P')

class ApplicationChecksCommand(ApplicationSubcommand, _BaseCommand, Generic[Callable[[CogT], CogT], P, T]):
    def __new__(cls: Type[ApplicationCommandT], *args: Any, **kwargs: Any) -> ApplicationCommandT:
        # if you're wondering why this is done, it's because we need to ensure
        # we have a complete original copy of **kwargs even for classes that
        # mess with it by popping before delegating to the subclass __init__.
        # In order to do this, we need to control the instance creation and
        # inject the original kwargs through __new__ rather than doing it
        # inside __init__.
        self = super().__new__(cls)

        # we do a shallow copy because it's probably the most common use case.
        # this could potentially break if someone modifies a list or something
        # while it's in movement, but for now this is the cheapest and
        # fastest way to do what we want.
        self.__original_kwargs__ = kwargs.copy()
        return self

    def __init__(self, func: Union[
            Callable[Concatenate[CogT, InteractionT, P], Coro[T]],
            Callable[Concatenate[InteractionT, P], Coro[T]],
        ], **kwargs: Any):
        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Callback must be a coroutine.')

        try:
            cooldown = func.__slash_commands_cooldown__
        except AttributeError:
            cooldown = kwargs.get('cooldown')
        
        if cooldown is None:
            buckets = ApplicationCooldownMapping(cooldown, ApplicationBucketType.default)
        elif isinstance(cooldown, ApplicationCooldownMapping):
            buckets = cooldown
        else:
            raise TypeError("ApplicationCooldown must be a an instance of ApplicationCooldownMapping or None.")
        self._buckets: ApplicationCooldownMapping = buckets

        try:
            max_concurrency = func.__slash_commands_max_concurrency__
        except AttributeError:
            max_concurrency = kwargs.get('max_concurrency')

        self._max_concurrency: Optional[ApplicationMaxConcurrency] = max_concurrency
        self.cooldown_after_parsing: bool = kwargs.get('cooldown_after_parsing', False)
        self.cog: Optional[CogT] = None

        # bandaid for the fact that sometimes parent can be the bot instance
        parent = kwargs.get('parent')
        self.parent: Optional[GroupMixin] = parent if isinstance(parent, _BaseCommand) else None  # type: ignore
            
    async def __call__(self, interaction: Interaction, *args: P.args, **kwargs: P.kwargs) -> T:
        """|coro|
        Calls the internal callback that the command holds.
        .. note::
            This bypasses all mechanisms -- including checks, converters,
            invoke hooks, cooldowns, etc. You must take care to pass
            the proper arguments and types to this function.
        .. versionadded:: 1.3
        """
        if self.cog is not None:
            return await self.callback(self.cog, interaction, *args, **kwargs)  # type: ignore
        else:
            return await self.callback(interaction, *args, **kwargs)  # type: ignore

    def _ensure_assignment_on_copy(self, other: ApplicationCommandT) -> ApplicationCommandT:
        other._before_invoke = self._before_invoke
        other._after_invoke = self._after_invoke
        if self.checks != other.checks:
            other.checks = self.checks.copy()
        if self._buckets.valid and not other._buckets.valid:
            other._buckets = self._buckets.copy()
        if self._max_concurrency != other._max_concurrency:
            # _max_concurrency won't be None at this point
            other._max_concurrency = self._max_concurrency.copy()  # type: ignore

        try:
            other.on_error = self.on_error
        except AttributeError:
            pass
        return other

    def copy(self: ApplicationCommandT) -> ApplicationCommandT:
        """Creates a copy of this command.
        Returns
        --------
        :class:`ApplicationChecksCommand`
            A new instance of this command.
        """
        ret = self.__class__(self.callback, **self.__original_kwargs__)
        return self._ensure_assignment_on_copy(ret)

    def _update_copy(self: ApplicationCommandT, kwargs: Dict[str, Any]) -> ApplicationCommandT:
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__original_kwargs__)
            copy = self.__class__(self.callback, **kw)
            return self._ensure_assignment_on_copy(copy)
        else:
            return self.copy()

    def _prepare_cooldowns(self, interaction: Interaction) -> None:
        if self._buckets.valid:
            dt = interaction.message.edited_at or interaction.message.created_at
            current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
            bucket = self._buckets.get_bucket(interaction.message, current)
            if bucket is not None:
                retry_after = bucket.update_rate_limit(current)
                if retry_after:
                    raise ApplicationCommandOnCooldown(bucket, retry_after, self._buckets.type)  # type: ignore

    async def prepare(self, interaction: Interaction) -> None:
        interaction.application_command = self

        if not await self.can_run(interaction):
            raise ApplicationCheckFailure(f'The check functions for command {self.qualified_name} failed.')

        if self._max_concurrency is not None:
            # For this application, context can be duck-typed as a Message
            await self._max_concurrency.acquire(interaction)  # type: ignore

        try:
            if self.cooldown_after_parsing:
                await self._parse_arguments(interaction)
                self._prepare_cooldowns(interaction)
            else:
                self._prepare_cooldowns(interaction)
                await self._parse_arguments(interaction)

            await self.call_before_hooks(interaction)
        except:
            if self._max_concurrency is not None:
                await self._max_concurrency.release(interaction)  # type: ignore
            raise

    def is_on_cooldown(self, interaction: Interaction) -> bool:
        """Checks whether the command is currently on cooldown.
        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to use when checking the commands cooldown status.
        Returns
        --------
        :class:`bool`
            A boolean indicating if the command is on cooldown.
        """
        if not self._buckets.valid:
            return False

        bucket = self._buckets.get_bucket(interaction.message)
        dt = interaction.message.edited_at or interaction.message.created_at
        current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        return bucket.get_tokens(current) == 0

    def reset_cooldown(self, interaction: Interaction) -> None:
        """Resets the cooldown on this command.
        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to reset the cooldown under.
        """
        if self._buckets.valid:
            bucket = self._buckets.get_bucket(interaction.message)
            bucket.reset()

    def get_cooldown_retry_after(self, interaction: Interaction) -> float:
        """Retrieves the amount of seconds before this command can be tried again.
        .. versionadded:: 1.4
        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to retrieve the cooldown from.
        Returns
        --------
        :class:`float`
            The amount of time left on this command's cooldown in seconds.
            If this is ``0.0`` then the command isn't on cooldown.
        """
        if self._buckets.valid:
            bucket = self._buckets.get_bucket(interaction.message)
            dt = interaction.message.edited_at or interaction.message.created_at
            current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
            return bucket.get_retry_after(current)

        # If we're here, either the buckets is not valid or there's no cooldown to begin with.
        return 0.0


    async def can_run(self, interaction: Interaction) -> bool:
        """|coro|
        Checks if the command can be executed by checking all the predicates
        inside the :attr:`~Command.checks` attribute. This also checks whether the
        command is disabled.
        .. versionchanged:: 1.3
            Checks whether the command is disabled or not
        Parameters
        -----------
        ctx: :class:`.Context`
            The ctx of the command currently being invoked.
        Raises
        -------
        :class:`CommandError`
            Any command error that was raised during a check call will be propagated
            by this function.
        Returns
        --------
        :class:`bool`
            A boolean indicating if the command can be invoked.
        """

        original = interaction.application_command
        interaction.application_command = self

        try:
            if not await self.application_command_can_run(interaction):
                raise ApplicationCheckFailure(f'The global check functions for command {self.qualified_name} failed.')

            cog = self.cog
            if cog is not None:
                local_check = Cog._get_overridden_method(cog.cog_check)
                if local_check is not None:
                    ret = await maybe_coroutine(local_check, interaction)
                    if not ret:
                        return False

            predicates = self.checks
            if not predicates:
                # since we have no checks, then we just return True.
                return True

            return await nextcord.utils.async_all(predicate(interaction) for predicate in predicates)  # type: ignore
        finally:
            interaction.application_command = original

class CheckWrapper(AppCmdCallbackWrapper):
    def __init__(self, callback: Union[Callable, AppCmdCallbackWrapper], predicate):
        super().__init__(callback)

        if not asyncio.iscoroutinefunction(predicate):
            @functools.wraps(predicate)
            async def async_wrapper(ctx):
                return predicate(ctx)
            self.predicate = async_wrapper
        else:
            self.predicate = predicate

    def modify(self, app_cmd: BaseApplicationCommand):
        app_cmd.checks.append(self.predicate)


# def check(predicate: "ApplicationCheck") -> Callable[[T], T]:
def check(predicate: "ApplicationCheck") -> Union[BaseApplicationCommand, BaseApplicationSubcommand, "CheckWrapper"]:
    r"""A decorator that adds a check to the :class:`.ApplicationCommand` or its
    subclasses. These checks are accessible via :attr:`.ApplicationCommand.checks`.

    These checks should be predicates that take in a single parameter taking
    a :class:`.Interaction`. If the check returns a ``False``\-like value, 
    a ApplicationCheckFailure is raised during invocation and sent to the 
    :func:`.on_application_command_error` event.

    If an exception should be thrown in the predicate then it should be a
    subclass of :exc:`.ApplicationError`. Any exception not subclassed from it
    will be propagated while those subclassed will be sent to
    :func:`on_application_command_error`.

    A special attribute named ``predicate`` is bound to the value
    returned by this decorator to retrieve the predicate passed to the
    decorator. This allows the following introspection and chaining to be done:

    .. code-block:: python3

        def owner_or_permissions(**perms):
            original = application_checks.has_permissions(**perms).predicate
            async def extended_check(interaction: Interaction):
                if interaction.guild is None:
                    return False

                return (
                    interaction.guild.owner_id == interaction.user.id
                    or await original(interaction)
                )
            return application_checks.check(extended_check)

    .. note::

        The function returned by ``predicate`` is **always** a coroutine,
        even if the original function was not a coroutine.

    Examples
    ---------

    Creating a basic check to see if the command invoker is you.

    .. code-block:: python3

        def check_if_it_is_me(interaction: Interaction):
            return interaction.message.author.id == 85309593344815104

        @bot.slash_command()
        @application_checks.check(check_if_it_is_me)
        async def only_for_me(interaction: Interaction):
            await interaction.response.send_message('I know you!')

    Transforming common checks into its own decorator:

    .. code-block:: python3

        def is_me():
            def predicate(interaction: Interaction):
                return interaction.user.id == 85309593344815104
            return application_checks.check(predicate)

        @bot.slash_command()
        @is_me()
        async def only_me(interaction: Interaction):
            await interaction.response.send_message('Only you!')

    Parameters
    -----------
    predicate: Callable[[:class:`~.Interaction`], :class:`bool`]
        The predicate to check if the command should be invoked.
    """
    # print("Base check called.")
    # if not asyncio.iscoroutinefunction(predicate):
    #     @functools.wraps(predicate)
    #     async def async_wrapper(ctx):
    #         return predicate(ctx)
    #     predicate = async_wrapper

    # class CheckWrapper(AppCmdCallbackWrapper):
    #     def modify(self, app_cmd: BaseApplicationCommand):
    #         app_cmd.checks.insert(0, predicate)

    # def decorator(
    #     func: Union[ApplicationSubcommand, "CoroFunc"]
    # ) -> Union[ApplicationSubcommand, "CoroFunc"]:
    #     if isinstance(func, ApplicationSubcommand):
    #         func.checks.insert(0, predicate)
    #     else:
    #         if not hasattr(func, "__slash_command_checks__"):
    #             func.__slash_command_checks__ = []
    #
    #         func.__slash_command_checks__.append(predicate)
    #
    #     return func
    # def wrapper(func):
    #     print("Check wrapper called, returning it!")
    #     return CheckWrapper(func)


    def wrapper(func):
        return CheckWrapper(func, predicate)
    return wrapper



    # if asyncio.iscoroutinefunction(predicate):
    #     decorator.predicate = predicate
    # else:
    #     @functools.wraps(predicate)
    #     async def async_wrapper(ctx):
    #         return predicate(ctx)
    #
    #     decorator.predicate = async_wrapper

    # return decorator
    # return wrapper



def check_any(*checks: "ApplicationCheck") -> Callable[[T], T]:
    r"""A :func:`check` that will pass if any of the given checks pass, 
    i.e. using logical OR.

    If all checks fail then :exc:`.ApplicationCheckAnyFailure` is raised to signal 
    the failure. It inherits from :exc:`.ApplicationCheckFailure`.

    .. note::

        The ``predicate`` attribute for this function **is** a coroutine.

    Parameters
    ------------
    \*checks: Callable[[:class:`~.Interaction`], :class:`bool`]
        An argument list of checks that have been decorated with
        the :func:`check` decorator.

    Raises
    -------
    TypeError
        A check passed has not been decorated with the :func:`check`
        decorator.

    Examples
    ---------

    Creating a basic check to see if it's the bot owner or
    the server owner:

    .. code-block:: python3

        def is_guild_owner():
            def predicate(interaction: Interaction):
                return (
                    interaction.guild is not None
                    and interaction.guild.owner_id == ctx.author.id
                )
            return commands.check(predicate)

        @bot.command()
        @checks.check_any(checks.is_owner(), is_guild_owner())
        async def only_for_owners(interaction: Interaction):
            await interaction.response.send_message('Hello mister owner!')
    """

    unwrapped = []
    for wrapped in checks:
        try:
            pred = wrapped.predicate
        except AttributeError:
            raise TypeError(
                f"{wrapped!r} must be wrapped by application_checks.check decorator"
            ) from None
        else:
            unwrapped.append(pred)

    async def predicate(interaction: Interaction) -> bool:
        errors = []
        for func in unwrapped:
            try:
                value = await func(interaction)
            except ApplicationCheckFailure as e:
                errors.append(e)
            else:
                if value:
                    return True
        # if we're here, all checks failed
        raise ApplicationCheckAnyFailure(unwrapped, errors)

    return check(predicate)


def has_role(item: Union[int, str]) -> Callable[[T], T]:
    """A :func:`.check` that is added that checks if the member invoking the
    command has the role specified via the name or ID specified.

    If a string is specified, you must give the exact name of the role, including
    caps and spelling.

    If an integer is specified, you must give the exact snowflake ID of the role.

    If the message is invoked in a private message context then the check will
    return ``False``.

    This check raises one of two special exceptions, :exc:`.MissingRole` if the user
    is missing a role, or :exc:`.NoPrivateMessage` if it is used in a private message.
    Both inherit from :exc:`.ApplicationCheckFailure`.

    Parameters
    -----------
    item: Union[:class:`int`, :class:`str`]
        The name or ID of the role to check.
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise ApplicationNoPrivateMessage()

        # interaction.guild is None doesn't narrow interaction.user to Member
        if isinstance(item, int):
            role = nextcord.utils.get(interaction.user.roles, id=item)  # type: ignore
        else:
            role = nextcord.utils.get(interaction.user.roles, name=item)  # type: ignore
        if role is None:
            raise ApplicationMissingRole(item)
        return True

    return check(predicate)


def has_any_role(*items: Union[int, str]) -> Callable[[T], T]:
    r"""A :func:`.check` that is added that checks if the member invoking the
    command has **any** of the roles specified. This means that if they have
    one out of the three roles specified, then this check will return `True`.

    Similar to :func:`.has_role`\, the names or IDs passed in must be exact.

    This check raises one of two special exceptions, :exc:`.MissingAnyRole` if the user
    is missing all roles, or :exc:`.NoPrivateMessage` if it is used in a private message.
    Both inherit from :exc:`.ApplicationCheckFailure`.

    Parameters
    -----------
    items: List[Union[:class:`str`, :class:`int`]]
        An argument list of names or IDs to check that the member has roles wise.

    Example
    --------

    .. code-block:: python3

        @bot.slash_command()
        @checks.has_any_role('Library `Dev`s', 'Moderators', 492212595072434186)
        async def cool(interaction: Interaction):
            await interaction.response.send_message('You are cool indeed')
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise ApplicationNoPrivateMessage()

        # interaction.guild is None doesn't narrow interaction.user to Member
        getter = functools.partial(nextcord.utils.get, interaction.user.roles)  # type: ignore
        if any(
            getter(id=item) is not None
            if isinstance(item, int)
            else getter(name=item) is not None
            for item in items
        ):
            return True
        raise ApplicationMissingAnyRole(list(items))

    return check(predicate)


def bot_has_role(item: int) -> Callable[[T], T]:
    """Similar to :func:`.has_role` except checks if the bot itself has the
    role.

    This check raises one of two special exceptions, 
    :exc:`.ApplicationBotMissingRole` if the bot is missing the role, 
    or :exc:`.ApplicationNoPrivateMessage` if it is used in a private message.
    Both inherit from :exc:`.ApplicationCheckFailure`.
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise ApplicationNoPrivateMessage()

        me = interaction.guild.me
        if isinstance(item, int):
            role = nextcord.utils.get(me.roles, id=item)
        else:
            role = nextcord.utils.get(me.roles, name=item)
        if role is None:
            raise ApplicationBotMissingRole(item)
        return True

    return check(predicate)


def bot_has_any_role(*items: int) -> Callable[[T], T]:
    """Similar to :func:`.has_any_role` except checks if the bot itself has
    any of the roles listed.

    This check raises one of two special exceptions, 
    :exc:`.ApplicationBotMissingAnyRole` if the bot is missing all roles, 
    or :exc:`.ApplicationNoPrivateMessage` if it is used in a private message.
    Both inherit from :exc:`.ApplicationCheckFailure`.
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise ApplicationNoPrivateMessage()

        me = interaction.guild.me or interaction.client.user
        getter = functools.partial(nextcord.utils.get, me.roles)
        if any(
            getter(id=item) is not None
            if isinstance(item, int)
            else getter(name=item) is not None
            for item in items
        ):
            return True
        raise ApplicationBotMissingAnyRole(list(items))

    return check(predicate)


def has_permissions(**perms: bool) -> Callable[[T], T]:
    """A :func:`.check` that is added that checks if the member has all of
    the permissions necessary.

    Note that this check operates on the current channel permissions, not the
    guild wide permissions.

    The permissions passed in must be exactly like the properties shown under
    :class:`.nextcord.Permissions`.

    This check raises a special exception, :exc:`.ApplicationMissingPermissions`
    that is inherited from :exc:`.ApplicationCheckFailure`.

    If this check is called in a DM context, it will raise an
    exception, :exc:`.ApplicationNoPrivateMessage`.

    Parameters
    ------------
    perms
        An argument list of permissions to check for.

    Example
    ---------

    .. code-block:: python3

        @bot.slash_command()
        @checks.has_permissions(manage_messages=True)
        async def test(interaction: Interaction):
            await interaction.response.send_message('You can manage messages.')

    """

    invalid = set(perms) - set(nextcord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(interaction: Interaction) -> bool:
        ch = interaction.channel
        try:
            permissions = ch.permissions_for(interaction.user)  # type: ignore
        except AttributeError:
            raise ApplicationNoPrivateMessage()

        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise ApplicationMissingPermissions(missing)

    return check(predicate)


def bot_has_permissions(**perms: bool) -> Callable[[T], T]:
    """Similar to :func:`.has_permissions` except checks if the bot itself has
    the permissions listed.

    This check raises a special exception, :exc:`.ApplicationBotMissingPermissions`
    that is inherited from :exc:`.ApplicationCheckFailure`.

    If this check is called in a DM context, it will raise an
    exception, :exc:`.ApplicationNoPrivateMessage`.
    """

    invalid = set(perms) - set(nextcord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(interaction: Interaction) -> bool:
        guild = interaction.guild
        me = guild.me if guild is not None else interaction.client.user
        ch = interaction.channel
        try:
            permissions = ch.permissions_for(me)  # type: ignore
        except AttributeError:
            raise ApplicationNoPrivateMessage()

        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise ApplicationBotMissingPermissions(missing)

    return check(predicate)


def has_guild_permissions(**perms: bool) -> Callable[[T], T]:
    """Similar to :func:`.has_permissions`, but operates on guild wide
    permissions instead of the current channel permissions.

    If this check is called in a DM context, it will raise an
    exception, :exc:`.ApplicationNoPrivateMessage`.
    """

    invalid = set(perms) - set(nextcord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(interaction: Interaction) -> bool:
        if not interaction.guild:
            raise ApplicationNoPrivateMessage

        permissions = interaction.user.guild_permissions  # type: ignore
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise ApplicationMissingPermissions(missing)

    return check(predicate)


def bot_has_guild_permissions(**perms: bool) -> Callable[[T], T]:
    """Similar to :func:`.has_guild_permissions`, but checks the bot
    members guild permissions.
    """

    invalid = set(perms) - set(nextcord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(interaction: Interaction) -> bool:
        if not interaction.guild:
            raise ApplicationNoPrivateMessage

        permissions = interaction.guild.me.guild_permissions  # type: ignore
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise ApplicationBotMissingPermissions(missing)

    return check(predicate)

def cooldown(rate: int = MISSING, per: float = MISSING, type: Union[ApplicationBucketType, Callable[[Interaction], Any]] = ApplicationBucketType.default) -> Callable[[T], T]
    def decorator(func: Union[ApplicationChecksCommand, "CoroFunc"]) -> Union[ApplicationChecksCommand, "CoroFunc"]:
        if isinstance(func, ApplicationChecksCommand):
            func._buckets = ApplicationCooldownMapping(ApplicationCooldown(rate, per), type)
        else:
            if not hasattr(func, "__slash_commands_cooldown__"):
                func.__slash_commands_cooldown__ = []
                
            func.__slash_commands_cooldown__ = ApplicationCooldownMapping(ApplicationCooldown(rate, per), type)
        return func
    return decorator

def dynamic_cooldown(cooldown: Union[ApplicationBucketType, Callable[[Interaction], Any]], type: ApplicationBucketType = ApplicationBucketType.default) -> Callable[[T], T]:
    """A decorator that adds a dynamic cooldown to a :class:`.Command`
    This differs from :func:`.cooldown` in that it takes a function that
    accepts a single parameter of type :class:`.nextcord.Message` and must
    return a :class:`.Cooldown` or ``None``. If ``None`` is returned then
    that cooldown is effectively bypassed.
    A cooldown allows a command to only be used a specific amount
    of times in a specific time frame. These cooldowns can be based
    either on a per-guild, per-channel, per-user, per-role or global basis.
    Denoted by the third argument of ``type`` which must be of enum
    type :class:`.BucketType`.
    If a cooldown is triggered, then :exc:`.CommandOnCooldown` is triggered in
    :func:`.on_command_error` and the local error handler.
    A command can only have a single cooldown.
    .. versionadded:: 2.0
    Parameters
    ------------
    cooldown: Callable[[:class:`.nextcord.Message`], Optional[:class:`.Cooldown`]]
        A function that takes a message and returns a cooldown that will
        apply to this invocation or ``None`` if the cooldown should be bypassed.
    type: :class:`.BucketType`
        The type of cooldown to have.
    """
    if not callable(cooldown):
        raise TypeError("A callable must be provided")

    def decorator(func: Union[ApplicationChecksCommand, "CoroFunc"]) -> Union[ApplicationChecksCommand, "CoroFunc"]:
        if isinstance(func, ApplicationChecksCommand):
            func._buckets = ApplicationDynamicCooldownMapping(cooldown, type)
        else:
            func.__slash_commands_cooldown__ = ApplicationDynamicCooldownMapping(cooldown, type)
        return func
    return decorator  # type: ignore

def max_concurrency(number: int, per: ApplicationBucketType = ApplicationBucketType.default, *, wait: bool = False) -> Callable[[T], T]:
    """A decorator that adds a maximum concurrency to a :class:`.Command` or its subclasses.
    This enables you to only allow a certain number of command invocations at the same time,
    for example if a command takes too long or if only one user can use it at a time. This
    differs from a cooldown in that there is no set waiting period or token bucket -- only
    a set number of people can run the command.
    .. versionadded:: 1.3
    Parameters
    -------------
    number: :class:`int`
        The maximum number of invocations of this command that can be running at the same time.
    per: :class:`.BucketType`
        The bucket that this concurrency is based on, e.g. ``BucketType.guild`` would allow
        it to be used up to ``number`` times per guild.
    wait: :class:`bool`
        Whether the command should wait for the queue to be over. If this is set to ``False``
        then instead of waiting until the command can run again, the command raises
        :exc:`.MaxConcurrencyReached` to its error handler. If this is set to ``True``
        then the command waits until it can be executed.
    """

    def decorator(func: Union[ApplicationChecksCommand, "CoroFunc"]) -> Union[ApplicationChecksCommand, "CoroFunc"]:
        value = ApplicationMaxConcurrency(number, per=per, wait=wait)
        if isinstance(func, ApplicationChecksCommand):
            func._max_concurrency = value
        else:
            func.__slash_commands_max_concurrency__ = value
        return func
    return decorator  # type: ignore

def dm_only() -> Callable[[T], T]:
    """A :func:`.check` that indicates this command must only be used in a
    DM context. Only private messages are allowed when
    using the command.

    This check raises a special exception, :exc:`.ApplicationPrivateMessageOnly`
    that is inherited from :exc:`.ApplicationCheckFailure`.
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is not None:
            raise ApplicationPrivateMessageOnly()
        return True

    return check(predicate)


def guild_only() -> Callable[[T], T]:
    """A :func:`.check` that indicates this command must only be used in a
    guild context only. Basically, no private messages are allowed when
    using the command.

    This check raises a special exception, :exc:`.ApplicationNoPrivateMessage`
    that is inherited from :exc:`.ApplicationCheckFailure`.
    """

    def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise ApplicationNoPrivateMessage()
        return True

    return check(predicate)


def is_owner() -> Callable[[T], T]:
    """A :func:`.check` that checks if the person invoking this command is the
    owner of the bot.

    This is powered by :meth:`.ext.commands.Bot.is_owner`.

    This check raises a special exception, :exc:`.ApplicationNotOwner` that is derived
    from :exc:`.ApplicationCheckFailure`.

    This check may only be used with :class:`~ext.commands.Bot`. Otherwise, it will
    raise :exc:`.ApplicationCheckForBotOnly`.
    """

    async def predicate(interaction: Interaction) -> bool:
        if not hasattr(interaction.client, "is_owner"):
            raise ApplicationCheckForBotOnly()

        if not await interaction.client.is_owner(interaction.user):
            raise ApplicationNotOwner("You do not own this bot.")
        return True

    return check(predicate)


def is_nsfw() -> Callable[[T], T]:
    """A :func:`.check` that checks if the channel is a NSFW channel.

    This check raises a special exception, :exc:`.ApplicationNSFWChannelRequired`
    that is derived from :exc:`.ApplicationCheckFailure`.
    """

    def pred(interaction: Interaction) -> bool:
        ch = interaction.channel
        if interaction.guild is None or (
            isinstance(ch, (nextcord.TextChannel, nextcord.Thread)) and ch.is_nsfw()
        ):
            return True
        raise ApplicationNSFWChannelRequired(ch)  # type: ignore

    return check(pred)


def application_command_before_invoke(coro) -> Callable[[T], T]:
    """A decorator that registers a coroutine as a pre-invoke hook.

    This allows you to refer to one before invoke hook for several commands that
    do not have to be within the same cog.

    Example
    ---------

    .. code-block:: python3

        async def record_usage(interaction: Interaction):
            print(
                interaction.user,
                "used",
                interaction.application_command,
                "at",
                interaction.message.created_at
            )

        @bot.slash_command()
        @application_checks.application_command_before_invoke(record_usage)
        async def who(interaction: Interaction): # Output: <User> used who at <Time>
            await interaction.response.send_message("I am a bot")

        class What(commands.Cog):

            @application_checks.application_command_before_invoke(record_usage)
            @slash_command()
            async def when(self, interaction: Interaction):
                # Output: <User> used when at <Time>
                await interaction.response.send_message(
                    f"and i have existed since {interaction.client.user.created_at}"
                )

            @slash_command()
            async def where(self, interaction: Interaction): # Output: <Nothing>
                await interaction.response.send_message("on Discord")

            @slash_command()
            async def why(self, interaction: Interaction): # Output: <Nothing>
                await interaction.response.send_message("because someone made me")

        bot.add_cog(What())
    """

    def decorator(
        func: Union[ApplicationSubcommand, "CoroFunc"]
    ) -> Union[ApplicationSubcommand, "CoroFunc"]:
        if isinstance(func, ApplicationSubcommand):
            func.application_command_before_invoke(coro)
        else:
            func.__application_command_before_invoke__ = coro
        return func

    return decorator  # type: ignore


def application_command_after_invoke(coro) -> Callable[[T], T]:
    """A decorator that registers a coroutine as a post-invoke hook.

    This allows you to refer to one after invoke hook for several commands that
    do not have to be within the same cog.
    """

    def decorator(
        func: Union[ApplicationSubcommand, "CoroFunc"]
    ) -> Union[ApplicationSubcommand, "CoroFunc"]:
        if isinstance(func, ApplicationSubcommand):
            func.application_command_after_invoke(coro)
        else:
            func.__application_command_after_invoke__ = coro
        return func

    return decorator  # type: ignore
