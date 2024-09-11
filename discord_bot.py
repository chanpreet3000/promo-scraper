import discord
from discord import app_commands
from db import add_search, remove_search, get_all_searches

from logger import Logger


async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    Logger.critical(f"Command error occurred", error)
    embed = discord.Embed(
        title="Error",
        description="An unexpected error occurred. Please check logs or [Contact Developer](https://chanpreet-portfolio.vercel.app/#connect)",
        color=discord.Color.red()
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message(embed=embed)


class AmazonSearchBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        self.tree.on_error = on_command_error


client = AmazonSearchBot()


@client.event
async def on_ready():
    Logger.info(f'Logged in as {client.user} (ID: {client.user.id})')


@client.tree.command(name='add_amazon_search', description='Add a new Amazon product search term')
async def add_amazon_search(interaction: discord.Interaction, search_term: str):
    Logger.info('Adding search term Command invoked')
    await interaction.response.defer()
    await add_search(search_term)
    embed = discord.Embed(title="Success", description=f"Added: {search_term}", color=discord.Color.green())
    await interaction.followup.send(embed=embed)
    Logger.info('Added search term Command completed')


@client.tree.command(name='remove_amazon_search', description='Remove an existing Amazon product search term')
async def remove_amazon_search(interaction: discord.Interaction, search_term: str):
    Logger.info('Removing search term Command invoked')
    await interaction.response.defer()
    removed = await remove_search(search_term)
    if removed:
        embed = discord.Embed(title="Success", description=f"Removed: {search_term}", color=discord.Color.green())
    else:
        embed = discord.Embed(title="Not Found", description=f"Term not found: {search_term}",
                              color=discord.Color.orange())
    await interaction.followup.send(embed=embed)
    Logger.info('Removed search term Command completed')


@client.tree.command(name='list_amazon_searches', description='List all saved Amazon product search terms')
async def list_amazon_searches(interaction: discord.Interaction):
    Logger.info('Listing search terms Command invoked')
    await interaction.response.defer()
    searches = await get_all_searches()
    search_list = '\n'.join(searches) if searches else "No search terms found."
    embed = discord.Embed(title="Amazon Search Terms", description=search_list, color=discord.Color.blue())
    embed.set_footer(text=f"Total search terms: {len(searches)}")
    await interaction.followup.send(embed=embed)
    Logger.info('Listing search terms Command completed')
