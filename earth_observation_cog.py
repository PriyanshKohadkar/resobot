import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from datetime import datetime, timedelta
import random

NASA_API_KEY = "QrwZX5RrVLpobVa6SbjnhbYWveyQ3dhCgddPPWSV"  # Replace with your key or use "DEMO_KEY"

# ── GIBS Layers ───────────────────────────────────────────────────────────────
# (layer_id, tilematrixset, format, description)
GIBS_LAYERS = {
    "land_surface_temp_day":   ("MODIS_Terra_Land_Surface_Temp_Day",                "1km",  "png", "Land Surface Temp (Day) — MODIS Terra"),
    "land_surface_temp_night": ("MODIS_Terra_Land_Surface_Temp_Night",              "1km",  "png", "Land Surface Temp (Night) — MODIS Terra"),
    "true_color":              ("MODIS_Terra_CorrectedReflectance_TrueColor",       "250m", "jpg", "True Color Imagery — MODIS Terra"),
    "snow_ice_cover":          ("MODIS_Terra_Snow_Cover",                           "500m", "png", "Snow & Ice Cover — MODIS Terra"),
    "aerosol_optical_depth":   ("MODIS_Terra_Aerosol",                              "2km",  "png", "Aerosol Optical Depth (Smoke/Dust) — MODIS Terra"),
    "sea_surface_temp":        ("GHRSST_L4_MUR_Sea_Surface_Temperature",            "1km",  "png", "Sea Surface Temperature — MUR L4"),
    "chlorophyll":             ("MODIS_Aqua_Chlorophyll_A",                         "1km",  "png", "Ocean Chlorophyll-A — MODIS Aqua"),
    "nighttime_lights":        ("VIIRS_SNPP_DayNightBand_ENCC",                     "500m", "png", "Nighttime City Lights — VIIRS SNPP"),
}

GIBS_LAYER_CHOICES = [
    app_commands.Choice(name=v[3][:100], value=k)
    for k, v in GIBS_LAYERS.items()
]

# ── EONET Categories ──────────────────────────────────────────────────────────
EONET_CATEGORIES = {
    "all":           (None,           "🌍 All Events"),
    "wildfires":     ("wildfires",    "🔥 Wildfires"),
    "severe_storms": ("severeStorms", "⛈️ Severe Storms"),
    "volcanoes":     ("volcanoes",    "🌋 Volcanoes"),
    "sea_lake_ice":  ("seaLakeIce",   "🧊 Sea & Lake Ice"),
    "floods":        ("floods",       "🌊 Floods"),
    "drought":       ("drought",      "☀️ Drought"),
    "dust_haze":     ("dustHaze",     "🌫️ Dust & Haze"),
    "snow":          ("snow",         "❄️ Snow"),
    "landslides":    ("landslides",   "⛰️ Landslides"),
}

EONET_CATEGORY_CHOICES = [
    app_commands.Choice(name=v[1], value=k)
    for k, v in EONET_CATEGORIES.items()
]

EONET_STATUS_CHOICES = [
    app_commands.Choice(name="Open (ongoing)", value="open"),
    app_commands.Choice(name="Closed (ended)", value="closed"),
    app_commands.Choice(name="All",            value="all"),
]


# ── EPIC date select menu ─────────────────────────────────────────────────────

