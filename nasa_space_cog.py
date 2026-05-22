import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import random
from datetime import date, timedelta

NASA_API_KEY = "QrwZX5RrVLpobVa6SbjnhbYWveyQ3dhCgddPPWSV"  # Replace with your key or use "DEMO_KEY"

ROVER_CAMERAS = {
    "curiosity":    ["FHAZ", "RHAZ", "MAST", "CHEMCAM", "MAHLI", "MARDI", "NAVCAM"],
    "perseverance": ["EDL_RUCAM", "FRONT_HAZCAM_LEFT_A", "NAVCAM_LEFT", "MCZ_RIGHT"],
    "opportunity":  ["FHAZ", "RHAZ", "NAVCAM", "PANCAM", "MINITES"],
    "spirit":       ["FHAZ", "RHAZ", "NAVCAM", "PANCAM", "MINITES"],
}


class NasaSpaceCog(commands.Cog, name="NASA Space"):
    """APOD and Mars Rover slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ── APOD ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="apod", description="Get NASA's Astronomy Picture of the Day")
    @app_commands.describe(date="Date in YYYY-MM-DD format (optional, defaults to today)")
    async def apod(self, interaction: discord.Interaction, date: str | None = None):
        await interaction.response.defer()

        params = {"api_key": NASA_API_KEY}
        if date:
            params["date"] = date

        try:
            async with self.session.get("https://api.nasa.gov/planetary/apod", params=params) as resp:
                if resp.status != 200:
                    await interaction.followup.send(
                        f"❌ NASA API returned status `{resp.status}`. Check your date format (YYYY-MM-DD).",
                        ephemeral=True,
                    )
                    return
                data = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Request failed: `{e}`", ephemeral=True)
            return

        title       = data.get("title", "No Title")
        explanation = data.get("explanation", "")
        apod_date   = data.get("date", "Unknown date")
        url         = data.get("url", "")
        hdurl       = data.get("hdurl", url)
        copyright_  = data.get("copyright", "NASA")
        media_type  = data.get("media_type", "image")

        if len(explanation) > 1000:
            explanation = explanation[:997] + "..."

        embed = discord.Embed(
            title=f"🔭 {title}",
            description=explanation,
            color=discord.Color.dark_blue(),
            url=hdurl or url,
        )
        embed.set_footer(text=f"📅 {apod_date}  •  © {copyright_}  •  NASA APOD")

        if media_type == "image":
            embed.set_image(url=url)
        else:
            embed.add_field(name="🎬 Media", value=f"[Watch video]({url})", inline=False)

        await interaction.followup.send(embed=embed)

    # ── APOD Random ───────────────────────────────────────────────────────────

    @app_commands.command(name="apod-random", description="Get a random NASA Astronomy Picture of the Day")
    async def apod_random(self, interaction: discord.Interaction):
        await interaction.response.defer()

        start       = date(1995, 6, 16)
        end         = date.today() - timedelta(days=1)
        random_date = start + timedelta(days=random.randint(0, (end - start).days))
        params      = {"api_key": NASA_API_KEY, "date": str(random_date)}

        try:
            async with self.session.get("https://api.nasa.gov/planetary/apod", params=params) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ Failed to fetch a random APOD.", ephemeral=True)
                    return
                data = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Request failed: `{e}`", ephemeral=True)
            return

        title       = data.get("title", "No Title")
        explanation = data.get("explanation", "")
        apod_date   = data.get("date", "Unknown")
        url         = data.get("url", "")
        hdurl       = data.get("hdurl", url)
        copyright_  = data.get("copyright", "NASA")

        if len(explanation) > 1000:
            explanation = explanation[:997] + "..."

        embed = discord.Embed(
            title=f"🎲 Random APOD — {title}",
            description=explanation,
            color=discord.Color.purple(),
            url=hdurl or url,
        )
        embed.set_footer(text=f"📅 {apod_date}  •  © {copyright_}  •  NASA APOD")
        if data.get("media_type") == "image":
            embed.set_image(url=url)

        await interaction.followup.send(embed=embed)

    # ── Mars Rover Photos ─────────────────────────────────────────────────────

    rover_choices = [
        app_commands.Choice(name="Curiosity",    value="curiosity"),
        app_commands.Choice(name="Perseverance", value="perseverance"),
        app_commands.Choice(name="Opportunity",  value="opportunity"),
        app_commands.Choice(name="Spirit",       value="spirit"),
    ]

    @app_commands.command(name="mars-rover", description="Get photos from a NASA Mars Rover")
    @app_commands.describe(
        rover="Which Mars rover to query",
        sol="Martian sol (day) number (optional, defaults to latest)",
        camera="Camera abbreviation e.g. NAVCAM, FHAZ (optional)",
    )
    @app_commands.choices(rover=rover_choices)
    async def mars_rover(
        self,
        interaction: discord.Interaction,
        rover: app_commands.Choice[str],
        sol: int | None = None,
        camera: str | None = None,
    ):
        await interaction.response.defer()

        rover_name = rover.value
        params: dict = {"api_key": NASA_API_KEY}

        if sol is not None:
            params["sol"] = sol
        else:
            try:
                async with self.session.get(
                    f"https://api.nasa.gov/mars-photos/api/v1/manifests/{rover_name}",
                    params={"api_key": NASA_API_KEY},
                ) as resp:
                    manifest   = await resp.json()
                    params["sol"] = manifest["photo_manifest"]["max_sol"]
            except Exception:
                params["sol"] = 1000

        if camera:
            params["camera"] = camera.upper()

        try:
            async with self.session.get(
                f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover_name}/photos",
                params=params,
            ) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"❌ NASA API error `{resp.status}`.", ephemeral=True)
                    return
                data = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Request failed: `{e}`", ephemeral=True)
            return

        photos = data.get("photos", [])
        if not photos:
            msg = f"No photos found for **{rover_name.title()}** on sol `{params['sol']}`"
            if camera:
                msg += f" with camera `{camera.upper()}`"
            msg += ".\nTry a different sol or omit the camera filter."
            await interaction.followup.send(msg, ephemeral=True)
            return

        photo      = random.choice(photos[:25])
        img_url    = photo["img_src"]
        earth_date = photo["earth_date"]
        photo_sol  = photo["sol"]
        cam_name   = photo["camera"]["full_name"]
        cam_abbr   = photo["camera"]["name"]
        status     = photo["rover"].get("status", "unknown").title()

        embed = discord.Embed(
            title=f"🔴 {rover_name.title()} — Sol {photo_sol}",
            color=discord.Color.from_rgb(188, 74, 40),
        )
        embed.set_image(url=img_url)
        embed.add_field(name="📷 Camera",         value=f"{cam_name} (`{cam_abbr}`)", inline=True)
        embed.add_field(name="🌍 Earth Date",      value=earth_date,                  inline=True)
        embed.add_field(name="🚀 Rover Status",    value=status,                      inline=True)
        embed.add_field(name="🖼️ Photos This Sol", value=f"{len(photos)} found (1 random shown)", inline=True)
        embed.add_field(
            name="📡 Available Cameras",
            value=", ".join(f"`{c}`" for c in ROVER_CAMERAS.get(rover_name, [])),
            inline=False,
        )
        embed.set_footer(text="NASA Mars Rover Photo API")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(NasaSpaceCog(bot))
