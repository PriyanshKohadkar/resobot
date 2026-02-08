import os
import discord
from discord.ext import commands
from discord.ui import View, Button
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)

# ---------- MongoDB ----------
mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo["gif_bot"]
collection = db["gifs"]

collection.create_index(
    [("guild_id", 1), ("name", 1)],
    unique=True
)

@bot.event
async def on_ready():
  await bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Game("Pressure of a scorer"))
  print('we have logged in as {0.user}'.format(bot))

@bot.event
async def on_message(message):
  if message.author == bot.user:
    return
  if message.mention_everyone:
    return
  else:
       if bot.user.mentioned_in(message):
          await message.channel.send(f"I am here to help you!, {message.author.mention}")

  

  if message.content.lower().startswith('hi'):
    await message.channel.send('whatsup!')

# ---------- COMMANDS ----------

@bot.command()
async def addgif(ctx, name: str, link: str):
    try:
        collection.insert_one({
            "guild_id": ctx.guild.id,
            "name": name.lower(),
            "link": link
        })
        await ctx.send(f"✅ GIF added for `{name}`")
    except Exception:
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

# ---------- LIST WITH BUTTONS ----------

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
            await interaction.message.delete()
            self.stop()

        async def on_timeout(self):
            await self.msg.delete()

    msg = await ctx.send(embed=embed(page))
    await msg.edit(view=Paginator(msg))

# ---------- AUTO GIF RESPONSE ----------

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content.lower()
    for gif in collection.find({"guild_id": message.guild.id}):
        if gif["name"] in content:
            await message.channel.send(gif["link"])
            break

    await bot.process_commands(message)

bot.run(TOKEN)
