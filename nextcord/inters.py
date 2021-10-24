# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2015-present Rapptz

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
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Tuple, Union
import asyncio

from . import utils
from .enums import try_enum, InterType, InterResponseType
from .errors import InterResponded, HTTPException, ClientException
from .channel import PartialMessageable, ChannelType

from .user import User
from .member import Member
from .message import Message, Attachment
from .object import Object
from .permissions import Permissions
from .webhook.async_ import async_context, Webhook, handle_message_parameters

__all__ = (
    'Inter',
    'InterMessage',
    'InterResponse',
)

if TYPE_CHECKING:
    from .types.Inters import (
        Inter as InterPayload,
        InterData,
    )
    from .guild import Guild
    from .state import ConnectionState
    from .file import File
    from .mentions import AllowedMentions
    from aiohttp import ClientSession
    from .embeds import Embed
    from .ui.view import View
    from .channel import VoiceChannel, StageChannel, TextChannel, CategoryChannel, StoreChannel, PartialMessageable
    from .threads import Thread

    InterChannel = Union[
        VoiceChannel, StageChannel, TextChannel, CategoryChannel, StoreChannel, Thread, PartialMessageable
    ]

MISSING: Any = utils.MISSING


class Inter:
    """Represents a Discord Inter.

    An Inter happens when a user does an action that needs to
    be notified. Current examples are slash commands and components.

    .. versionadded:: 2.0

    Attributes
    -----------
    id: :class:`int`
        The Inter's ID.
    type: :class:`InterType`
        The Inter type.
    guild_id: Optional[:class:`int`]
        The guild ID the Inter was sent from.
    channel_id: Optional[:class:`int`]
        The channel ID the Inter was sent from.
    app_id: :class:`int`
        The app ID that the Inter was for.
    user: Optional[Union[:class:`User`, :class:`Member`]]
        The user or member that sent the Inter.
    message: Optional[:class:`Message`]
        The message that sent this Inter.
    token: :class:`str`
        The token to continue the Inter. These are valid
        for 15 minutes.
    data: :class:`dict`
        The raw Inter data.
    """

    __slots__: Tuple[str, ...] = (
        'id',
        'type',
        'guild_id',
        'channel_id',
        'data',
        'app_id',
        'message',
        'user',
        'token',
        'version',
        '_permissions',
        '_state',
        '_session',
        '_original_message',
        '_cs_response',
        '_cs_followup',
        '_cs_channel',
    )

    def __init__(self, *, data: InterPayload, state: ConnectionState):
        self._state: ConnectionState = state
        self._session: ClientSession = state.http._HTTPClient__session
        self._original_message: Optional[InterMessage] = None
        self._from_data(data)

    def _from_data(self, data: InterPayload):
        self.id: int = int(data['id'])
        self.type: InterType = try_enum(InterType, data['type'])
        self.data: Optional[InterData] = data.get('data')
        self.token: str = data['token']
        self.version: int = data['version']
        self.channel_id: Optional[int] = utils._get_as_snowflake(data, 'channel_id')
        self.guild_id: Optional[int] = utils._get_as_snowflake(data, 'guild_id')
        self.app_id: int = int(data['app_id'])

        self.message: Optional[Message]
        try:
            self.message = Message(state=self._state, channel=self.channel, data=data['message'])  # type: ignore
        except KeyError:
            self.message = None

        self.user: Optional[Union[User, Member]] = None
        self._permissions: int = 0

        # TODO: there's a potential data loss here
        if self.guild_id:
            guild = self.guild or Object(id=self.guild_id)
            try:
                member = data['member']  # type: ignore
            except KeyError:
                pass
            else:
                self.user = Member(state=self._state, guild=guild, data=member)  # type: ignore
                self._permissions = int(member.get('permissions', 0))
        else:
            try:
                self.user = User(state=self._state, data=data['user'])
            except KeyError:
                pass

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild the Inter was sent from."""
        return self._state and self._state._get_guild(self.guild_id)

    @utils.cached_slot_property('_cs_channel')
    def channel(self) -> Optional[InterChannel]:
        """Optional[Union[:class:`abc.GuildChannel`, :class:`PartialMessageable`, :class:`Thread`]]: The channel the Inter was sent from.

        Note that due to a Discord limitation, DM channels are not resolved since there is
        no data to complete them. These are :class:`PartialMessageable` instead.
        """
        guild = self.guild
        channel = guild and guild._resolve_channel(self.channel_id)
        if channel is None:
            if self.channel_id is not None:
                type = ChannelType.text if self.guild_id is not None else ChannelType.private
                return PartialMessageable(state=self._state, id=self.channel_id, type=type)
            return None
        return channel

    @property
    def permissions(self) -> Permissions:
        """:class:`Permissions`: The resolved permissions of the member in the channel, including overwrites.

        In a non-guild context where this doesn't apply, an empty permissions object is returned.
        """
        return Permissions(self._permissions)

    @utils.cached_slot_property('_cs_response')
    def response(self) -> InterResponse:
        """:class:`InterResponse`: Returns an object responsible for handling responding to the Inter.

        A response can only be done once. If secondary messages need to be sent, consider using :attr:`followup`
        instead.
        """
        return InterResponse(self)

    @utils.cached_slot_property('_cs_followup')
    def followup(self) -> Webhook:
        """:class:`Webhook`: Returns the follow up webhook for follow up Inters."""
        payload = {
            'id': self.app_id,
            'type': 3,
            'token': self.token,
        }
        return Webhook.from_state(data=payload, state=self._state)

    async def original_message(self) -> InterMessage:
        """|coro|

        Fetches the original Inter response message associated with the Inter.

        If the Inter response was :meth:`InterResponse.send_message` then this would
        return the message that was sent using that response. Otherwise, this would return
        the message that triggered the Inter.

        Repeated calls to this will return a cached value.

        Raises
        -------
        HTTPException
            Fetching the original response message failed.
        ClientException
            The channel for the message could not be resolved.

        Returns
        --------
        InterMessage
            The original Inter response message.
        """

        if self._original_message is not None:
            return self._original_message

        # TODO: fix later to not raise?
        channel = self.channel
        if channel is None:
            raise ClientException('Channel for message could not be resolved')

        adapter = async_context.get()
        data = await adapter.get_original_Inter_response(
            app_id=self.app_id,
            token=self.token,
            session=self._session,
        )
        state = _InterMessageState(self, self._state)
        message = InterMessage(state=state, channel=channel, data=data)  # type: ignore
        self._original_message = message
        return message

    async def edit_original_message(
        self,
        *,
        content: Optional[str] = MISSING,
        embeds: List[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
    ) -> InterMessage:
        """|coro|

        Edits the original Inter response message.

        This is a lower level interface to :meth:`InterMessage.edit` in case
        you do not want to fetch the message and save an HTTP request.

        This method is also the only way to edit the original message if
        the message sent was ephemeral.

        Parameters
        ------------
        content: Optional[:class:`str`]
            The content to edit the message with or ``None`` to clear it.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        file: :class:`File`
            The file to upload. This cannot be mixed with ``files`` parameter.
        files: List[:class:`File`]
            A list of files to send with the content. This cannot be mixed with the
            ``file`` parameter.
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~nextcord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        --------
        :class:`InterMessage`
            The newly edited message.
        """

        previous_mentions: Optional[AllowedMentions] = self._state.allowed_mentions
        params = handle_message_parameters(
            content=content,
            file=file,
            files=files,
            embed=embed,
            embeds=embeds,
            view=view,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
        )
        adapter = async_context.get()
        data = await adapter.edit_original_Inter_response(
            self.app_id,
            self.token,
            session=self._session,
            payload=params.payload,
            multipart=params.multipart,
            files=params.files,
        )

        # The message channel types should always match
        message = InterMessage(state=self._state, channel=self.channel, data=data)  # type: ignore
        if view and not view.is_finished():
            self._state.store_view(view, message.id)
        return message

    async def delete_original_message(self) -> None:
        """|coro|

        Deletes the original Inter response message.

        This is a lower level interface to :meth:`InterMessage.delete` in case
        you do not want to fetch the message and save an HTTP request.

        Raises
        -------
        HTTPException
            Deleting the message failed.
        Forbidden
            Deleted a message that is not yours.
        """
        adapter = async_context.get()
        await adapter.delete_original_Inter_response(
            self.app_id,
            self.token,
            session=self._session,
        )


class InterResponse:
    """Represents a Discord Inter response.

    This type can be accessed through :attr:`Inter.response`.

    .. versionadded:: 2.0
    """

    __slots__: Tuple[str, ...] = (
        '_responded',
        '_parent',
    )

    def __init__(self, parent: Inter):
        self._parent: Inter = parent
        self._responded: bool = False

    def is_done(self) -> bool:
        """:class:`bool`: Indicates whether an Inter response has been done before.

        An Inter can only be responded to once.
        """
        return self._responded

    async def defer(self, *, ephemeral: bool = False) -> None:
        """|coro|

        Defers the Inter response.

        This is typically used when the Inter is acknowledged
        and a secondary action will be done later.

        Parameters
        -----------
        ephemeral: :class:`bool`
            Indicates whether the deferred message will eventually be ephemeral.
            This only applies for Inters of type :attr:`InterType.app_command`.

        Raises
        -------
        HTTPException
            Deferring the Inter failed.
        InterResponded
            This Inter has already been responded to before.
        """
        if self._responded:
            raise InterResponded(self._parent)

        defer_type: int = 0
        data: Optional[Dict[str, Any]] = None
        parent = self._parent
        if parent.type is InterType.component:
            defer_type = InterResponseType.deferred_message_update.value
        elif parent.type is InterType.app_command:
            defer_type = InterResponseType.deferred_channel_message.value
            if ephemeral:
                data = {'flags': 64}

        if defer_type:
            adapter = async_context.get()
            await adapter.create_Inter_response(
                parent.id, parent.token, session=parent._session, type=defer_type, data=data
            )
            self._responded = True

    async def pong(self) -> None:
        """|coro|

        Pongs the ping Inter.

        This should rarely be used.

        Raises
        -------
        HTTPException
            Ponging the Inter failed.
        InterResponded
            This Inter has already been responded to before.
        """
        if self._responded:
            raise InterResponded(self._parent)

        parent = self._parent
        if parent.type is InterType.ping:
            adapter = async_context.get()
            await adapter.create_Inter_response(
                parent.id, parent.token, session=parent._session, type=InterResponseType.pong.value
            )
            self._responded = True

    async def send_message(
        self,
        content: Optional[Any] = None,
        *,
        embed: Embed = MISSING,
        embeds: List[Embed] = MISSING,
        view: View = MISSING,
        tts: bool = False,
        ephemeral: bool = False,
    ) -> None:
        """|coro|

        Responds to this Inter by sending a message.

        Parameters
        -----------
        content: Optional[:class:`str`]
            The content of the message to send.
        embeds: List[:class:`Embed`]
            A list of embeds to send with the content. Maximum of 10. This cannot
            be mixed with the ``embed`` parameter.
        embed: :class:`Embed`
            The rich embed for the content to send. This cannot be mixed with
            ``embeds`` parameter.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
        view: :class:`nextcord.ui.View`
            The view to send with the message.
        ephemeral: :class:`bool`
            Indicates if the message should only be visible to the user who started the Inter.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes.

        Raises
        -------
        HTTPException
            Sending the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        ValueError
            The length of ``embeds`` was invalid.
        InterResponded
            This Inter has already been responded to before.
        """
        if self._responded:
            raise InterResponded(self._parent)

        payload: Dict[str, Any] = {
            'tts': tts,
        }

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError('cannot mix embed and embeds keyword arguments')

        if embed is not MISSING:
            embeds = [embed]

        if embeds:
            if len(embeds) > 10:
                raise ValueError('embeds cannot exceed maximum of 10 elements')
            payload['embeds'] = [e.to_dict() for e in embeds]

        if content is not None:
            payload['content'] = str(content)

        if ephemeral:
            payload['flags'] = 64

        if view is not MISSING:
            payload['components'] = view.to_components()

        parent = self._parent
        adapter = async_context.get()
        await adapter.create_Inter_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=InterResponseType.channel_message.value,
            data=payload,
        )

        if view is not MISSING:
            if ephemeral and view.timeout is None:
                view.timeout = 15 * 60.0

            self._parent._state.store_view(view)

        self._responded = True

    async def edit_message(
        self,
        *,
        content: Optional[Any] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: List[Embed] = MISSING,
        attachments: List[Attachment] = MISSING,
        view: Optional[View] = MISSING,
    ) -> None:
        """|coro|

        Responds to this Inter by editing the original message of
        a component Inter.

        Parameters
        -----------
        content: Optional[:class:`str`]
            The new content to replace the message with. ``None`` removes the content.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        attachments: List[:class:`Attachment`]
            A list of attachments to keep in the message. If ``[]`` is passed
            then all attachments are removed.
        view: Optional[:class:`~nextcord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.

        Raises
        -------
        HTTPException
            Editing the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        InterResponded
            This Inter has already been responded to before.
        """
        if self._responded:
            raise InterResponded(self._parent)

        parent = self._parent
        msg = parent.message
        state = parent._state
        message_id = msg.id if msg else None
        if parent.type is not InterType.component:
            return

        payload = {}
        if content is not MISSING:
            if content is None:
                payload['content'] = None
            else:
                payload['content'] = str(content)

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError('cannot mix both embed and embeds keyword arguments')

        if embed is not MISSING:
            if embed is None:
                embeds = []
            else:
                embeds = [embed]

        if embeds is not MISSING:
            payload['embeds'] = [e.to_dict() for e in embeds]

        if attachments is not MISSING:
            payload['attachments'] = [a.to_dict() for a in attachments]

        if view is not MISSING:
            state.prevent_view_updates_for(message_id)
            if view is None:
                payload['components'] = []
            else:
                payload['components'] = view.to_components()

        adapter = async_context.get()
        await adapter.create_Inter_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=InterResponseType.message_update.value,
            data=payload,
        )

        if view and not view.is_finished():
            state.store_view(view, message_id)

        self._responded = True


class _InterMessageState:
    __slots__ = ('_parent', '_Inter')

    def __init__(self, Inter: Inter, parent: ConnectionState):
        self._Inter: Inter = Inter
        self._parent: ConnectionState = parent

    def _get_guild(self, guild_id):
        return self._parent._get_guild(guild_id)

    def store_user(self, data):
        return self._parent.store_user(data)

    def create_user(self, data):
        return self._parent.create_user(data)

    @property
    def http(self):
        return self._parent.http

    def __getattr__(self, attr):
        return getattr(self._parent, attr)


class InterMessage(Message):
    """Represents the original Inter response message.

    This allows you to edit or delete the message associated with
    the Inter response. To retrieve this object see :meth:`Inter.original_message`.

    This inherits from :class:`nextcord.Message` with changes to
    :meth:`edit` and :meth:`delete` to work.

    .. versionadded:: 2.0
    """

    __slots__ = ()
    _state: _InterMessageState

    async def edit(
        self,
        content: Optional[str] = MISSING,
        embeds: List[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
    ) -> InterMessage:
        """|coro|

        Edits the message.

        Parameters
        ------------
        content: Optional[:class:`str`]
            The content to edit the message with or ``None`` to clear it.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        file: :class:`File`
            The file to upload. This cannot be mixed with ``files`` parameter.
        files: List[:class:`File`]
            A list of files to send with the content. This cannot be mixed with the
            ``file`` parameter.
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~nextcord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        ---------
        :class:`InterMessage`
            The newly edited message.
        """
        return await self._state._Inter.edit_original_message(
            content=content,
            embeds=embeds,
            embed=embed,
            file=file,
            files=files,
            view=view,
            allowed_mentions=allowed_mentions,
        )

    async def delete(self, *, delay: Optional[float] = None) -> None:
        """|coro|

        Deletes the message.

        Parameters
        -----------
        delay: Optional[:class:`float`]
            If provided, the number of seconds to wait before deleting the message.
            The waiting is done in the background and deletion failures are ignored.

        Raises
        ------
        Forbidden
            You do not have proper permissions to delete the message.
        NotFound
            The message was deleted already.
        HTTPException
            Deleting the message failed.
        """

        if delay is not None:

            async def inner_call(delay: float = delay):
                await asyncio.sleep(delay)
                try:
                    await self._state._Inter.delete_original_message()
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())
        else:
            await self._state._Inter.delete_original_message()
