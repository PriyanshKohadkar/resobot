import asyncio
import json
import math
import os

import discord
import folium
import requests
from folium.features import DivIcon
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ------------------ GLOBALS ------------------

RADIUS_KM = 32
HEADING_TOLERANCE = 12
INBOUND_TOLERANCE = 20
ALTITUDE_LIMIT_FT = 5000
MIN_FETCH_INTERVAL = 30
REFRESH_RUNNING = 12
REFRESH_IDLE = 25

selected_airport = None
selected_airport_icao = None
aircraft_trails = {}
cached_aircraft = []
cached_nearby_aircraft = []
last_fetch_ts = 0.0
last_fetch_issue = None
opensky_token = None
opensky_token_expiry_ts = 0.0

AIRLINE_STYLE = {
    "IGO": ("IndiGo", "blue"),
    "AIC": ("Air India", "red"),
    "AXB": ("Air India Express", "orange"),
    "VTI": ("Vistara", "purple"),
    "UAE": ("Emirates", "green"),
}

# ------------------ LOAD AIRPORTS ------------------

AIRPORTS_PATH = os.path.join(os.path.dirname(__file__), "airports.json")
RADAR_STATE_PATH = os.path.join(os.path.dirname(__file__), "radar_state.json")

with open(AIRPORTS_PATH, "r", encoding="utf-8") as f:
    airport_data = json.load(f)


