# cogs/ipl.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import os
from datetime import datetime, timezone

CRICAPI_KEY = os.getenv("CRICAPI_KEY")
BASE_URL = "https://api.cricapi.com/v1"

TEAM_COLORS = {
    "MI":   0x004BA0,
    "CSK":  0xFDB913,
    "RCB":  0xEC1C24,
    "KKR":  0x3A225D,
    "DC":   0x0078BC,
    "PBKS": 0xED1F27,
    "RR":   0x254AA5,
    "SRH":  0xF7A721,
    "GT":   0x1C1C1C,
    "LSG":  0xA2FFFF,
}

def get_color(team1: str, team2: str = "") -> int:
    combined = (team1 + " " + team2).upper()
    for abbr, color in TEAM_COLORS.items():
        if abbr in combined:
            return color
    return 0xFF6B00

def is_ipl(match: dict) -> bool:
    name = match.get("name", "").lower()
    series = match.get("series", "").lower()
    return "ipl" in name or "indian premier league" in series

def build_score_field(scores: list) -> str:
    if not scores:
        return "No score available"
    lines = []
    for inn in scores:
        team = inn.get("inning", "?")
        r, w, o = inn.get("r", "?"), inn.get("w", "?"), inn.get("o", "?")
        lines.append(f"**{team}:** {r}/{w} ({o} ov)")
    return "\n".join(lines)

def build_embed(match: dict, label: str) -> discord.Embed:
    name = match.get("name", "Unknown Match")
    status = match.get("status", "")
    venue = match.get("venue", "Unknown Venue")
    date = match.get("date", "")
    teams = match.get("teams", [])
    scores = match.get("score", [])

    team1 = teams[0] if len(teams) > 0 else ""
    team2 = teams[1] if len(teams) > 1 else ""
    color = get_color(team1, team2)

    embed = discord.Embed(title=f"🏏 {label} — {name}", color=color)
    embed.add_field(name="📍 Venue", value=venue, inline=False)
    if date:
        embed.add_field(name="📅 Date", value=date, inline=True)
    if scores:
        embed.add_field(name="📊 Scores", value=build_score_field(scores), inline=False)
    elif "Upcoming" in label:
        embed.add_field(name="📊 Scores", value="Match hasn't started yet", inline=False)
    if status:
        embed.add_field(name="📢 Status", value=status, inline=False)
    embed.set_footer(text="Powered by cricketdata.org")
    return embed


class IPL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_matches(self, endpoint: str) -> list | None:
        if not CRICAPI_KEY:
            return None
        url = f"{BASE_URL}/{endpoint}?apikey={CRICAPI_KEY}&offset=0"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if data.get("status") != "success":
                        return None
                    return data.get("data", [])
        except Exception:
            return None

    def parse_date(self, m: dict) -> datetime:
        try:
            return datetime.fromisoformat(m.get("dateTimeGMT", "").replace("Z", "+00:00"))
        except Exception:
            return datetime.max.replace(tzinfo=timezone.utc)

    @app_commands.command(name="ipl", description="IPL 2026 live score or upcoming match 🏏")
    @app_commands.describe(mode="What to show — defaults to live score")
    @app_commands.choices(mode=[
        app_commands.Choice(name="upcoming", value="upcoming"),
    ])
    async def ipl(self, interaction: discord.Interaction, mode: app_commands.Choice[str] = None):
        await interaction.response.defer()

        if not CRICAPI_KEY:
            await interaction.followup.send("❌ `CRICAPI_KEY` env var not set!", ephemeral=True)
            return

        # ── /ipl upcoming ──────────────────────────────────────
        if mode and mode.value == "upcoming":
            matches = await self.fetch_matches("matches")
            if matches is None:
                await interaction.followup.send("❌ Could not reach CricAPI. Try again later!", ephemeral=True)
                return

            now = datetime.now(timezone.utc)
            ipl_upcoming = [
                m for m in matches
                if is_ipl(m) and not m.get("matchStarted", False) and self.parse_date(m) > now
            ]
            ipl_upcoming.sort(key=self.parse_date)

            if not ipl_upcoming:
                embed = discord.Embed(
                    title="🏏 IPL 2026 — Upcoming",
                    description="No upcoming matches found. Season might be over!",
                    color=0xFF6B00
                )
                embed.set_footer(text="Powered by cricketdata.org")
                await interaction.followup.send(embed=embed)
                return

            next_match = ipl_upcoming[0]
            dt = self.parse_date(next_match)
            unix_ts = int(dt.timestamp())
            time_str = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"

            embed = build_embed(next_match, "📅 Upcoming")
            for i, field in enumerate(embed.fields):
                if field.name == "📅 Date":
                    embed.set_field_at(i, name="📅 Date & Time", value=time_str, inline=False)
                    break

            await interaction.followup.send(embed=embed)
            return

        # ── /ipl (default: live → recent fallback) ─────────────
        matches = await self.fetch_matches("currentMatches")
        if matches is None:
            await interaction.followup.send("❌ Could not reach CricAPI. Try again later!", ephemeral=True)
            return

        ipl_live = [m for m in matches if is_ipl(m) and not m.get("matchEnded", False)]

        if ipl_live:
            embeds = [build_embed(m, "🔴 Live") for m in ipl_live[:5]]
            await interaction.followup.send(embeds=embeds)
            return

        # Fallback to recent result
        recent_matches = await self.fetch_matches("matches")
        if recent_matches is None:
            await interaction.followup.send("❌ Could not fetch recent matches.", ephemeral=True)
            return

        ipl_ended = [m for m in recent_matches if is_ipl(m) and m.get("matchEnded", False)]

        if not ipl_ended:
            embed = discord.Embed(
                title="🏏 IPL 2026",
                description="No live or recent IPL matches found.\nTry `/ipl mode:upcoming` to see what's next!",
                color=0xFF6B00
            )
            embed.set_footer(text="Powered by cricketdata.org")
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send(embed=build_embed(ipl_ended[0], "✅ Recent Result"))


async def setup(bot):
    await bot.add_cog(IPL(bot))
