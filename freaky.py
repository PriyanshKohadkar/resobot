import discord
from discord.ext import commands
from discord import app_commands
import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB setup ────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")

mongo = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    tls=True,
    tlsAllowInvalidCertificates=True
)

db = mongo["gif_bot"]
freaky_col  = db["freaky_leaderboard"]
votes_col   = db["freaky_pending_votes"]

# ── Constants ────────────────────────────────────────────────────────────────
STAR_EMOJI     = "⭐"
FIRE_EMOJI     = "🔥"
VOTE_THRESHOLD = 3
FIRE_THRESHOLD = 4
DYNO_ID        = 155149108183695360


# ── DB helpers ───────────────────────────────────────────────────────────────
def get_or_create(user_id: int, username: str):
    doc = freaky_col.find_one({"user_id": user_id})
    if not doc:
        freaky_col.insert_one({
            "user_id": user_id,
            "username": username,
            "points": 0,
            "starred_messages": [],
        })


def add_point(user_id: int, username: str, amount: int = 1):
    freaky_col.update_one(
        {"user_id": user_id},
        {"$inc": {"points": amount}, "$set": {"username": username}},
        upsert=True,
    )


def remove_point(user_id: int, amount: int = 1):
    freaky_col.update_one(
        {"user_id": user_id},
        {"$inc": {"points": -amount}},
    )


def already_starred(user_id: int, msg_id: int) -> bool:
    return freaky_col.find_one({"user_id": user_id, "starred_messages": msg_id}) is not None


def mark_starred(user_id: int, msg_id: int):
    freaky_col.update_one(
        {"user_id": user_id},
        {"$addToSet": {"starred_messages": msg_id}},
    )


def build_leaderboard_embed(guild: discord.Guild) -> discord.Embed:
    top = list(freaky_col.find().sort("points", -1))

    embed = discord.Embed(
        title="🌶️  Freaky Leaderboard",
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )

    if not top:
        embed.description = "No freaky points yet. Get weird, people."
        return embed

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, doc in enumerate(top):
        member = guild.get_member(doc["user_id"])
        name   = member.display_name if member else doc.get("username", f"<{doc['user_id']}>")
        medal  = medals[i] if i < 3 else f"`#{i+1}`"
        lines.append(f"{medal} **{name}** — {doc['points']} pts")

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"⭐ {VOTE_THRESHOLD} stars on a message = 1 freaky point")
    return embed


# ── Cog ──────────────────────────────────────────────────────────────────────
class Freaky(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── ⭐ Star listener — freaky message voting ──────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        emoji = str(payload.emoji)

        # ── ⭐ Star: awards point for freaky messages ─────────────────────────
        if emoji == STAR_EMOJI:
            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                return
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return

            # Ignore Dyno's messages
            if message.author.id == DYNO_ID:
                return

            author = message.author
            msg_id = message.id

            reaction_count = 0
            for r in message.reactions:
                if str(r.emoji) == STAR_EMOJI:
                    reaction_count = r.count
                    break

            if reaction_count == VOTE_THRESHOLD:
                if not already_starred(author.id, msg_id):
                    get_or_create(author.id, str(author))
                    add_point(author.id, str(author))
                    mark_starred(author.id, msg_id)
                    try:
                        await message.reply(
                            f"⭐ **+1 freaky point** awarded to {author.mention}!",
                            mention_author=False,
                            delete_after=8,
                        )
                    except discord.HTTPException:
                        pass

        # ── 🔥 Fire: approves a /fr add vote ─────────────────────────────────
        elif emoji == FIRE_EMOJI:
            if not votes_col.find_one({"message_id": payload.message_id}):
                return

            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                return
            try:
                vote_msg = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return

            reaction_count = 0
            for r in vote_msg.reactions:
                if str(r.emoji) == FIRE_EMOJI:
                    reaction_count = r.count
                    break

            if reaction_count == FIRE_THRESHOLD:
                vote = votes_col.find_one_and_delete({"message_id": payload.message_id})
                if not vote:
                    return
                target_id   = vote["target_id"]
                target_name = vote["target_name"]
                points      = vote["points"]

                get_or_create(target_id, target_name)
                add_point(target_id, target_name, points)

                try:
                    await vote_msg.edit(
                        content=f"🔥 Vote passed! **+{points}** freaky point(s) awarded to <@{target_id}>!",
                        embed=None,
                    )
                except discord.HTTPException:
                    pass

    # ── Subcommand group ──────────────────────────────────────────────────────
    fr_group = app_commands.Group(name="fr", description="Freaky leaderboard 🌶️")

    @fr_group.command(name="leaderboard", description="Show the freaky leaderboard")
    async def fr_leaderboard(self, interaction: discord.Interaction):
        embed = build_leaderboard_embed(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @fr_group.command(name="add", description="Vote to award freaky points to a user 🔥")
    @app_commands.describe(
        user="user to award points to",
        points="number of points to award (default 1)",
    )
    async def fr_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        points: int = 1,
    ):
        if points < 1:
            await interaction.response.send_message("❌ Points must be at least 1.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔥 Freaky Point Vote",
            description=(
                f"{interaction.user.mention} wants to award **{points}** freaky point(s) to {user.mention}.\n\n"
                f"React with 🔥 to approve! Need **{FIRE_THRESHOLD}** fires."
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )

        await interaction.response.send_message(embed=embed)
        vote_msg = await interaction.original_response()
        await vote_msg.add_reaction(FIRE_EMOJI)

        votes_col.update_one(
            {"message_id": vote_msg.id},
            {"$set": {
                "message_id":  vote_msg.id,
                "target_id":   user.id,
                "target_name": str(user),
                "points":      points,
            }},
            upsert=True,
        )

    @fr_group.command(name="remove", description="Remove 1 freaky point from a user")
    @app_commands.describe(user="user to remove a point from")
    async def fr_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        doc = freaky_col.find_one({"user_id": user.id})
        if not doc or doc["points"] <= 0:
            await interaction.response.send_message(
                f"⚠️ {user.mention} has no freaky points to remove.", ephemeral=True
            )
            return
        remove_point(user.id, 1)
        await interaction.response.send_message(
            f"✅ Removed **1** freaky point from {user.mention}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Freaky(bot))
