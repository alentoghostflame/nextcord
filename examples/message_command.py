import nextcord
from nextcord import user_command
from nextcord.ext import commands

bot = commands.Bot(command_prefix="/")

@bot.message_command(name="dump")
async def messagedump(interaction, message):
    await interaction.response.send_message(f"Data Dump: {interaction.data}")
    
bot.run("TOKEN")  
