import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
HIGHLIGHTLY_KEY = os.getenv("HIGHLIGHTLY_API_KEY")
BASE_URL        = "https://cricket.highlightly.net"
HEADERS         = {"x-rapidapi-key": HIGHLIGHTLY_KEY}

IPL_LEAGUE_ID   = 52875307   # IPL 2026 — confirmed
IPL_SEASON      = 2026

LIVE_COLOUR     = 0xFF4500
RESULT_COLOUR   = 0x1DB954
UPCOMING_COLOUR = 0x5865F2
TABLE_COLOUR    = 0xFFD700

LIVE_STATES = {"in play", "lunch", "innings break", "drinks", "timeout", "tea", "stumps"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_ist() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def fmt_ist(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        ist = dt + timedelta(hours=5, minutes=30)
        return ist.strftime("%d %b, %I:%M %p IST")
    except Exception:
        return utc_str

def state_of(match: dict) -> str:
    desc = match.get("state", {}).get("description", "").lower()
    if desc in LIVE_STATES:
        return "live"
    if desc == "finished":
        return "finished"
    if desc in {"scheduled", "match delayed", "no live coverage", "unknown"}:
        return "upcoming"
    return "other"

def score_field(team_name: str, team_data: dict) -> str:
    score = team_data.get("score", "—")
    info  = (team_data.get("info") or "").replace("ov", "overs")
    return f"**{score}**  _{info}_" if info else f"**{score}**"

async def hl_get(session: aiohttp.ClientSession, endpoint: str, params: dict) -> dict | None:
    try:
        async with session.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception:
        return None

# ── Embed builders ────────────────────────────────────────────────────────────
def embed_live(match: dict) -> discord.Embed:
    home   = match["homeTeam"]["name"]
    away   = match["awayTeam"]["name"]
    state  = match["state"]
    report = state.get("report") or "Match in progress"
    teams  = state.get("teams", {})

    embed = discord.Embed(
        title=f"🏏  LIVE — {home}  vs  {away}",
        description=f"_{report}_",
        colour=LIVE_COLOUR,
    )
    embed.set_author(name="IPL 2026 • Live Score")

    if "home" in teams:
        embed.add_field(name=home, value=score_field(home, teams["home"]), inline=False)
    if "away" in teams:
        embed.add_field(name=away, value=score_field(away, teams["away"]), inline=False)

    embed.add_field(name="Status", value=state.get("description", "In Play"), inline=True)
    embed.set_footer(text="IPL 2026 • Highlightly • Refreshes ~every minute")
    return embed

def embed_result(match: dict, index: int) -> discord.Embed:
    home   = match["homeTeam"]["name"]
    away   = match["awayTeam"]["name"]
    state  = match["state"]
    report = state.get("report") or "Match finished"
    teams  = state.get("teams", {})
    date   = fmt_ist(match.get("startTime") or match.get("startDate", ""))

    embed = discord.Embed(
        title=f"🏆  Result #{index} — {home}  vs  {away}",
        description=f"_{report}_",
        colour=RESULT_COLOUR,
    )
    if "home" in teams:
        embed.add_field(name=home, value=score_field(home, teams["home"]), inline=True)
    if "away" in teams:
        embed.add_field(name=away, value=score_field(away, teams["away"]), inline=True)

    embed.set_footer(text=f"📅 {date}  •  IPL 2026 • Highlightly")
    return embed

def embed_upcoming(matches: list) -> discord.Embed:
    embed = discord.Embed(title="🕐  IPL 2026 — Upcoming Matches", colour=UPCOMING_COLOUR)
    if not matches:
        embed.description = "No upcoming IPL matches found right now."
        return embed

    for m in matches[:8]:
        home  = m["homeTeam"]["name"]
        away  = m["awayTeam"]["name"]
        time  = fmt_ist(m.get("startTime") or m.get("startDate", ""))
        status = m["state"].get("description", "Scheduled")
        embed.add_field(
            name=f"{home}  vs  {away}",
            value=f"📅 {time}\n_{status}_",
            inline=False,
        )

    embed.set_footer(text="IPL 2026 • Highlightly • Times in IST")
    return embed

def embed_standings(standings: list) -> discord.Embed:
    embed = discord.Embed(title="📊  IPL 2026 — Points Table", colour=TABLE_COLOUR)
    if not standings:
        embed.description = "Points table unavailable right now."
        return embed

    rows = ["`#   Team                 P    W    L    NRR     Pts`"]
    for e in standings:
        pos  = str(e.get("position", "—")).ljust(3)
        team = e.get("team", {}).get("name", "?")[:19].ljust(19)
        p    = str(e.get("matchesPlayed", "—")).ljust(4)
        w    = str(e.get("wins",          "—")).ljust(4)
        l    = str(e.get("loses",         "—")).ljust(4)
        try:
            nrr = f"{float(e.get('netRunRate') or e.get('nrr') or 0):+.3f}".ljust(7)
        except Exception:
            nrr = "—".ljust(7)
        pts = str(e.get("points", "—"))
        rows.append(f"`{pos} {team} {p} {w} {l} {nrr} {pts}`")

    embed.description = "\n".join(rows)
    embed.set_footer(text="IPL 2026 • Highlightly")
    return embed

# ── Cog ───────────────────────────────────────────────────────────────────────
class IPL(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ipl", description="IPL 2026: live score, recent results, upcoming matches, or points table")
    @app_commands.describe(mode="Choose what to display")
    @app_commands.choices(mode=[
        app_commands.Choice(name="🏏  live score / recent results  (default)", value="live"),
        app_commands.Choice(name="🕐  upcoming matches",                        value="upcoming"),
        app_commands.Choice(name="📊  points table",                            value="points-table"),
    ])
    async def ipl(self, interaction: discord.Interaction, mode: app_commands.Choice[str] = None):
        await interaction.response.defer()
        selected = mode.value if mode else "live"

        async with aiohttp.ClientSession() as session:

            # ── POINTS TABLE ──────────────────────────────────────────────
            if selected == "points-table":
                data = await hl_get(session, "standings", {
                    "leagueId": IPL_LEAGUE_ID,
                    "season":   IPL_SEASON,
                })
                standings = []
                if data:
                    groups = data.get("groups", [])
                    if groups:
                        standings = groups[0].get("standings", [])
                await interaction.followup.send(embed=embed_standings(standings))
                return

            # ── Fetch matches for today + yesterday (covers live + recent) ─
            ist_now  = now_ist()
            today    = ist_now.strftime("%Y-%m-%d")
            yesterday = (ist_now - timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow  = (ist_now + timedelta(days=1)).strftime("%Y-%m-%d")

            all_matches = []
            for date_str in [today, yesterday, tomorrow]:
                data = await hl_get(session, "matches", {
                    "leagueId": IPL_LEAGUE_ID,
                    "season":   IPL_SEASON,
                    "date":     date_str,
                    "timezone": "Asia/Kolkata",
                    "limit":    20,
                })
                if data:
                    raw = data.get("data") if isinstance(data, dict) else data
                    if isinstance(raw, list):
                        all_matches.extend(raw)

            # Deduplicate by match ID
            seen, merged = set(), []
            for m in all_matches:
                if m.get("id") not in seen:
                    seen.add(m["id"])
                    merged.append(m)

            live     = [m for m in merged if state_of(m) == "live"]
            finished = [m for m in merged if state_of(m) == "finished"]
            upcoming = [m for m in merged if state_of(m) == "upcoming"]

            # Sort finished: most recent first
            finished.sort(key=lambda m: m.get("startTime") or m.get("startDate") or "", reverse=True)
            # Sort upcoming: soonest first
            upcoming.sort(key=lambda m: m.get("startTime") or m.get("startDate") or "")

            # ── UPCOMING MODE ─────────────────────────────────────────────
            if selected == "upcoming":
                # If nothing in today/tomorrow window, fetch next 7 days
                if not upcoming:
                    for i in range(2, 8):
                        future_date = (ist_now + timedelta(days=i)).strftime("%Y-%m-%d")
                        data = await hl_get(session, "matches", {
                            "leagueId": IPL_LEAGUE_ID,
                            "season":   IPL_SEASON,
                            "date":     future_date,
                            "timezone": "Asia/Kolkata",
                            "limit":    10,
                        })
                        if data:
                            raw = data.get("data") if isinstance(data, dict) else data
                            if isinstance(raw, list):
                                for m in raw:
                                    if m.get("id") not in seen and state_of(m) == "upcoming":
                                        seen.add(m["id"])
                                        upcoming.append(m)
                        if len(upcoming) >= 5:
                            break

                await interaction.followup.send(embed=embed_upcoming(upcoming))
                return

            # ── LIVE / RESULTS (default) ──────────────────────────────────
            if live:
                await interaction.followup.send(embeds=[embed_live(m) for m in live[:10]])
            elif finished:
                await interaction.followup.send(embeds=[embed_result(m, i) for i, m in enumerate(finished[:2], 1)])
            else:
                await interaction.followup.send(embed=discord.Embed(
                    title="IPL 2026",
                    description="No live or recent IPL matches right now.\nCheck back closer to match time! 🏏",
                    colour=RESULT_COLOUR,
                ))


async def setup(bot: commands.Bot):
    await bot.add_cog(IPL(bot))
