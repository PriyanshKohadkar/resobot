import os
import re
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

from keep_alive import keep_alive
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)

# ---------- MongoDB ----------
mongo = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    tls=True,
    tlsAllowInvalidCertificates=True
)

try:
    mongo.server_info()
    print("MongoDB connected successfully")
except Exception as e:
    print("MongoDB connection failed:", e)


db = mongo["gif_bot"]
collection = db["gifs"]
settings_col = db["settings"]

collection.create_index([("guild_id", 1), ("name", 1)], unique=True)
settings_col.create_index([("guild_id", 1)], unique=True)

# ---------- SETTINGS ----------
def get_settings(guild_id: int):
    settings = settings_col.find_one({"guild_id": guild_id})
    if not settings:
        settings = {
            "guild_id": guild_id,
            "enabled": True,
            "delete_after": 15
        }
        settings_col.insert_one(settings)
    return settings

# ---------- READY ----------
@bot.event
async def on_ready():
    await bot.tree.sync()  # global sync
    await bot.change_presence(
        status=discord.Status.do_not_disturb,
        activity=discord.Game("Pressure of a scorer")
    )
    print(f"Logged in as {bot.user}")
    print("✅ Slash commands synced")



# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

# ---------- TEXT COMMANDS ----------
@bot.command()
async def addgif(ctx, name: str, link: str):
    try:
        collection.insert_one({
            "guild_id": ctx.guild.id,
            "name": name.lower(),
            "link": link
        })
        await ctx.send(f"✅ GIF added for `{name}`")
    except:
        await ctx.send("⚠️ That keyword already exists.")

@bot.command()
async def editgif(ctx, old_name: str, new_name: str = None, new_link: str = None):
    update = {}
    if new_name:
        update["name"] = new_name.lower()
    if new_link:
        update["link"] = new_link

    result = collection.update_one(
        {"guild_id": ctx.guild.id, "name": old_name.lower()},
        {"$set": update}
    )

    await ctx.send("✅ GIF updated." if result.matched_count else "❌ GIF not found.")

@bot.command()
async def delgif(ctx, name: str):
    result = collection.delete_one(
        {"guild_id": ctx.guild.id, "name": name.lower()}
    )
    await ctx.send("🗑️ GIF deleted." if result.deleted_count else "❌ GIF not found.")

# ---------- SLASH COMMANDS ----------
@bot.tree.command(name="gifstop", description="Stop GIF responses")
async def gifstop(interaction: discord.Interaction):
    settings_col.update_one(
        {"guild_id": interaction.guild.id},
        {"$set": {"enabled": False}},
        upsert=True
    )
    await interaction.response.send_message(
        "🛑 GIF responses disabled.",
        ephemeral=True
    )

@bot.tree.command(name="gifstart", description="Start GIF responses")
async def gifstart(interaction: discord.Interaction):
    settings_col.update_one(
        {"guild_id": interaction.guild.id},
        {"$set": {"enabled": True}},
        upsert=True
    )
    await interaction.response.send_message(
        "✅ GIF responses enabled.",
        ephemeral=True
    )

@bot.tree.command(name="giftime", description="Set GIF auto-delete time")
@app_commands.describe(seconds="Time in seconds (1–300)")
async def giftime(interaction: discord.Interaction, seconds: int):
    if not 1 <= seconds <= 300:
        await interaction.response.send_message(
            "❌ Time must be between 1 and 300 seconds.",
            ephemeral=True
        )
        return

    settings_col.update_one(
        {"guild_id": interaction.guild.id},
        {"$set": {"delete_after": seconds}},
        upsert=True
    )

    await interaction.response.send_message(
        f"⏱️ GIF delete time set to **{seconds}s**.",
        ephemeral=True
    )

# ---------- AUTO GIF RESPONSE ----------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    if bot.user.mentioned_in(message):
        await message.channel.send(f"I am here to help you!, {message.author.mention}")

    if message.content.lower() == "hi":
        await message.channel.send("whatsup!")

    settings = get_settings(message.guild.id)
    if not settings["enabled"]:
        await bot.process_commands(message)
        return

    for word in message.content.lower().split():
        if not word.startswith("?"):
            continue

        match = re.match(r"\?([a-zA-Z]+)", word)
        if not match:
            continue

        gif = collection.find_one({
            "guild_id": message.guild.id,
            "name": match.group(1)
        })

        if gif:
            sent = await message.channel.send(gif["link"])
            await asyncio.sleep(settings["delete_after"])
            await sent.delete()
            break

    await bot.process_commands(message)

bot.run(TOKEN)
