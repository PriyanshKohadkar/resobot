# cogs/f1.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime, timezone

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"

TYRE_EMOJI = {"SOFT": "🔴", "MEDIUM": "🟡", "HARD": "⬜", "INTER": "🟢", "WET": "🔵"}
F1_RED = 0xE8002D

POSITION_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# ── Helpers ────────────────────────────────────────────────────

async def jolpica_get(session: aiohttp.ClientSession, path: str) -> dict | None:
    url = f"{JOLPICA_BASE}{path}.json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None

def format_time(ms: str | None) -> str:
    if not ms:
        return "N/A"
    return ms

def ordinal(n: int) -> str:
    return f"{n}{'th' if 11<=n%100<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

# ── Pagination View ────────────────────────────────────────────

class PaginatedEmbed(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0
        self.author_id = author_id
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1
        for page in self.pages:
            page.set_footer(text=f"Page {self.current + 1}/{len(self.pages)} • Powered by Jolpica/Ergast")

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("These aren't your buttons!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

def paginate(entries: list[str], title: str, color: int, per_page: int = 10) -> list[discord.Embed]:
    pages = []
    for i in range(0, len(entries), per_page):
        chunk = entries[i:i + per_page]
        embed = discord.Embed(title=title, description="\n".join(chunk), color=color)
        pages.append(embed)
    return pages


# ── Cog ───────────────────────────────────────────────────────

class F1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="f1", description="F1 live session, standings, results & more 🏎️")
    @app_commands.describe(mode="What to show — defaults to live/next race")
    @app_commands.choices(mode=[
        app_commands.Choice(name="results", value="results"),
        app_commands.Choice(name="drivers", value="drivers"),
        app_commands.Choice(name="constructors", value="constructors"),
        app_commands.Choice(name="schedule", value="schedule"),
    ])
    async def f1(self, interaction: discord.Interaction, mode: app_commands.Choice[str] = None):
        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            if mode is None:
                await self._default(interaction, session)
            elif mode.value == "results":
                await self._results(interaction, session)
            elif mode.value == "drivers":
                await self._drivers(interaction, session)
            elif mode.value == "constructors":
                await self._constructors(interaction, session)
            elif mode.value == "schedule":
                await self._schedule(interaction, session)

    # ── /f1 default: live session → next race ──────────────────
    async def _default(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        # Check current season schedule for next race
        data = await jolpica_get(session, "/current")
        if not data:
            await interaction.followup.send("❌ Could not reach F1 API. Try again later!", ephemeral=True)
            return

        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            await interaction.followup.send("❌ No race data found.", ephemeral=True)
            return

        now = datetime.now(timezone.utc)

        # Find current or next race
        next_race = None
        last_race = None
        for race in races:
            try:
                race_dt_str = f"{race['date']}T{race.get('time', '00:00:00Z')}"
                race_dt = datetime.fromisoformat(race_dt_str.replace("Z", "+00:00"))
            except Exception:
                continue

            if race_dt > now:
                next_race = race
                break
            last_race = race

        # Check if a session is currently live (within race weekend window)
        # A race weekend spans Thu–Sun, so check if we're within ±4 days of a race
        live_session = None
        if last_race:
            try:
                last_dt_str = f"{last_race['date']}T{last_race.get('time', '00:00:00Z')}"
                last_dt = datetime.fromisoformat(last_dt_str.replace("Z", "+00:00"))
                diff_hours = abs((now - last_dt).total_seconds() / 3600)
                if diff_hours < 96:  # within 4 days = still race weekend
                    live_session = last_race
            except Exception:
                pass

        if live_session:
            # We're in a race weekend — show session info
            circuit = live_session.get("Circuit", {})
            embed = discord.Embed(
                title=f"🏎️ Race Weekend — {live_session.get('raceName', 'Unknown')}",
                description=f"Round {live_session.get('round', '?')} of the 2026 F1 Season",
                color=F1_RED
            )
            embed.add_field(
                name="🏟️ Circuit",
                value=f"{circuit.get('circuitName', '?')}, {circuit.get('Location', {}).get('country', '?')}",
                inline=False
            )
            try:
                race_ts = int(datetime.fromisoformat(
                    f"{live_session['date']}T{live_session.get('time', '00:00:00Z')}".replace("Z", "+00:00")
                ).timestamp())
                embed.add_field(name="🏁 Race", value=f"<t:{race_ts}:F> (<t:{race_ts}:R>)", inline=False)
            except Exception:
                embed.add_field(name="📅 Race Date", value=live_session.get("date", "?"), inline=False)

            embed.add_field(
                name="💡 Tip",
                value="Use `/f1 mode:results` for latest session results!",
                inline=False
            )
            embed.set_footer(text="Powered by Jolpica/Ergast")
            await interaction.followup.send(embed=embed)

        elif next_race:
            # Show next race countdown
            circuit = next_race.get("Circuit", {})
            try:
                race_ts = int(datetime.fromisoformat(
                    f"{next_race['date']}T{next_race.get('time', '00:00:00Z')}".replace("Z", "+00:00")
                ).timestamp())
                time_str = f"<t:{race_ts}:F>\n<t:{race_ts}:R>"
            except Exception:
                time_str = next_race.get("date", "?")

            embed = discord.Embed(
                title=f"🏎️ Next Race — {next_race.get('raceName', 'Unknown')}",
                description=f"Round {next_race.get('round', '?')} of the 2026 F1 Season",
                color=F1_RED
            )
            embed.add_field(
                name="🏟️ Circuit",
                value=f"{circuit.get('circuitName', '?')}, {circuit.get('Location', {}).get('country', '?')}",
                inline=False
            )
            embed.add_field(name="📅 Race", value=time_str, inline=False)
            embed.set_footer(text="Powered by Jolpica/Ergast")
            await interaction.followup.send(embed=embed)

        else:
            embed = discord.Embed(
                title="🏎️ F1 2026",
                description="Season appears to be over! Stay tuned for 2027.",
                color=F1_RED
            )
            await interaction.followup.send(embed=embed)

    # ── /f1 results ────────────────────────────────────────────
    async def _results(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        # Try qualifying results first (most recent session)
        qual_data = await jolpica_get(session, "/current/last/qualifying")
        race_data = await jolpica_get(session, "/current/last/results")

        qual_races = qual_data.get("MRData", {}).get("RaceTable", {}).get("Races", []) if qual_data else []
        race_races = race_data.get("MRData", {}).get("RaceTable", {}).get("Races", []) if race_data else []

        now = datetime.now(timezone.utc)

        # Determine which is more recent
        def get_race_dt(race_list):
            if not race_list:
                return datetime.min.replace(tzinfo=timezone.utc)
            r = race_list[0]
            try:
                return datetime.fromisoformat(f"{r['date']}T{r.get('time','00:00:00Z')}".replace("Z", "+00:00"))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)

        qual_dt = get_race_dt(qual_races)
        race_dt = get_race_dt(race_races)

        # Show whichever happened more recently, but only if it's in the past
        if qual_races and qual_dt > race_dt and qual_dt <= now:
            await self._show_qualifying(interaction, qual_races[0])
        elif race_races:
            await self._show_race_results(interaction, race_races[0])
        else:
            await interaction.followup.send("❌ No recent results found.", ephemeral=True)

    async def _show_qualifying(self, interaction: discord.Interaction, race: dict):
        name = race.get("raceName", "Unknown")
        circuit = race.get("Circuit", {}).get("circuitName", "?")
        date = race.get("date", "?")
        results = race.get("QualifyingResults", [])

        entries = []
        for r in results:
            pos = int(r.get("position", 0))
            medal = POSITION_MEDALS.get(pos, f"**P{pos}**")
            driver = r.get("Driver", {})
            code = driver.get("code", "???")
            name_str = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
            team = r.get("Constructor", {}).get("name", "?")
            q3 = r.get("Q3", "")
            q2 = r.get("Q2", "")
            q1 = r.get("Q1", "")
            best = q3 or q2 or q1 or "N/A"
            entries.append(f"{medal} `{code}` {name_str} — **{team}**\n┗ Best: `{best}`")

        if not entries:
            await interaction.followup.send("❌ No qualifying results found.", ephemeral=True)
            return

        pages = paginate(entries, f"🏎️ Qualifying — {name}\n{circuit} • {date}", F1_RED, per_page=8)
        view = PaginatedEmbed(pages, interaction.user.id)
        await interaction.followup.send(embed=pages[0], view=view)

    async def _show_race_results(self, interaction: discord.Interaction, race: dict):
        name = race.get("raceName", "Unknown")
        circuit = race.get("Circuit", {}).get("circuitName", "?")
        date = race.get("date", "?")
        results = race.get("Results", [])

        entries = []
        for r in results:
            pos = r.get("position", "?")
            try:
                pos_int = int(pos)
                medal = POSITION_MEDALS.get(pos_int, f"**P{pos_int}**")
            except Exception:
                medal = f"**{pos}**"
            driver = r.get("Driver", {})
            code = driver.get("code", "???")
            name_str = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
            team = r.get("Constructor", {}).get("name", "?")
            status = r.get("status", "?")
            time_val = r.get("Time", {}).get("time", "") or f"({status})"
            points = r.get("points", "0")
            entries.append(f"{medal} `{code}` {name_str} — **{team}**\n┗ {time_val} • +{points} pts")

        if not entries:
            await interaction.followup.send("❌ No race results found.", ephemeral=True)
            return

        pages = paginate(entries, f"🏁 Race Results — {name}\n{circuit} • {date}", F1_RED, per_page=8)
        view = PaginatedEmbed(pages, interaction.user.id)
        await interaction.followup.send(embed=pages[0], view=view)

    # ── /f1 drivers ────────────────────────────────────────────
    async def _drivers(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        data = await jolpica_get(session, "/current/driverStandings")
        if not data:
            await interaction.followup.send("❌ Could not fetch driver standings.", ephemeral=True)
            return

        standings_list = (
            data.get("MRData", {})
            .get("StandingsTable", {})
            .get("StandingsLists", [])
        )
        if not standings_list:
            await interaction.followup.send("❌ No standings data found.", ephemeral=True)
            return

        standings = standings_list[0].get("DriverStandings", [])
        entries = []
        for s in standings:
            pos = int(s.get("position", 0))
            medal = POSITION_MEDALS.get(pos, f"**P{pos}**")
            driver = s.get("Driver", {})
            code = driver.get("code", "???")
            full = f"{driver.get('givenName','')} {driver.get('familyName','')}".strip()
            team = s.get("Constructors", [{}])[0].get("name", "?")
            points = s.get("points", "0")
            wins = s.get("wins", "0")
            entries.append(f"{medal} `{code}` {full} — **{team}**\n┗ {points} pts • {wins} wins")

        pages = paginate(entries, "🏆 Driver Championship — 2026", F1_RED, per_page=8)
        view = PaginatedEmbed(pages, interaction.user.id)
        await interaction.followup.send(embed=pages[0], view=view)

    # ── /f1 constructors ───────────────────────────────────────
    async def _constructors(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        data = await jolpica_get(session, "/current/constructorStandings")
        if not data:
            await interaction.followup.send("❌ Could not fetch constructor standings.", ephemeral=True)
            return

        standings_list = (
            data.get("MRData", {})
            .get("StandingsTable", {})
            .get("StandingsLists", [])
        )
        if not standings_list:
            await interaction.followup.send("❌ No standings data found.", ephemeral=True)
            return

        standings = standings_list[0].get("ConstructorStandings", [])
        entries = []
        for s in standings:
            pos = int(s.get("position", 0))
            medal = POSITION_MEDALS.get(pos, f"**P{pos}**")
            team = s.get("Constructor", {}).get("name", "?")
            points = s.get("points", "0")
            wins = s.get("wins", "0")
            entries.append(f"{medal} **{team}**\n┗ {points} pts • {wins} wins")

        pages = paginate(entries, "🏗️ Constructor Championship — 2026", F1_RED, per_page=8)
        view = PaginatedEmbed(pages, interaction.user.id)
        await interaction.followup.send(embed=pages[0], view=view)

    # ── /f1 schedule ───────────────────────────────────────────
    async def _schedule(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        data = await jolpica_get(session, "/current")
        if not data:
            await interaction.followup.send("❌ Could not fetch schedule.", ephemeral=True)
            return

        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        now = datetime.now(timezone.utc)

        entries = []
        for race in races:
            try:
                race_ts = int(datetime.fromisoformat(
                    f"{race['date']}T{race.get('time','00:00:00Z')}".replace("Z", "+00:00")
                ).timestamp())
                time_str = f"<t:{race_ts}:d>"
            except Exception:
                time_str = race.get("date", "?")

            circuit = race.get("Circuit", {})
            country = circuit.get("Location", {}).get("country", "?")
            round_no = race.get("round", "?")
            name = race.get("raceName", "?")

            try:
                race_dt = datetime.fromisoformat(
                    f"{race['date']}T{race.get('time','00:00:00Z')}".replace("Z", "+00:00")
                )
                done = race_dt < now
            except Exception:
                done = False

            status = "✅" if done else "🔜"
            entries.append(f"{status} **R{round_no}** {time_str} — {name} 🇫🇷\n┗ {country}")

        if not entries:
            await interaction.followup.send("❌ No schedule found.", ephemeral=True)
            return

        pages = paginate(entries, "📅 F1 2026 — Full Season Schedule", F1_RED, per_page=8)
        view = PaginatedEmbed(pages, interaction.user.id)
        await interaction.followup.send(embed=pages[0], view=view)


async def setup(bot):
    await bot.add_cog(F1(bot))