class EpicDateSelect(discord.ui.Select):
    def __init__(self, dates: list[str], collection: str, session: aiohttp.ClientSession):
        self.collection = collection
        self.session    = session
        options = [
            discord.SelectOption(label=d, value=d)
            for d in dates[:25]          # Discord limit: 25 options
        ]
        super().__init__(
            placeholder="📅 Pick a date to view EPIC imagery…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        chosen_date = self.values[0]
        await interaction.response.defer()

        try:
            async with self.session.get(
                f"https://api.nasa.gov/EPIC/api/{self.collection}/date/{chosen_date}",
                params={"api_key": NASA_API_KEY},
            ) as resp:
                photos = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Request failed: `{e}`", ephemeral=True)
            return

        if not photos:
            await interaction.followup.send("❌ No photos found for that date.", ephemeral=True)
            return

        photo      = random.choice(photos[:10])
        image_name = photo["image"]
        caption    = photo.get("caption", "")
        centroid   = photo.get("centroid_coordinates", {})
        dscovr_dt  = photo.get("date", "")

        try:
            dt         = datetime.strptime(dscovr_dt[:10], "%Y-%m-%d")
            date_path  = dt.strftime("%Y/%m/%d")
        except Exception:
            date_path  = chosen_date.replace("-", "/")

        img_url = (
            f"https://epic.gsfc.nasa.gov/archive/{self.collection}"
            f"/{date_path}/jpg/{image_name}.jpg"
        )

        embed = discord.Embed(
            title=f"🌍 EPIC Earth Image — {self.collection.title()}",
            description=caption or "DSCOVR satellite full-disk Earth image.",
            color=discord.Color.blue(),
        )
        embed.set_image(url=img_url)
        embed.add_field(name="📅 Date",       value=chosen_date,                          inline=True)
        embed.add_field(name="🗂️ Collection", value=self.collection.title(),              inline=True)
        if centroid:
            embed.add_field(
                name="🌐 Centroid",
                value=f"Lat `{centroid.get('lat', 0):.2f}` / Lon `{centroid.get('lon', 0):.2f}`",
                inline=True,
            )
        embed.add_field(name="📸 Images This Day", value=f"{len(photos)} total (1 random shown)", inline=True)
        embed.set_footer(text="NASA EPIC — Earth Polychromatic Imaging Camera  •  DSCOVR Satellite")

        # Disable the select after use
        self.disabled = True
        await interaction.message.edit(view=self.view)
        await interaction.followup.send(embed=embed)


class EpicDateView(discord.ui.View):
    def __init__(self, dates: list[str], collection: str, session: aiohttp.ClientSession):
        super().__init__(timeout=120)
        self.add_item(EpicDateSelect(dates, collection, session))


# ── Cog ───────────────────────────────────────────────────────────────────────

class EarthObservationCog(commands.Cog, name="Earth Observation"):
    """EPIC, EONET, and GIBS slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ── EPIC ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="epic", description="Browse NASA EPIC full-disk Earth imagery by date")
    @app_commands.describe(collection="Image type: natural (true color) or enhanced")
    @app_commands.choices(collection=[
        app_commands.Choice(name="Natural (True Color)", value="natural"),
        app_commands.Choice(name="Enhanced Color",       value="enhanced"),
    ])
    async def epic(
        self,
        interaction: discord.Interaction,
        collection: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer()

        col = collection.value if collection else "natural"

        try:
            async with self.session.get(
                f"https://api.nasa.gov/EPIC/api/{col}/available",
                params={"api_key": NASA_API_KEY},
            ) as resp:
                all_dates = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to fetch available dates: `{e}`", ephemeral=True)
            return

        if not all_dates:
            await interaction.followup.send("❌ No EPIC dates available right now.", ephemeral=True)
            return

        # Show the 25 most recent dates in the dropdown
        recent_dates = list(reversed(all_dates))[:25]

        embed = discord.Embed(
            title="🌍 NASA EPIC — Earth Imagery",
            description=(
                f"**Collection:** {col.title()}\n"
                f"**Available dates:** {len(all_dates)}\n\n"
                "Select a date below to load the full-disk Earth image from that day."
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="NASA EPIC  •  DSCOVR Satellite  •  Select menu expires in 2 minutes")

        view = EpicDateView(recent_dates, col, self.session)
        await interaction.followup.send(embed=embed, view=view)

    # ── EONET ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="eonet", description="List recent NASA EONET natural events (wildfires, storms, etc.)")
    @app_commands.describe(
        category="Filter by event category (default: all)",
        status="Filter by event status (default: open/ongoing)",
        limit="Number of events to show, 1–15 (default 8)",
    )
    @app_commands.choices(category=EONET_CATEGORY_CHOICES, status=EONET_STATUS_CHOICES)
    async def eonet(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] = None,
        status:   app_commands.Choice[str] = None,
        limit:    int = 8,
    ):
        await interaction.response.defer()

        limit    = max(1, min(limit, 15))
        cat_key  = category.value if category else "all"
        cat_id, cat_label = EONET_CATEGORIES.get(cat_key, (None, "🌍 All Events"))
        status_val = status.value if status else "open"

        params: dict = {"limit": limit, "days": 30}
        if status_val in ("open", "closed"):
            params["status"] = status_val

        url = (
            f"https://eonet.gsfc.nasa.gov/api/v3/categories/{cat_id}"
            if cat_id else
            "https://eonet.gsfc.nasa.gov/api/v3/events"
        )

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"❌ EONET API error `{resp.status}`.", ephemeral=True)
                    return
                data = await resp.json()
        except Exception as e:
            await interaction.followup.send(f"❌ Request failed: `{e}`", ephemeral=True)
            return

        events = data.get("events", [])
        if not events:
            await interaction.followup.send(
                f"No **{cat_label}** events found (status: `{status_val}`, last 30 days).",
                ephemeral=True,
            )
            return

        color_map = {
            "wildfires":    discord.Color.from_rgb(220, 60, 20),
            "severeStorms": discord.Color.from_rgb(80, 100, 200),
            "volcanoes":    discord.Color.from_rgb(150, 40, 10),
            "seaLakeIce":   discord.Color.teal(),
            "floods":       discord.Color.blue(),
            "snow":         discord.Color.from_rgb(200, 220, 255),
        }
        embed = discord.Embed(
            title=f"{cat_label} — EONET Natural Events",
            description=f"**{len(events)}** event(s)  •  Status: `{status_val}`  •  Last 30 days",
            color=color_map.get(cat_id, discord.Color.green()),
        )

        for event in events:
            title      = event.get("title", "Unnamed Event")
            categories = ", ".join(c["title"] for c in event.get("categories", []))
            geometries = event.get("geometry", [])

            if geometries:
                geo      = geometries[-1]
                geo_date = geo.get("date", "")[:10]
                coords   = geo.get("coordinates", [])
                loc_str  = (
                    f"`{coords[1]:.2f}°N, {coords[0]:.2f}°E`"
                    if isinstance(coords, list) and len(coords) >= 2
                    else "N/A"
                )
            else:
                geo_date = "N/A"
                loc_str  = "N/A"

            closed       = event.get("closed")
            status_icon  = "🔴 Open" if not closed else f"✅ Closed {closed[:10]}"
            sources      = event.get("sources", [])
            source_url   = sources[0]["url"] if sources else None
            title_fmt    = f"[{title}]({source_url})" if source_url else title

            embed.add_field(
                name=title_fmt,
                value=(
                    f"📂 {categories}\n"
                    f"📅 {geo_date}  •  🗺️ {loc_str}\n"
                    f"🔘 {status_icon}"
                ),
                inline=False,
            )

        embed.set_footer(text="NASA EONET — Earth Observatory Natural Event Tracker")
        await interaction.followup.send(embed=embed)

    # ── GIBS ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="gibs", description="Get a NASA GIBS satellite imagery tile")
    @app_commands.describe(
        layer="Which satellite imagery layer to show",
        date="Date in YYYY-MM-DD format (optional, defaults to 3 days ago)",
        tile_row="Tile row 0–3, N→S (default 2 = mid-latitude)",
        tile_col="Tile col 0–7, W→E (default 4 = roughly central)",
    )
    @app_commands.choices(layer=GIBS_LAYER_CHOICES)
    async def gibs(
        self,
        interaction: discord.Interaction,
        layer:    app_commands.Choice[str],
        date:     str | None = None,
        tile_row: int = 2,
        tile_col: int = 4,
    ):
        await interaction.response.defer()

        tile_row = max(0, min(tile_row, 3))
        tile_col = max(0, min(tile_col, 7))

        layer_id, tilematrixset, fmt, description = GIBS_LAYERS[layer.value]
        tile_date = date or (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")

        zoom     = 3
        tile_url = (
            f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{layer_id}/default"
            f"/{tile_date}/{tilematrixset}/{zoom}/{tile_row}/{tile_col}.{fmt}"
        )

        try:
            async with self.session.head(tile_url) as resp:
                tile_exists = resp.status == 200
        except Exception:
            tile_exists = False

        embed = discord.Embed(
            title=f"🛰️ GIBS — {description}",
            color=discord.Color.from_rgb(30, 80, 160),
        )

        if tile_exists:
            embed.set_image(url=tile_url)
            embed.description = "Satellite imagery tile from **NASA GIBS**. Updates daily with ~1–3 day delay."
        else:
            embed.description = (
                f"⚠️ Tile unavailable for **{tile_date}** at row `{tile_row}`, col `{tile_col}`.\n"
                f"This layer may have a longer delay or limited coverage here.\n"
                f"Try a different date or tile position."
            )
            embed.add_field(name="🔗 Direct URL", value=f"[Try in browser]({tile_url})", inline=False)

        embed.add_field(name="📅 Date",          value=tile_date,              inline=True)
        embed.add_field(name="📐 Resolution",     value=tilematrixset,          inline=True)
        embed.add_field(name="🔢 Tile",           value=f"Z`{zoom}` R`{tile_row}` C`{tile_col}`", inline=True)
        embed.add_field(
            name="💡 Tile Grid (zoom 3)",
            value="Rows 0–3: Arctic→Antarctic  •  Cols 0–7: West→East Pacific",
            inline=False,
        )
        embed.set_footer(text="NASA GIBS — Global Imagery Browse Services  •  Earthdata")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EarthObservationCog(bot))
