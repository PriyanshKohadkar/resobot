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

IPL_LEAGUE_ID = 52875307
IPL_SEASON    = 2026

LIVE_COLOUR     = 0xFF4500
RESULT_COLOUR   = 0x1DB954
UPCOMING_COLOUR = 0x5865F2
TABLE_COLOUR    = 0xFFD700
CARD_COLOUR     = 0x2B2D31

LIVE_STATES = {"in play", "lunch", "innings break", "drinks", "timeout", "tea", "stumps"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_ist() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def fmt_ist(utc_str: str) -> str:
    try:
        dt  = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        ist = dt + timedelta(hours=5, minutes=30)
        return ist.strftime("%d %b, %I:%M %p IST")
    except Exception:
        return utc_str

def state_of(match: dict) -> str:
    desc = match.get("state", {}).get("description", "").lower()
    if desc in LIVE_STATES:   return "live"
    if desc == "finished":    return "finished"
    if desc in {"scheduled", "match delayed", "no live coverage", "unknown"}: return "upcoming"
    return "other"

def score_field(team_data: dict) -> str:
    score = team_data.get("score", "—")
    info  = (team_data.get("info") or "").replace(" ov", " overs")
    return f"**{score}**  _{info}_" if info else f"**{score}**"

async def hl_get(session: aiohttp.ClientSession, endpoint: str, params: dict = None) -> dict | None:
    try:
        async with session.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params or {}) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception:
        return None

async def fetch_match_detail(session: aiohttp.ClientSession, match_id: str) -> dict | None:
    """Fetch full match detail including innings scorecard."""
    data = await hl_get(session, f"matches/{match_id}")
    if not data:
        return None
    # Response is a list with one item
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data.get("data") or data
    return None

