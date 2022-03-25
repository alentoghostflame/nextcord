import nextcord
from nextcord import CommandPermission, Interaction, Permissions, permissions, Role
from nextcord.ext import commands

TESTING_GUILD_ID = 123456789  # Replace with your testing guild id

bot = commands.Bot(command_prefix="$")


# checking member_default_permissions without decorators
@bot.slash_command(
    description='Bans a member', 
    guild_ids=[TESTING_GUILD_ID], 
    member_default_permissions = Permissions(ban_members = True)
)
async def ban(interaction: Interaction, member: nextcord.Member):
    await member.ban()
    await interaction.response.send_message(f"{member.mention} has been banned")

# checking member_default_permissions with decorators
@bot.slash_command(description='Kicks a member', guild_ids=[TESTING_GUILD_ID])
@permissions.has_permissions(kick_members = True)
async def kick(interaction: Interaction, member: nextcord.Member):
    await member.kick()
    await interaction.response.send_message(f"{member.mention} has been kicked")
    
# restricting a command to guilds
@bot.slash_command(
    description='Command without dm_permission', 
    guild_ids=[TESTING_GUILD_ID]
) # or you can set dm_permission = False here
@permissions.guild_only()
async def guild_command(interaction: Interaction):
    await interaction.response.send_message(f"This command is only available in guilds")
    
# restricting a command to roles - same way works with channels/members
@bot.slash_command(description='role only command', guild_ids=[TESTING_GUILD_ID])
@permissions.guild_permissions(
    guild_id=TESTING_GUILD_ID, 
    perms=[CommandPermission(target=123456789, permission=True, target_type=Role)]
)
async def role_only(interaction: Interaction):
    await interaction.response.send_message(f"This command is only available for the role")


bot.run("token")
