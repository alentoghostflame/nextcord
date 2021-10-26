:orphan:

.. _migrating_to_slash_commands:


Migrating To Slash Commands
============================
Differences
------------
One of the biggest difference's is the deprevation of CTX(Context) in the use of interaction

Old Commands:

.. codeblock:: python3
    
    @bot.command()
    async def example(ctx):
      await ctx.send("Hey!")
      
**This Way Is Deprecated For Slash Commands**

New Commands:

.. codeblock:: python3
    
    @bot.slash_command(name="example", guild_ids=[guild1, guild2])
    async def example(interaction):
      await interaction.response.send_message("Slash Commands POOOG!")
      
**Note:** You have to respond to messages using replys      

Converting Normal Commands To Slash Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
