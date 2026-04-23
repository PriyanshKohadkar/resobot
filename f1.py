# cogs/f1.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime, timezone

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"
F1_RED = 0xE8002D
POSITION_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# ── Helpers ────────────────────────────────────────────────────

async def jolpica_get(session: aiohttp.ClientSession, path: str) -> dict | None:
    url = f"{JOLPICA_BASE}{path}.json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200: return None
            return await resp.json()
    except Exception: return None

def extract_fastest_lap(results: list) -> str | None:
    for r in results:
        fl = r.get("FastestLap", {})
        if str(fl.get("rank", "")) == "1":
            driver = r.get("Driver", {})
            code = driver.get("code", "???")
            team = r.get("Constructor", {}).get("name", "?")
            lap_time = fl.get("Time", {}).get("time", "N/A")
            return f"`{code}` — **{team}**\n⏱️ `{lap_time}`"
    return None

# ── Pagination View ────────────────────────────────────────────

class PaginatedEmbed(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=120)
        self.pages, self.current, self.author_id = pages, 0, author_id
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1
        for page in self.pages:
            page.set_footer(text=f"Page {self.current + 1}/{len(self.pages)} • Powered by Jolpica/Ergast")

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id: return
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id: return
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

def paginate(entries: list[str], title: str, color: int, per_page: int = 10) -> list[discord.Embed]:
    return [discord.Embed(title=title, description="\n".join(entries[i:i + per_page]), color=color) for i in range(0, len(entries), per_page)]

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
            if mode is None: await self._default(interaction, session)
            elif mode.value == "results": await self._results(interaction, session)
            elif mode.value == "drivers": await self._drivers(interaction, session)
            elif mode.value == "constructors": await self._constructors(interaction, session)
            elif mode.value == "schedule": await self._schedule(interaction, session)

    # ── /f1 default (Next Race View) ──────────────────
    async def _default(self, interaction: discord.Interaction, session: aiohttp.ClientSession):
        data = await jolpica_get(session, "/current")
        if not data:
            await interaction.followup.send("❌ API Error.")
            return

        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        now = datetime.now(timezone.utc)
        next_race = None
        for r in races:
            try:
                dt = datetime.fromisoformat(f"{r['date']}T{r.get('time', '00:00:00Z')}".replace("Z", "+00:00"))
                if dt > now:
                    next_race = r
                    break
            except: continue
        
        if next_race:
            circuit = next_race.get("Circuit", {})
            loc = circuit.get("Location", {})
            ts = int(datetime.fromisoformat(f"{next_race['date']}T{next_race.get('time', '00:00:00Z')}".replace("Z", "+00:00")).timestamp())
            
            embed = discord.Embed(
                title=f"🏎️ Next Race — {next_race['raceName']}",
                description=f"Round {next_race['round']} of the 2026 F1 Season",
                color=F1_RED
            )
            embed.add_field(
                name="🏟️ Circuit", 
                value=f"{circuit.get('circuitName')}, {loc.get('country')}", 
                inline=False
            )
            embed.add_field(
                name="📅 Race", 
                value=f"<t:{ts}:F>\n<t:{ts}:R>", 
                inline=False
            )
            embed.set_footer(text="Powered by Jolpica/Ergast")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Season appears to be over!")

    async def _results(self, interaction, session):
        q_data, r_data = await asyncio.gather(
            jolpica_get(session, "/current/last/qualifying"),
            jolpica_get(session, "/current/last/results")
        )
        q_race = q_data.get("MRData", {}).get("RaceTable", {}).get("Races", [None])[0]
        r_race = r_data.get("MRData", {}).get("RaceTable", {}).get("Races", [None])[0]

        if r_race and (not q_race or int(r_race['round']) >= int(q_race['round'])):
            await self._show_race_results(interaction, r_race)
        elif q_race:
            await self._show_qualifying(interaction, q_race)

    async def _drivers(self, interaction, session):
        data = await jolpica_get(session, "/current/driverStandings")
        standings = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [{}])[0].get("DriverStandings", [])
        entries = []
        for s in standings:
            pos = int(s['position'])
            medal = POSITION_MEDALS.get(pos, f"`{pos:02d}`")
            name = f"{s['Driver'].get('givenName')} {s['Driver'].get('familyName')}"
            entries.append(f"{medal} **{s['Driver']['code']}** — {name}\n└ `{s['points']} pts` • *{s['Constructors'][0]['name']}*\n")
        pages = paginate(entries, "🏆 Driver World Championship", F1_RED, per_page=7)
        await interaction.followup.send(embed=pages[0], view=PaginatedEmbed(pages, interaction.user.id))

    async def _schedule(self, interaction, session):
        data = await jolpica_get(session, "/current")
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        now, entries = datetime.now(timezone.utc), []
        for r in races:
            try:
                dt = datetime.fromisoformat(f"{r['date']}T{r.get('time','00:00:00Z')}".replace("Z", "+00:00"))
                status = "✅" if dt < now else "🔜"
                entries.append(f"{status} **R{r['round']}** <t:{int(dt.timestamp())}:d> — {r['raceName']}\n┗ {r['Circuit']['Location'].get('country')}\n")
            except: continue
        pages = paginate(entries, "📅 F1 2026 Full Season Schedule", F1_RED, per_page=8)
        await interaction.followup.send(embed=pages[0], view=PaginatedEmbed(pages, interaction.user.id))

    async def _show_qualifying(self, interaction, race):
        entries = [f"{POSITION_MEDALS.get(int(r['position']), f'`{int(r['position']):02d}`')} **{r['Driver'].get('code')}** | {r['Constructor'].get('name')}\n⏱️ `{r.get('Q3') or r.get('Q2') or r.get('Q1') or 'N/A'}`\n" for r in race.get("QualifyingResults", [])]
        pages = paginate(entries, f"⏱️ Qualifying: {race.get('raceName')}", F1_RED, per_page=6)
        for p in pages: p.description = f"**{race['Circuit'].get('circuitName')}**\n" + "—"*15 + "\n\n" + p.description
        await interaction.followup.send(embed=pages[0], view=PaginatedEmbed(pages, interaction.user.id))

    async def _show_race_results(self, interaction, race):
        results = race.get("Results", [])
        entries = [f"{POSITION_MEDALS.get(int(r['position']), f'`{int(r['position']):02d}`')} **{r['Driver'].get('code')}** • {r['Constructor'].get('name')}\n└ `+{r.get('points')} pts` • {r.get('status')}\n" for r in results]
        pages = paginate(entries, f"🏁 Race Results: {race.get('raceName')}", F1_RED, per_page=6)
        for p in pages: p.description = f"**{race['Circuit'].get('circuitName')}**\n" + "—"*15 + "\n\n" + p.description
        fl = extract_fastest_lap(results)
        if fl: pages[0].insert_field_at(0, name="⚡ Fastest Lap", value=fl, inline=False)
        await interaction.followup.send(embed=pages[0], view=PaginatedEmbed(pages, interaction.user.id))

    async def _constructors(self, interaction, session):
        data = await jolpica_get(session, "/current/constructorStandings")
        standings = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [{}])[0].get("ConstructorStandings", [])
        entries = [f"{POSITION_MEDALS.get(int(s['position']), f'`{int(s['position']):02d}`')} **{s['Constructor']['name']}**\n🏆 `{s['points']} pts` — {s['wins']} wins\n" for s in standings]
        pages = paginate(entries, "🏗️ Constructor Championship", F1_RED, per_page=8)
        await interaction.followup.send(embed=pages[0], view=PaginatedEmbed(pages, interaction.user.id))

async def setup(bot): await bot.add_cog(F1(bot))