async def fetch_ipl_matches(session: aiohttp.ClientSession) -> tuple[list, list, list]:
    """Fetch IPL matches across today/yesterday/tomorrow, return (live, finished, upcoming)."""
    ist_now   = now_ist()
    dates     = [
        (ist_now - timedelta(days=1)).strftime("%Y-%m-%d"),
        ist_now.strftime("%Y-%m-%d"),
        (ist_now + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]
    seen, all_matches = set(), []
    for date_str in dates:
        data = await hl_get(session, "matches", {
            "leagueId": IPL_LEAGUE_ID, "season": IPL_SEASON,
            "date": date_str, "timezone": "Asia/Kolkata", "limit": 20,
        })
        if data:
            raw = data.get("data") if isinstance(data, dict) else data
            if isinstance(raw, list):
                for m in raw:
                    if m.get("id") not in seen:
                        seen.add(m["id"])
                        all_matches.append(m)

    live     = [m for m in all_matches if state_of(m) == "live"]
    finished = sorted([m for m in all_matches if state_of(m) == "finished"],
                      key=lambda m: m.get("startTime") or "", reverse=True)
    upcoming = sorted([m for m in all_matches if state_of(m) == "upcoming"],
                      key=lambda m: m.get("startTime") or "")
    return live, finished, upcoming

# ── Scorecard embed builders ──────────────────────────────────────────────────
def build_batting_embed(innings: dict, match_title: str, inn_label: str, colour: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏏  {inn_label} — Batting",
        description=f"*{match_title}*",
        colour=colour,
    )
    batters = innings.get("inningBatsmen", [])
    # Only those who have batted (runs not None)
    batted  = [b for b in batters if b.get("runs") is not None]
    yet_to  = [b for b in batters if b.get("runs") is None]

    rows = ["`Batter                R    B   4s  6s    SR`"]
    for b in batted:
        name = b["player"]["name"][:19].ljust(19)
        r    = str(b.get("runs",  0)).ljust(4)
        ball = str(b.get("balls", 0)).ljust(4)
        fours= str(b.get("fours", 0)).ljust(3)
        sixes= str(b.get("sixes", 0)).ljust(3)
        try:
            sr = f"{float(b.get('battingStrikeRate') or 0):.1f}".ljust(5)
        except Exception:
            sr = "—".ljust(5)
        rows.append(f"`{name} {r} {ball} {fours} {sixes} {sr}`")

    embed.add_field(name="Scorecard", value="\n".join(rows) if len(rows) > 1 else "*No batting data yet*", inline=False)

    if yet_to:
        embed.add_field(
            name="Yet to bat",
            value=", ".join(b["player"]["name"] for b in yet_to),
            inline=False,
        )

    # Innings total from state if available
    total = innings.get("inningTotal")
    if total:
        embed.set_footer(text=f"Total: {total}  •  IPL 2026 • Highlightly")
    else:
        embed.set_footer(text="IPL 2026 • Highlightly")
    return embed

def build_bowling_embed(innings: dict, match_title: str, inn_label: str, colour: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚡  {inn_label} — Bowling",
        description=f"*{match_title}*",
        colour=colour,
    )
    bowlers = innings.get("inningBowlers", [])

    rows = ["`Bowler               O     M   R    W   Econ`"]
    for b in bowlers:
        name  = b["player"]["name"][:19].ljust(19)
        ovs   = str(b.get("overs",       0)).ljust(5)
        maid  = str(b.get("maidens",     0)).ljust(3)
        runs  = str(b.get("concededRuns",0)).ljust(4)
        wkts  = str(b.get("wickets",     0)).ljust(3)
        try:
            eco = f"{float(b.get('economy') or 0):.2f}".ljust(4)
        except Exception:
            eco = "—".ljust(4)
        rows.append(f"`{name} {ovs} {maid} {runs} {wkts} {eco}`")

    embed.add_field(
        name="Figures",
        value="\n".join(rows) if len(rows) > 1 else "*No bowling data yet*",
        inline=False,
    )
    embed.set_footer(text="IPL 2026 • Highlightly")
    return embed

# ── Paginated scorecard View ──────────────────────────────────────────────────
class ScorecardView(discord.ui.View):
    """
    Pagination across all innings.
    Each innings has 2 pages: Batting and Bowling.
    Buttons: ◀ Batting | Bowling ▶ | and Innings switcher if multiple innings.
    """
    def __init__(self, detail: dict, match_title: str, colour: int):
        super().__init__(timeout=120)
        self.match_title = match_title
        self.colour      = colour

        # Build innings list from statistics array
        # statistics[i] = { team: { name, inningBatsmen, inningBowlers, fallOfWickets }, inningNumber }
        raw_stats = detail.get("statistics", [])
        self.innings = []
        for stat in raw_stats:
            team = stat.get("team", {})
            if team.get("inningBatsmen") or team.get("inningBowlers"):
                self.innings.append({
                    "teamName":      team.get("name", "Unknown"),
                    "inningBatsmen": team.get("inningBatsmen", []),
                    "inningBowlers": team.get("inningBowlers", []),
                    "fallOfWickets": team.get("fallOfWickets", []),
                    "inningNumber":  stat.get("inningNumber", 1),
                })

        self.inn_idx = len(self.innings) - 1  # start at latest innings
        self.page    = 0  # 0 = batting, 1 = bowling
        self._update_buttons()

    def current_embed(self) -> discord.Embed:
        if not self.innings:
            return discord.Embed(title="Scorecard", description="No scorecard data available.", colour=self.colour)
        inn      = self.innings[self.inn_idx]
        inn_name = inn.get("teamName", f"Innings {self.inn_idx + 1}")
        label    = f"{inn_name} — Innings {inn.get('inningNumber', self.inn_idx + 1)}"
        if self.page == 0:
            return build_batting_embed(inn, self.match_title, label, self.colour)
        else:
            return build_bowling_embed(inn, self.match_title, label, self.colour)

    def _update_buttons(self):
        self.batting_btn.disabled  = self.page == 0
        self.bowling_btn.disabled  = self.page == 1
        self.prev_inn_btn.disabled = self.inn_idx <= 0
        self.next_inn_btn.disabled = self.inn_idx >= len(self.innings) - 1
        # Label shows which innings we're on
        total = len(self.innings)
        self.prev_inn_btn.label = f"◀ Inn {self.inn_idx}"        if self.inn_idx > 0     else "◀"
        self.next_inn_btn.label = f"Inn {self.inn_idx + 2} ▶"    if self.inn_idx < total - 1 else "▶"

    @discord.ui.button(label="🏏 Batting", style=discord.ButtonStyle.primary, disabled=True)
    async def batting_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="⚡ Bowling", style=discord.ButtonStyle.secondary)
    async def bowling_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey, disabled=True)
    async def prev_inn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.inn_idx -= 1
        self.page     = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
    async def next_inn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.inn_idx += 1
        self.page     = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

# ── Standard embed builders ───────────────────────────────────────────────────
def embed_live(match: dict) -> discord.Embed:
    home   = match["homeTeam"]["name"]
    away   = match["awayTeam"]["name"]
    state  = match["state"]
    teams  = state.get("teams", {})
    embed  = discord.Embed(
        title=f"🏏  LIVE — {home}  vs  {away}",
        description=f"_{state.get('report') or 'Match in progress'}_",
        colour=LIVE_COLOUR,
    )
    embed.set_author(name="IPL 2026 • Live Score")
    if "home" in teams:
        embed.add_field(name=home, value=score_field(teams["home"]), inline=False)
    if "away" in teams:
        embed.add_field(name=away, value=score_field(teams["away"]), inline=False)
    embed.add_field(name="Status", value=state.get("description", "In Play"), inline=True)
    embed.set_footer(text="IPL 2026 • Highlightly • Refreshes ~every minute")
    return embed

def embed_result(match: dict, index: int) -> discord.Embed:
    home  = match["homeTeam"]["name"]
    away  = match["awayTeam"]["name"]
    state = match["state"]
    teams = state.get("teams", {})
    date  = fmt_ist(match.get("startTime") or match.get("startDate", ""))
    embed = discord.Embed(
        title=f"🏆  Result #{index} — {home}  vs  {away}",
        description=f"_{state.get('report') or 'Match finished'}_",
        colour=RESULT_COLOUR,
    )
    if "home" in teams:
        embed.add_field(name=home, value=score_field(teams["home"]), inline=True)
    if "away" in teams:
        embed.add_field(name=away, value=score_field(teams["away"]), inline=True)
    embed.set_footer(text=f"📅 {date}  •  IPL 2026 • Highlightly")
    return embed

