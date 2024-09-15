# Amazon Promotions Discord Bot

## Overview

This Discord bot monitors Amazon product searches for promotions and notifies users in designated Discord channels. It
uses web scraping techniques to find products with active promotions and filters them based on monthly sales data.

## Features

- Automated Amazon product searches
- Promotion notifications in Discord channels
- Customizable search terms
- Multiple notification channels support
- Minimum monthly sales cutoff filter

## Installation

1. Clone the repository
2. Install required dependencies: `pip install -r requirements.txt`
3. Set up your Discord bot and get the token
4. Configure the bot token in `.env` and other settings in `config.py`
5. Run the bot: `python main.py`

## Commands

All commands are prefixed with `ap_` (Amazon Promotions).

### Search Management

- `/ap_add_amazon_search <search_term>`: Add a new Amazon product search term
- `/ap_remove_amazon_search <search_term>`: Remove an existing Amazon product search term
- `/ap_list_amazon_searches`: List all saved Amazon product search terms

### Channel Management

- `/ap_add_notification_channel`: Add the current channel for promotion notifications
- `/ap_remove_notification_channel`: Remove the current channel from promotion notifications
- `/ap_list_notification_channels`: List all channels set for promotion notifications

### Settings

- `/ap_set_monthly_sales_cutoff <cutoff>`: Set the minimum monthly sales cutoff for notifications
- `/ap_get_monthly_sales_cutoff`: Get the current minimum monthly sales cutoff

## Scheduled Tasks

The bot runs a scheduled task every 6 hours to check for new promotions and send notifications to all registered
channels.