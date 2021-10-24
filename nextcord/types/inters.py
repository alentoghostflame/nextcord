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

from typing import Optional, TYPE_CHECKING, Dict, TypedDict, Union, List, Literal
from .snowflake import Snowflake
from .components import Component, ComponentType
from .embed import Embed
from .channel import ChannelType
from .member import Member
from .role import Role
from .user import User

if TYPE_CHECKING:
    from .message import AllowedMentions, Message


AppCommandType = Literal[1, 2, 3]

class _AppCommandOptional(TypedDict, total=False):
    options: List[AppCommandOption]
    type: AppCommandType


class AppCommand(_AppCommandOptional):
    id: Snowflake
    app_id: Snowflake
    name: str
    description: str


class _AppCommandOptionOptional(TypedDict, total=False):
    choices: List[AppCommandOptionChoice]
    options: List[AppCommandOption]


AppCommandOptionType = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class AppCommandOption(_AppCommandOptionOptional):
    type: AppCommandOptionType
    name: str
    description: str
    required: bool


class AppCommandOptionChoice(TypedDict):
    name: str
    value: Union[str, int]


AppCommandPermissionType = Literal[1, 2]


class AppCommandPermissions(TypedDict):
    id: Snowflake
    type: AppCommandPermissionType
    permission: bool


class BaseGuildAppCommandPermissions(TypedDict):
    permissions: List[AppCommandPermissions]


class PartialGuildAppCommandPermissions(BaseGuildAppCommandPermissions):
    id: Snowflake


class GuildAppCommandPermissions(PartialGuildAppCommandPermissions):
    app_id: Snowflake
    guild_id: Snowflake


InterType = Literal[1, 2, 3]


class _AppCommandInterDataOption(TypedDict):
    name: str


class _AppCommandInterDataOptionSubcommand(_AppCommandInterDataOption):
    type: Literal[1, 2]
    options: List[AppCommandInterDataOption]


class _AppCommandInterDataOptionString(_AppCommandInterDataOption):
    type: Literal[3]
    value: str


class _AppCommandInterDataOptionInteger(_AppCommandInterDataOption):
    type: Literal[4]
    value: int


class _AppCommandInterDataOptionBoolean(_AppCommandInterDataOption):
    type: Literal[5]
    value: bool


class _AppCommandInterDataOptionSnowflake(_AppCommandInterDataOption):
    type: Literal[6, 7, 8, 9]
    value: Snowflake


class _AppCommandInterDataOptionNumber(_AppCommandInterDataOption):
    type: Literal[10]
    value: float


AppCommandInterDataOption = Union[
    _AppCommandInterDataOptionString,
    _AppCommandInterDataOptionInteger,
    _AppCommandInterDataOptionSubcommand,
    _AppCommandInterDataOptionBoolean,
    _AppCommandInterDataOptionSnowflake,
    _AppCommandInterDataOptionNumber,
]


class AppCommandResolvedPartialChannel(TypedDict):
    id: Snowflake
    type: ChannelType
    permissions: str
    name: str


class AppCommandInterDataResolved(TypedDict, total=False):
    users: Dict[Snowflake, User]
    members: Dict[Snowflake, Member]
    roles: Dict[Snowflake, Role]
    channels: Dict[Snowflake, AppCommandResolvedPartialChannel]


class _AppCommandInterDataOptional(TypedDict, total=False):
    options: List[AppCommandInterDataOption]
    resolved: AppCommandInterDataResolved
    target_id: Snowflake
    type: AppCommandType


class AppCommandInterData(_AppCommandInterDataOptional):
    id: Snowflake
    name: str


class _ComponentInterDataOptional(TypedDict, total=False):
    values: List[str]


class ComponentInterData(_ComponentInterDataOptional):
    custom_id: str
    component_type: ComponentType


InterData = Union[AppCommandInterData, ComponentInterData]


class _InterOptional(TypedDict, total=False):
    data: InterData
    guild_id: Snowflake
    channel_id: Snowflake
    member: Member
    user: User
    message: Message


class Inter(_InterOptional):
    id: Snowflake
    app_id: Snowflake
    type: InterType
    token: str
    version: int


class InterAppCommandCallbackData(TypedDict, total=False):
    tts: bool
    content: str
    embeds: List[Embed]
    allowed_mentions: AllowedMentions
    flags: int
    components: List[Component]


InterResponseType = Literal[1, 4, 5, 6, 7]


class _InterResponseOptional(TypedDict, total=False):
    data: InterAppCommandCallbackData


class InterResponse(_InterResponseOptional):
    type: InterResponseType


class MessageInter(TypedDict):
    id: Snowflake
    type: InterType
    name: str
    user: User





class _EditAppCommandOptional(TypedDict, total=False):
    description: str
    options: Optional[List[AppCommandOption]]
    type: AppCommandType


class EditAppCommand(_EditAppCommandOptional):
    name: str
    default_permission: bool