def embed_upcoming(matches: list) -> discord.Embed:
    embed = discord.Embed(title="🕐  IPL 2026 — Upcoming Matches", colour=UPCOMING_COLOUR)
    if not matches:
        embed.description = "No upcoming IPL matches found right now."
        return embed
    for m in matches[:8]:
        home   = m["homeTeam"]["name"]
        away   = m["awayTeam"]["name"]
        time   = fmt_ist(m.get("startTime") or m.get("startDate", ""))
        status = m["state"].get("description", "Scheduled")
        embed.add_field(name=f"{home}  vs  {away}", value=f"📅 {time}\n_{status}_", inline=False)
    embed.set_footer(text="IPL 2026 • Highlightly • Times in IST")
    return embed

def embed_standings(standings: list) -> discord.Embed:
    embed = discord.Embed(title="📊  IPL 2026 — Points Table", colour=TABLE_COLOUR)
    if not standings:
        embed.description = "Points table unavailable right now."
        return embed
    rows = ["`#   Team                 P    W    L    NRR     Pts`"]
    for e in standings:
        pos  = str(e.get("position",     "—")).ljust(3)
        team = e.get("team", {}).get("name", "?")[:19].ljust(19)
        p    = str(e.get("matchesPlayed","—")).ljust(4)
        w    = str(e.get("wins",         "—")).ljust(4)
        l    = str(e.get("loses",        "—")).ljust(4)
        try:    nrr = f"{float(e.get('netRunRate') or 0):+.3f}".ljust(7)
        except: nrr = "—".ljust(7)
        pts  = str(e.get("points", "—"))
        rows.append(f"`{pos} {team} {p} {w} {l} {nrr} {pts}`")
    embed.description = "\n".join(rows)
    embed.set_footer(text="IPL 2026 • Highlightly")
    return embed

# ── Cog ───────────────────────────────────────────────────────────────────────
class IPL(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ipl", description="IPL 2026: live score, recent results, scorecard, upcoming, or points table")
    @app_commands.describe(mode="Choose what to display")
    @app_commands.choices(mode=[
        app_commands.Choice(name="🏏  live score / recent results  (default)", value="live"),
        app_commands.Choice(name="📋  scorecard  (live or most recent match)", value="scorecard"),
        app_commands.Choice(name="🕐  upcoming matches",                        value="upcoming"),
        app_commands.Choice(name="📊  points table",                            value="points-table"),
    ])
    async def ipl(self, interaction: discord.Interaction, mode: app_commands.Choice[str] = None):
        await interaction.response.defer()
        selected = mode.value if mode else "live"

        async with aiohttp.ClientSession() as session:

            # ── POINTS TABLE ──────────────────────────────────────────────
            if selected == "points-table":
                data = await hl_get(session, "standings", {"leagueId": IPL_LEAGUE_ID, "season": IPL_SEASON})
                standings = []
                if data:
                    groups = data.get("groups", [])
                    if groups:
                        standings = groups[0].get("standings", [])
                await interaction.followup.send(embed=embed_standings(standings))
                return

            live, finished, upcoming = await fetch_ipl_matches(session)

            # ── UPCOMING ─────────────────────────────────────────────────
            if selected == "upcoming":
                if not upcoming:
                    ist_now = now_ist()
                    seen    = {m["id"] for m in live + finished + upcoming}
                    for i in range(2, 9):
                        future = (ist_now + timedelta(days=i)).strftime("%Y-%m-%d")
                        data   = await hl_get(session, "matches", {
                            "leagueId": IPL_LEAGUE_ID, "season": IPL_SEASON,
                            "date": future, "timezone": "Asia/Kolkata", "limit": 10,
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

            # ── SCORECARD ─────────────────────────────────────────────────
            if selected == "scorecard":
                # Use live match if available, else most recent finished
                target = live[0] if live else (finished[0] if finished else None)
                if not target:
                    await interaction.followup.send(embed=discord.Embed(
                        title="Scorecard",
                        description="No live or recent IPL match found right now.",
                        colour=CARD_COLOUR,
                    ))
                    return

                match_id    = target["id"]
                home        = target["homeTeam"]["name"]
                away        = target["awayTeam"]["name"]
                match_title = f"{home} vs {away}"
                colour      = LIVE_COLOUR if live else RESULT_COLOUR

                detail = await fetch_match_detail(session, match_id)
                if not detail or not detail.get("statistics"):
                    await interaction.followup.send(embed=discord.Embed(
                        title=f"Scorecard — {match_title}",
                        description="Scorecard data not available yet.",
                        colour=colour,
                    ))
                    return

                view  = ScorecardView(detail, match_title, colour)
                embed = view.current_embed()
                await interaction.followup.send(embed=embed, view=view)
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
