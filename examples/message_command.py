import nextcord
from nextcord.ext import commands
from nextcord.application_command import user_command

bot = commands.Bot(command_prefix="/")

@bot.message_command(name="dump")
async def messagedump(interaction, message):
    await interaction.response.send_message(f"Data Dump: {interaction.data}")
    
bot.run("TOKEN")  
