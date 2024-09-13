import asyncio
from math import ceil

import discord
from discord import app_commands
from discord.ext import tasks

from config import DISCORD_MESSAGE_DELAY
from data_manager import DataManager
from db import add_search, remove_search, get_all_searches, get_recent_products, upsert_product

from logger import Logger
from scraper import startBot
from utils import get_current_time

data_manager = DataManager()


async def send_promo_notification_to_discord(channel, promo_code: str, promo_data: dict):
    Logger.info('Sending promo notification to Discord',
                {'promo_code': promo_code, 'promo_data': promo_data})

    def create_product_embed(product):
        embed = discord.Embed(
            title=product['product_title'],
            url=product['product_url'],
            color=discord.Color.green()
        ).set_thumbnail(url=product['product_img'])

        embed.add_field(name="Current Price", value=product['current_price'] or 'N/A', inline=True)
        embed.add_field(name="Sales This Month", value=f"{product['sales_last_month']}+ this month" or 'N/A',
                        inline=True)
        embed.add_field(name="Promo", value=f"[{promo_data['title']}]({promo_data['promotion_url']})",
                        inline=True)

        return embed

    content = f"**{promo_data['title']}**\n Promotion Code - [{promo_code}]({promo_data['promotion_url']})"

    all_embeds = [create_product_embed(product) for product in promo_data['products']]

    chunk_size = 10
    total_chunks = ceil(len(all_embeds) / chunk_size)

    for i in range(total_chunks):
        embed_chunk = all_embeds[i * chunk_size: (i + 1) * chunk_size]

        try:
            if i == 0:
                await channel.send(content=content, embeds=embed_chunk)
            else:
                await channel.send(embeds=embed_chunk)
            Logger.info(f"Promo notification sent successfully (Chunk {i + 1} of {total_chunks})")
        except Exception as error:
            Logger.error(f"Error sending promo notification (Chunk {i + 1} of {total_chunks})", error)

        if i < total_chunks - 1:
            await asyncio.sleep(DISCORD_MESSAGE_DELAY)

    if total_chunks == 0:
        await channel.send(content=content,
                           embed=discord.Embed(title="All products already notified!", color=discord.Color.red()))

    Logger.info('Finished sending promo notification to Discord')


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
    amazon_cron.start()


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


@client.tree.command(name="set_channel", description="Set the channel for stock notifications")
@app_commands.checks.has_permissions(administrator=True)
async def set_channel(interaction: discord.Interaction):
    Logger.info(f"Setting notification channel: {interaction.channel.id}")
    data_manager.set_notification_channel(interaction.channel.id)

    embed = discord.Embed(
        title="✅ Notification Channel Set",
        description=f"This channel will now receive promotions notifications.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="set_monthly_sales_cutoff",
                     description="Set the minimum monthly sales cutoff for notifications")
@app_commands.checks.has_permissions(administrator=True)
async def set_monthly_sales_cutoff(interaction: discord.Interaction, cutoff: int):
    Logger.info(f"Setting monthly sales cutoff: {cutoff}")
    data_manager.set_monthly_sales_cutoff(cutoff)

    embed = discord.Embed(
        title="✅ Monthly Sales Cutoff Set",
        description=f"The minimum monthly sales cutoff has been set to {cutoff}.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="get_monthly_sales_cutoff",
                     description="Get the current minimum monthly sales cutoff for notifications")
async def get_monthly_sales_cutoff(interaction: discord.Interaction):
    cutoff = data_manager.get_monthly_sales_cutoff()
    Logger.info(f"Getting monthly sales cutoff: {cutoff}")

    embed = discord.Embed(
        title="📊 Current Monthly Sales Cutoff",
        description=f"The current minimum monthly sales cutoff is set to {cutoff}.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)


@tasks.loop(seconds=60 * 60 * 24)
async def amazon_cron():
    try:
        Logger.info("Starting scheduled Cron")

        promo_products_details_dict = await startBot()
        recent_products = await get_recent_products(days=7)

        filtered_promo_products = {}

        # Filter the products
        for promo_code, value in promo_products_details_dict.items():
            filtered_products = []
            for product in value['products']:
                if product['asin'] not in recent_products and product[
                    'sales_last_month'] >= data_manager.get_monthly_sales_cutoff():
                    await upsert_product(product['asin'], promo_code)
                    filtered_products.append(product)

            filtered_promo_products[promo_code] = {**value, 'products': filtered_products}

        channel_id = data_manager.get_notification_channel()
        channel = client.get_channel(channel_id)

        for promo_code, value in filtered_promo_products.items():
            await send_promo_notification_to_discord(channel, promo_code, value)

        await channel.send(content=f'@here Please check the above products with promotions.\n**{get_current_time()}**')

        Logger.info(f"Scheduled cron completed. Next run in {60 * 60 * 24} seconds.")
    except Exception as e:
        Logger.critical("An error occurred in scheduled cron", e)
