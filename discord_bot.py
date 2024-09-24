import asyncio
import datetime
import discord

from math import ceil
from discord import app_commands
from discord.ext import tasks

from config import DISCORD_MESSAGE_DELAY
from data_manager import DataManager
from db import add_search, remove_search, get_all_searches

from logger import Logger
from models import ProductDetails, ProcessedProductDetails
from scraper import startScraper
from utils import get_current_time

data_manager = DataManager()


async def send_promo_notification_to_discord(channel, processed_data: ProcessedProductDetails):
    products = processed_data.upserted
    total_products = len(processed_data.upserted) + len(processed_data.up_to_date) + len(processed_data.below_threshold)

    Logger.info(f'Sending promo notification to Discord. Channel: {channel.id}, Total Products: {total_products}')

    content = (
        f"@here\n\n"
        f"We've just completed a scan for product promotions. Here's what we found:\n\n"
        f"**Summary:**\n"
        f"- Total products scanned: **{total_products}**\n"
        f"- New eligible products: **{len(processed_data.upserted)}**\n"
        f"- Up-to-date products: **{len(processed_data.up_to_date)}**\n"
        f"- Products below threshold: **{len(processed_data.below_threshold)}**\n\n"
        f"Scan completed at: **{get_current_time()}**\n\n"
    )

    await channel.send(content=content)

    def create_product_embed(product: ProductDetails):
        promotion_url = f'https://www.amazon.co.uk/promotion/psp/{product.promotion_code}'

        embed = discord.Embed(
            title=product.product_title,
            url=product.product_url,
            color=discord.Color.green()
        ).set_thumbnail(url=product.product_image_url)

        embed.add_field(name="Price", value=product.product_price or 'N/A', inline=True)
        embed.add_field(name="Sales This Month", value=f"{product.product_sales}+ this month" or 'N/A',
                        inline=True)
        embed.add_field(name="Promotion", value=f"[{product.promotion_title}]({promotion_url})",
                        inline=True)

        return embed

    all_embeds = [create_product_embed(product) for product in products]

    chunk_size = 10
    total_chunks = ceil(len(all_embeds) / chunk_size)

    for i in range(total_chunks):
        embed_chunk = all_embeds[i * chunk_size: (i + 1) * chunk_size]

        try:
            await channel.send(embeds=embed_chunk)
            Logger.info(f"Promo notification sent successfully (Chunk {i + 1} of {total_chunks})")
        except Exception as error:
            Logger.error(f"Error sending promo notification (Chunk {i + 1} of {total_chunks})", error)

        if i < total_chunks - 1:
            await asyncio.sleep(DISCORD_MESSAGE_DELAY)

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
        self.amazon_cron.start()

    async def close(self):
        self.amazon_cron.cancel()
        await super().close()

    @tasks.loop(time=datetime.time(hour=1, minute=0, tzinfo=datetime.timezone.utc))
    async def amazon_cron(self):
        await run_amazon_cron()

    @amazon_cron.before_loop
    async def before_amazon_cron(self):
        await self.wait_until_ready()


client = AmazonSearchBot()


@client.event
async def on_ready():
    Logger.info(f'Logged in as {client.user} (ID: {client.user.id})')


@client.tree.command(name='ap_add_amazon_search', description='Add a new Amazon product search term')
async def add_amazon_search(interaction: discord.Interaction, search_term: str):
    Logger.info('Adding search term Command invoked')
    await interaction.response.defer()
    await add_search(search_term)
    embed = discord.Embed(title="Success", description=f"Added: {search_term}", color=discord.Color.green())
    await interaction.followup.send(embed=embed)
    Logger.info('Added search term Command completed')


@client.tree.command(name='ap_remove_amazon_search', description='Remove an existing Amazon product search term')
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


@client.tree.command(name='ap_list_amazon_searches', description='List all saved Amazon product search terms')
async def list_amazon_searches(interaction: discord.Interaction):
    Logger.info('Listing search terms Command invoked')
    await interaction.response.defer()
    searches = await get_all_searches()
    search_list = '\n'.join(searches) if searches else "No search terms found."
    embed = discord.Embed(title="Amazon Search Terms", description=search_list, color=discord.Color.blue())
    embed.set_footer(text=f"Total search terms: {len(searches)}")
    await interaction.followup.send(embed=embed)
    Logger.info('Listing search terms Command completed')


@client.tree.command(name="ap_add_notification_channel", description="Add a channel for stock notifications")
@app_commands.checks.has_permissions(administrator=True)
async def add_notification_channel(interaction: discord.Interaction):
    Logger.info(f"Adding notification channel: {interaction.channel.id}")
    data_manager.add_notification_channel(interaction.channel.id)

    embed = discord.Embed(
        title="✅ Notification Channel Added",
        description=f"This channel will now receive promotions notifications.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="ap_remove_notification_channel", description="Remove a channel from stock notifications")
@app_commands.checks.has_permissions(administrator=True)
async def remove_notification_channel(interaction: discord.Interaction):
    Logger.info(f"Removing notification channel: {interaction.channel.id}")
    data_manager.remove_notification_channel(interaction.channel.id)

    embed = discord.Embed(
        title="✅ Notification Channel Removed",
        description=f"This channel will no longer receive promotions notifications.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="ap_list_notification_channels", description="List all channels set for stock notifications")
@app_commands.checks.has_permissions(administrator=True)
async def list_notification_channels(interaction: discord.Interaction):
    channels = data_manager.get_notification_channels()
    channel_list = "\n".join([f"<#{channel_id}>" for channel_id in channels]) if channels else "No channels set."

    embed = discord.Embed(
        title="📢 Notification Channels",
        description=channel_list,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Total channels: {len(channels)}")
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="ap_set_monthly_sales_cutoff",
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


@client.tree.command(name="ap_get_monthly_sales_cutoff",
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


@client.tree.command(name="ap_run_scraper", description="Manually run the Amazon promotion scraper")
@app_commands.checks.has_permissions(administrator=True)
async def run_scraper(interaction: discord.Interaction):
    Logger.info("Manual scraper run initiated")
    embed = discord.Embed(
        title="Manually Triggered Bot",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)
    await run_amazon_cron()


async def run_amazon_cron():
    try:
        Logger.info("Starting daily Amazon promotion check")

        processed_data = await startScraper()

        channel_ids = data_manager.get_notification_channels()

        for channel_id in channel_ids:
            channel = client.get_channel(channel_id)
            if channel:
                await send_promo_notification_to_discord(channel, processed_data)
            else:
                Logger.warn(f"Channel with ID {channel_id} not found")

        Logger.info("Daily Amazon promotion check completed.")
    except Exception as e:
        Logger.critical("An error occurred in daily Amazon promotion check", e)
