# cogs/ipl.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import os

# Get from https://cricketdata.org/signup.aspx (free, 100 req/day)
CRICAPI_KEY = os.getenv("CRICAPI_KEY")
API_URL = f"https://api.cricapi.com/v1/currentMatches?apikey={CRICAPI_KEY}&offset=0"

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

def get_color(name: str) -> int:
    name_upper = name.upper()
    for abbr, color in TEAM_COLORS.items():
        if abbr in name_upper:
            return color
    return 0xFF6B00  # IPL orange fallback


class IPL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ipl", description="Get live IPL 2026 match scores 🏏")
    async def ipl(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not CRICAPI_KEY:
            await interaction.followup.send(
                "❌ `CRICAPI_KEY` env variable is not set. Add it to your Render env vars!",
                ephemeral=True
            )
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("❌ CricAPI returned an error. Try again later!", ephemeral=True)
                        return
                    data = await resp.json()
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ API timed out. Try again in a bit!", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Something went wrong: `{e}`", ephemeral=True)
            return

        if data.get("status") != "success":
            await interaction.followup.send("❌ CricAPI error: " + data.get("reason", "Unknown"), ephemeral=True)
            return

        matches = data.get("data", [])

        # Filter for IPL matches only
        ipl_matches = [
            m for m in matches
            if "ipl" in m.get("name", "").lower() or "indian premier league" in m.get("series", "").lower()
        ]

        if not ipl_matches:
            embed = discord.Embed(
                title="🏏 IPL 2026 — Live Scores",
                description="No IPL matches live right now. Check back during match time!\n\n> Matches are usually at **7:30 PM** and **3:30 PM IST**.",
                color=0xFF6B00
            )
            embed.set_footer(text="Powered by cricketdata.org")
            await interaction.followup.send(embed=embed)
            return

        embeds = []
        for match in ipl_matches[:5]:  # max 5 embeds
            name = match.get("name", "Unknown Match")
            status = match.get("status", "")
            match_type = match.get("matchType", "T20").upper()
            venue = match.get("venue", "Unknown Venue")
            date = match.get("date", "")
            teams = match.get("teams", [])
            scores = match.get("score", [])

            team1 = teams[0] if len(teams) > 0 else "Team 1"
            team2 = teams[1] if len(teams) > 1 else "Team 2"
            color = get_color(team1) if get_color(team1) != 0xFF6B00 else get_color(team2)

            embed = discord.Embed(
                title=f"🏏 {name}",
                color=color
            )
            embed.add_field(name="📍 Venue", value=venue, inline=False)
            embed.add_field(name="🎮 Format", value=match_type, inline=True)
            if date:
                embed.add_field(name="📅 Date", value=date, inline=True)

            # Scores
            if scores:
                score_text = ""
                for innings in scores:
                    inn_team = innings.get("inning", "?")
                    runs = innings.get("r", "?")
                    wickets = innings.get("w", "?")
                    overs = innings.get("o", "?")
                    score_text += f"**{inn_team}:** {runs}/{wickets} ({overs} ov)\n"
                embed.add_field(name="📊 Scores", value=score_text.strip(), inline=False)
            else:
                embed.add_field(name="📊 Scores", value="Match not started yet", inline=False)

            # Status
            if status:
                embed.add_field(name="📢 Status", value=status, inline=False)

            embed.set_footer(text="Live data • cricketdata.org • Free tier: 100 req/day")
            embeds.append(embed)

        await interaction.followup.send(embeds=embeds)


async def setup(bot):
    await bot.add_cog(IPL(bot))
