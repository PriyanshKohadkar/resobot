import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from dotenv import load_dotenv
import brain

from radar_bot import setup_radar

load_dotenv()
from keep_alive import keep_alive
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
setup_radar(bot)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    await bot.tree.sync()
    await bot.change_presence(
        status=discord.Status.do_not_disturb,
        activity=discord.Game("Recommending Peak Movies🔥")
    )
    print(f"Logged in as {bot.user}")
    print("✅ Slash commands synced")
    print("aircraft radar setup completed!!")

async def main():
    async with bot:
        await bot.load_extension("movies")
        await bot.load_extension("summary")
        await bot.load_extension("intel")
        await bot.load_extension("gif")      # 👈 added
        await bot.load_extension("music")
        await bot.start(TOKEN)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

# ---------- AI BOT ----------
ALLOWED_CHANNELS = [1471906526326296731, 126278539286898697, 1262764932877779015, 1262765298495393864]

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        clean_text = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()

        if not clean_text:
            await message.reply("Bol na bhai, sun raha hoon!")
            return

        response = await brain.get_chat_response(message.author.name, clean_text)
        if message.channel.id in ALLOWED_CHANNELS:
            await message.reply(response)
        else:
            await message.reply(f"{response}", delete_after=180)

    if message.content.lower() == "hi":
        await message.channel.send("whatsup!")

    if message.content.lower().startswith("!intel"):
        query = message.content[7:].strip() or "latest updates"
        image_bytes = None
        if message.attachments:
            att = message.attachments[0]
            image_bytes = await att.read()
        from intel import fetch_gemini_intel
        response = await fetch_gemini_intel(query, image_bytes)
        await message.channel.send(response)

    await bot.process_commands(message)

# ---------- DELETED MESSAGES ----------
deleted_messages = {}

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    guild_id = message.guild.id
    channel_id = message.channel.id
    if guild_id not in deleted_messages:
        deleted_messages[guild_id] = {}
    if channel_id not in deleted_messages[guild_id]:
        deleted_messages[guild_id][channel_id] = []
    deleted_messages[guild_id][channel_id].append({
        "author": str(message.author),
        "content": message.content
    })
    deleted_messages[guild_id][channel_id] = deleted_messages[guild_id][channel_id][-10:]

@bot.tree.command(name="retrieve", description="Retrieve deleted messages")
@app_commands.describe(amount="Number of deleted messages to show")
async def retrieve(interaction: discord.Interaction, amount: int = 5):
    guild_id = interaction.guild.id
    channel_id = interaction.channel.id
    if guild_id not in deleted_messages or channel_id not in deleted_messages[guild_id]:
        await interaction.response.send_message("No deleted messages found.")
        return
    msgs = deleted_messages[guild_id][channel_id][-amount:]
    embed = discord.Embed(title="Deleted Messages", color=discord.Color.red())
    for msg in reversed(msgs):
        embed.add_field(
            name=f"{msg['author']}",
            value=msg["content"] if msg["content"] else "*No text content*",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

asyncio.run(main())
