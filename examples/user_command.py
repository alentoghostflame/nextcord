import nextcord
from nextcord import user_command
from nextcord.ext import commands

bot = commands.Bot(command_prefix="/")

@bot.user_command(name="dump")
async def userdump(interaction, member):
    await interaction.response.send_message(f"Member: {member}, Data Dump: {interaction.data}")
    
bot.run("TOKEN")   
