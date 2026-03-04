import os
import re
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
from pymongo import MongoClient
from dotenv import load_dotenv
import brain

from radar_bot import setup_radar

load_dotenv()
from keep_alive import keep_alive
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
setup_radar(bot)
monitor_task = None
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

# ---------- SETTINGS HELPER ----------
def get_settings(guild_id: int):
    settings = settings_col.find_one({"guild_id": guild_id})
    if not settings:
        settings = {"guild_id": guild_id, "enabled": True, "delete_after": 15}
        settings_col.insert_one(settings)
    return settings

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    await bot.tree.sync()  # global sync
    await bot.change_presence(
        status=discord.Status.do_not_disturb,
        activity=discord.Game("Recommending Peak Movies🔥")
    )
    print(f"Logged in as {bot.user}")
    print("✅ Slash commands synced")
    print("aircraft radar setup completed!!")

async def main():
    async with bot:
        await bot.load_extension("movies")  # 👈 loads movies.py
        await bot.start(TOKEN)
        print("movies.py enabled")

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

    if not update:
        await ctx.send("❌ Provide a new name or link.")
        return

    result = collection.update_one(
        {"guild_id": ctx.guild.id, "name": old_name.lower()},
        {"$set": update}
    )
    await ctx.send("✅ GIF updated." if result.matched_count else "❌ GIF not found.")

@bot.command()
async def delgif(ctx, name: str):
    result = collection.delete_one({
        "guild_id": ctx.guild.id,
        "name": name.lower()
    })
    await ctx.send("🗑️ GIF deleted." if result.deleted_count else "❌ GIF not found.")

# ---------- LIST WITH PAGINATOR ----------
@bot.command()
async def listgifs(ctx, *, query: str = None):
    PER_PAGE = 10
    q = {"guild_id": ctx.guild.id}
    if query:
        q["name"] = {"$regex": query.lower()}

    gifs = list(collection.find(q))
    if not gifs:
        await ctx.send("📭 No matching GIFs found.")
        return

    pages = [gifs[i:i + PER_PAGE] for i in range(0, len(gifs), PER_PAGE)]
    page = 0

    def embed(i):
        e = discord.Embed(
            title="🎞️ GIF Keywords",
            description="\n".join(f"• `{g['name']}`" for g in pages[i]),
            color=discord.Color.blue()
        )
        e.set_footer(text=f"Page {i + 1}/{len(pages)}")
        return e

    class Paginator(View):
        def __init__(self, msg):
            super().__init__(timeout=60)
            self.msg = msg

        @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, _: Button):
            nonlocal page
            page = (page - 1) % len(pages)
            await interaction.response.edit_message(embed=embed(page), view=self)

        @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, _: Button):
            nonlocal page
            page = (page + 1) % len(pages)
            await interaction.response.edit_message(embed=embed(page), view=self)

        @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
        async def close(self, interaction: discord.Interaction, _: Button):
            await self.msg.delete()
            self.stop()

        async def on_timeout(self):
            await self.msg.delete()

    msg = await ctx.send(embed=embed(page))
    await msg.edit(view=Paginator(msg))

# ---------- SLASH COMMANDS ----------
@bot.tree.command(name="gifstop", description="Stop GIF responses")
async def gifstop(interaction: discord.Interaction):
    settings_col.update_one(
        {"guild_id": interaction.guild.id},
        {"$set": {"enabled": False}},
        upsert=True
    )
    await interaction.response.send_message("🛑 GIF responses disabled.", ephemeral=True)

@bot.tree.command(name="gifstart", description="Start GIF responses")
async def gifstart(interaction: discord.Interaction):
    settings_col.update_one(
        {"guild_id": interaction.guild.id},
        {"$set": {"enabled": True}},
        upsert=True
    )
    await interaction.response.send_message("✅ GIF responses enabled.", ephemeral=True)

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
    await interaction.response.send_message(f"⏱️ GIF delete time set to **{seconds}s**.", ephemeral=True)

#---------AIRCRAFT-TRACKING-COMMAND----------------------

CHANNEL_ID = 1471906526326296731  # your alert channel

#@bot.tree.command(name="radar", description="Control NMIA runway radar")
#async def radar(interaction: discord.Interaction):
 #   await radar_command(interaction)

#-----------AI BOT CONFIGURE------------
ALLOWED_CHANNELS=[1471906526326296731,126278539286898697,1262764932877779015,1262765298495393864 ]

# ---------- AUTO GIF RESPONSE ----------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return


    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        # Clean the mention from the text (e.g., "@Bot kaisa hai?" -> "kaisa hai?")
        clean_text = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
        
        if not clean_text:
            await message.reply("Bol na bhai, sun raha hoon!")
            return

        # Get response from our brain.py
        response = brain.get_chat_response(message.author.id, clean_text)
        if message.channel.id in ALLOWED_CHANNELS:
            # Specified channel mein permanent message
            await message.reply(response)
        else:
            # Doosre channels mein AI response 5 min (300s) baad delete ho jayega
            await message.reply(f"{response}", delete_after=180)
    



    settings = get_settings(message.guild.id)
    if not settings["enabled"]:
        await bot.process_commands(message)
        return

    words = message.content.lower().split()
    for word in words:
        if not word.startswith("?") or len(word) == 1:
            continue
        match = re.match(r"\?([a-zA-Z]+)", word)
        if not match:
            continue
        gif_name = match.group(1)
        gif = collection.find_one({
            "guild_id": message.guild.id,
            "name": gif_name
        })
        if gif:
            sent = await message.channel.send(gif["link"])
            await asyncio.sleep(settings["delete_after"])
            await sent.delete()
            break

    if message.content.lower() == "hi":
        await message.channel.send("whatsup!")

    await bot.process_commands(message)

asyncio.run(main())