def save_radar_state():
    state = {"selected_airport_icao": selected_airport_icao}
    try:
        with open(RADAR_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def load_radar_state():
    global selected_airport, selected_airport_icao
    if not os.path.exists(RADAR_STATE_PATH):
        return

    try:
        with open(RADAR_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return

    icao = state.get("selected_airport_icao")
    if not icao:
        return

    airport = airport_data.get(icao)
    if not airport:
        return

    selected_airport_icao = icao
    selected_airport = airport


load_radar_state()


# ------------------ UTILITY FUNCTIONS ------------------


def heading_difference(h1, h2):
    diff = abs(h1 - h2) % 360
    return min(diff, 360 - diff)


def is_runway_aligned(heading):
    if not selected_airport:
        return False
    return any(
        heading_difference(heading, runway_heading) <= HEADING_TOLERANCE
        for runway_heading in selected_airport["runways"]
    )


def bearing_to_airport(lat, lon):
    if not selected_airport:
        return 0

    airport_lat = selected_airport["lat"]
    airport_lon = selected_airport["lon"]
    dlon = math.radians(airport_lon - lon)
    y = math.sin(dlon) * math.cos(math.radians(airport_lat))
    x = (
        math.cos(math.radians(lat)) * math.sin(math.radians(airport_lat))
        - math.sin(math.radians(lat))
        * math.cos(math.radians(airport_lat))
        * math.cos(dlon)
    )
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def is_heading_towards_airport(lat, lon, heading):
    target_bearing = bearing_to_airport(lat, lon)
    return heading_difference(heading, target_bearing) <= INBOUND_TOLERANCE


def distance_km(lat1, lon1, lat2, lon2):
    radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def get_airline(callsign):
    prefix = (callsign or "").strip()[:3]
    return AIRLINE_STYLE.get(prefix, ("Unknown", "cyan"))


def plane_icon_html(heading, color, size=20):
    rotation = float(heading or 0) % 360
    return f"""
    <div style="
        width:{size}px;
        height:{size}px;
        transform: rotate({rotation}deg);
        transform-origin: 50% 50%;
        display:inline-block;">
        <svg viewBox="0 0 24 24" width="{size}" height="{size}">
            <path d="M12 1 L15 10 L22 12 L15 14 L12 23 L9 14 L2 12 L9 10 Z"
                  fill="{color}" stroke="black" stroke-width="0.7"/>
        </svg>
    </div>
    """
    

def build_color_legend():
    legend_entries = [f"{name}={color}" for name, color in AIRLINE_STYLE.values()]
    legend_entries.append("Unknown=cyan")
    return "Airline colors: " + ", ".join(legend_entries)


def search_airport_by_name(name):
    name = name.lower()
    for icao, data in airport_data.items():
        if name in data["name"].lower():
            return icao, data
    return None, None


# ------------------ FETCH AIRCRAFT ------------------


def get_opensky_token(now):
    global opensky_token, opensky_token_expiry_ts

    client_id = os.getenv("OPENSKY_CLIENT_ID")
    client_secret = os.getenv("OPENSKY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None, None

    if opensky_token and now < opensky_token_expiry_ts:
        return opensky_token, None

    token_url = (
        "https://auth.opensky-network.org/auth/realms/opensky-network/"
        "protocol/openid-connect/token"
    )
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        token_resp = requests.post(token_url, data=payload, timeout=10)
        if token_resp.status_code != 200:
            opensky_token = None
            opensky_token_expiry_ts = 0.0
            return None, f"OpenSky token HTTP {token_resp.status_code}"

        token_data = token_resp.json()
        token = token_data.get("access_token")
        expires_in = int(token_data.get("expires_in", 300))
        if not token:
            opensky_token = None
            opensky_token_expiry_ts = 0.0
            return None, "OpenSky token missing access_token"

        opensky_token = token
        opensky_token_expiry_ts = now + max(60, expires_in - 30)
        return opensky_token, None
    except (requests.RequestException, ValueError):
        opensky_token = None
        opensky_token_expiry_ts = 0.0
        return None, "OpenSky token request failed"


def fetch_aircraft():
    global cached_aircraft, cached_nearby_aircraft, last_fetch_ts, last_fetch_issue

    if not selected_airport:
        return [], []

    now = asyncio.get_running_loop().time()
    if (
        (cached_aircraft or cached_nearby_aircraft)
        and (now - last_fetch_ts) < MIN_FETCH_INTERVAL
    ):
        return cached_aircraft, cached_nearby_aircraft

    url = "https://opensky-network.org/api/states/all"
    username = os.getenv("OPENSKY_USERNAME")
    password = os.getenv("OPENSKY_PASSWORD")
    basic_auth = (username, password) if username and password else None

    try:
        response = None
        issue = None

        token, token_issue = get_opensky_token(now)
        if token:
            response = requests.get(
                url,
                timeout=10,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401:
                global opensky_token, opensky_token_expiry_ts
                opensky_token = None
                opensky_token_expiry_ts = 0.0
                token, token_issue = get_opensky_token(now)
                if token:
                    response = requests.get(
                        url,
                        timeout=10,
                        headers={"Authorization": f"Bearer {token}"},
                    )

        if response is None:
            issue = token_issue
            if basic_auth:
                response = requests.get(url, timeout=10, auth=basic_auth)
                if response.status_code == 401:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        issue = "OpenSky 401 for username/password. Using anonymous feed."
                    else:
                        last_fetch_ts = now
                        last_fetch_issue = "OpenSky HTTP 401 (invalid credentials)."
                        return [], []
            else:
                response = requests.get(url, timeout=10)

        if response.status_code != 200:
            last_fetch_ts = now
            last_fetch_issue = issue or f"OpenSky HTTP {response.status_code}"
            return [], []

        if issue and response.status_code == 200:
            last_fetch_issue = issue
        data = response.json()
    except (requests.RequestException, ValueError):
        last_fetch_ts = now
        last_fetch_issue = "OpenSky fetch failed"
        return [], []

    states = data.get("states") or []
    inbound_aircraft = []
    nearby_aircraft = []

    for state in states:
        lat = state[6]
        lon = state[5]
        heading = state[10] if state[10] is not None else 0
        altitude = state[13] if state[13] is not None else (state[7] or 0)
        callsign = state[1]
        icao = state[0]

        if lat is None or lon is None:
            continue

        dist = distance_km(
            selected_airport["lat"],
            selected_airport["lon"],
            lat,
            lon,
        )

        if dist > RADIUS_KM:
            continue

        airline, color = get_airline(callsign)
        ac_entry = {
            "icao": icao,
            "lat": lat,
            "lon": lon,
            "heading": heading,
            "altitude": altitude,
            "callsign": callsign.strip() if callsign else "Unknown",
            "distance_km": dist,
            "airline": airline,
            "color": color,
        }
        nearby_aircraft.append(ac_entry)

        if altitude > ALTITUDE_LIMIT_FT:
            continue
        if not is_runway_aligned(heading):
            continue
        if not is_heading_towards_airport(lat, lon, heading):
            continue

        inbound_aircraft.append({**ac_entry})

    cached_aircraft = inbound_aircraft
    cached_nearby_aircraft = nearby_aircraft
    last_fetch_ts = now
    if not last_fetch_issue or not (
        last_fetch_issue.startswith("OpenSky 401")
        or last_fetch_issue.startswith("OpenSky token")
    ):
        last_fetch_issue = None
    return inbound_aircraft, nearby_aircraft


# ------------------ MAP GENERATION ------------------


def generate_map():
    global aircraft_trails

    if not selected_airport:
        return False, [], [], None

    radar_map = folium.Map(
        location=[selected_airport["lat"], selected_airport["lon"]],
        zoom_start=12,
        tiles=None,
    )

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
    ).add_to(radar_map)

    folium.Circle(
        radius=RADIUS_KM * 1000,
        location=[selected_airport["lat"], selected_airport["lon"]],
        color="yellow",
        fill=False,
        weight=2,
    ).add_to(radar_map)

    inbound_aircraft, nearby_aircraft = fetch_aircraft()
    issue = last_fetch_issue
    if not inbound_aircraft and not nearby_aircraft and (cached_aircraft or cached_nearby_aircraft):
        inbound_aircraft = cached_aircraft
        nearby_aircraft = cached_nearby_aircraft
        issue = "Using cached aircraft (OpenSky rate limit/fetch issue)."

    inbound_details = []

    for ac in inbound_aircraft:
        icao = ac["icao"]

        if icao not in aircraft_trails:
            aircraft_trails[icao] = []

        aircraft_trails[icao].append((ac["lat"], ac["lon"]))
        aircraft_trails[icao] = aircraft_trails[icao][-25:]

        folium.PolyLine(
            aircraft_trails[icao],
            color=ac["color"],
            weight=3,
        ).add_to(radar_map)

        if ac["altitude"] < 1500:
            phase = "Landing"
        elif ac["altitude"] < 4000:
            phase = "Approach"
        else:
            phase = "Departure"

        folium.Marker(
            location=[ac["lat"], ac["lon"]],
            icon=DivIcon(html=plane_icon_html(ac["heading"], ac["color"], size=20)),
            popup=f"{ac['callsign']} ({ac['airline']}) | {phase}",
        ).add_to(radar_map)

        inbound_details.append(
            f"- {ac['callsign']} ({ac['airline']}) | {ac['distance_km']:.1f} km | {phase}"
        )

    inbound_ids = {ac["icao"] for ac in inbound_aircraft}
    nearby_only = [ac for ac in nearby_aircraft if ac["icao"] not in inbound_ids]
    nearby_only.sort(key=lambda x: x["distance_km"])

    for ac in nearby_only[:20]:
        folium.Marker(
            location=[ac["lat"], ac["lon"]],
            icon=DivIcon(html=plane_icon_html(ac["heading"], ac["color"], size=16)),
            popup=f"{ac['callsign']} ({ac['airline']}) | Nearby",
        ).add_to(radar_map)

    compact_lines = [
        f"Inbound: {len(inbound_aircraft)} | Nearby: {len(nearby_aircraft)}"
    ]

    detail_lines = []
    if inbound_details:
        detail_lines.append("Inbound runway-aligned:")
        detail_lines.extend(inbound_details[:6])

    if nearby_only:
        if detail_lines:
            detail_lines.append("")
        detail_lines.append("Nearby traffic:")
        for ac in nearby_only[:8]:
            detail_lines.append(
                f"- {ac['callsign']} ({ac['airline']}) | {ac['distance_km']:.1f} km"
            )

    radar_map.save("radar_map.html")
    return bool(inbound_aircraft or nearby_aircraft), compact_lines, detail_lines, issue


# ------------------ SCREENSHOT ------------------


async def screenshot_map():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    driver.get("file://" + os.path.abspath("radar_map.html"))
    await asyncio.sleep(2)
    driver.save_screenshot("radar.png")
    driver.quit()


def build_radar_text(show_details, compact_lines, detail_lines, issue):
    if not selected_airport:
        return "Select airport first using /airport"

    lines = [
        f"Live Radar - {selected_airport['name']}",
        build_color_legend(),
        "",
        *compact_lines,
    ]

    if show_details and detail_lines:
        lines.append("")
        lines.extend(detail_lines)

    if issue:
        lines.append("")
        lines.append(f"Source note: {issue}")

    return "\n".join(lines)


# ------------------ SETUP FUNCTION ------------------


def setup_radar(bot):
    tree = bot.tree

    @tree.command(name="airport", description="Select airport by name")
    async def airport(interaction: discord.Interaction, name: str):
        global selected_airport, selected_airport_icao, aircraft_trails

        icao, data = search_airport_by_name(name)

        if not data:
            await interaction.response.send_message(
                "Airport not found.",
                ephemeral=True,
            )
            return

        selected_airport = data
        selected_airport_icao = icao
        aircraft_trails.clear()
        save_radar_state()

        await interaction.response.send_message(
            f"Airport set to {data['name']} ({icao})",
            ephemeral=True,
        )

    class RadarControl(discord.ui.View):
        def __init__(self, owner_id):
            super().__init__(timeout=900)
            self.owner_id = owner_id
            self.running = False
            self.show_details = False
            self.panel_message = None
            self.update_task = None

        def _owner_only(self, interaction):
            return interaction.user.id == self.owner_id

        async def _render_radar(self, interaction):
            detected, compact_lines, detail_lines, issue = generate_map()
            await screenshot_map()

            text = build_radar_text(self.show_details, compact_lines, detail_lines, issue)
            if not detected:
                text = text + "\n\nNo traffic detected in current radius."

            file = discord.File("radar.png")
            await interaction.edit_original_response(
                content=text,
                attachments=[file],
                view=self,
            )
            self.panel_message = await interaction.original_response()

        async def _render_to_panel(self):
            if self.panel_message is None:
                return

            detected, compact_lines, detail_lines, issue = generate_map()
            await screenshot_map()

            text = build_radar_text(self.show_details, compact_lines, detail_lines, issue)
            if not detected:
                text = text + "\n\nNo traffic detected in current radius."

            file = discord.File("radar.png")
            await self.panel_message.edit(
                content=text,
                attachments=[file],
                view=self,
            )

        async def _run_updates(self):
            while self.running and not self.is_finished():
                try:
                    await self._render_to_panel()
                except Exception:
                    self.running = False
                    break
                await asyncio.sleep(REFRESH_RUNNING)

        def _start_updates(self):
            if self.update_task and not self.update_task.done():
                return
            self.update_task = asyncio.create_task(self._run_updates())

        def _stop_updates(self):
            if self.update_task and not self.update_task.done():
                self.update_task.cancel()
            self.update_task = None

        async def on_timeout(self):
            self.running = False
            self._stop_updates()

        @discord.ui.button(label="Start", style=discord.ButtonStyle.success)
        async def start_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            if not self._owner_only(interaction):
                await interaction.response.send_message(
                    "Only the command user can control this radar panel.",
                    ephemeral=True,
                )
                return

            if not selected_airport:
                await interaction.response.send_message(
                    "Select airport first using /airport",
                    ephemeral=True,
                )
                return

            self.running = True
            await interaction.response.defer()
            await self._render_radar(interaction)
            self._start_updates()

        @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
        async def stop_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            if not self._owner_only(interaction):
                await interaction.response.send_message(
                    "Only the command user can control this radar panel.",
                    ephemeral=True,
                )
                return

            self.running = False
            self._stop_updates()
            await interaction.response.defer()
            message = build_radar_text(
                self.show_details,
                ["Radar stopped.", f"Auto refresh idle: {REFRESH_IDLE}s"],
                [],
                None,
            )
            await interaction.edit_original_response(content=message, attachments=[], view=self)
            self.panel_message = await interaction.original_response()

        @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary)
        async def restart_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            if not self._owner_only(interaction):
                await interaction.response.send_message(
                    "Only the command user can control this radar panel.",
                    ephemeral=True,
                )
                return

            if not selected_airport:
                await interaction.response.send_message(
                    "Select airport first using /airport",
                    ephemeral=True,
                )
                return

            self.running = True
            self._stop_updates()
            await interaction.response.defer()
            await self._render_radar(interaction)
            self._start_updates()

        @discord.ui.button(label="Toggle Info", style=discord.ButtonStyle.secondary)
        async def toggle_info_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
            if not self._owner_only(interaction):
                await interaction.response.send_message(
                    "Only the command user can control this radar panel.",
                    ephemeral=True,
                )
                return

            self.show_details = not self.show_details
            if self.running:
                await interaction.response.defer()
                await self._render_radar(interaction)
                return

            detail_state = "ON" if self.show_details else "OFF"
            message = build_radar_text(
                self.show_details,
                [f"Detailed info: {detail_state}", "Press Start to fetch radar."],
                [],
                None,
            )
            await interaction.response.edit_message(content=message, attachments=[], view=self)

    @tree.command(name="radar", description="Control radar")
    async def radar(interaction: discord.Interaction):
        view = RadarControl(interaction.user.id)
        airport_name = selected_airport["name"] if selected_airport else "No airport selected"
        content = (
            f"Radar Control - {airport_name}\n"
            f"{build_color_legend()}\n\n"
            "Default mode is compact. Use `Toggle Info` for detailed lists.\n"
            "Press Start to render radar."
        )
        await interaction.response.send_message(
            content,
            view=view,
            ephemeral=True,
        )
        view.panel_message = await interaction.original_response()
