:orphan:

.. _migrating_to_slash_commands:


Migrating To Slash Commands
============================
Differences
------------
One of the biggest difference's is the deprevation of CTX(Context) in the use of interaction

Old Commands:

.. code-block:: python3
    
    @bot.command()
    async def example(ctx):
      await ctx.send("Hey!")
      
**This Way Is Deprecated For Slash Commands**

New Commands:

.. code-block:: python3
    
    @bot.slash_command()
    async def example(interaction):
      await interaction.response.send_message("Slash Commands POOOG!")
      
**Note:** You have to respond to messages using replys      

For more info on interaction Look at the API Docs

Converting Normal Commands To Slash Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
