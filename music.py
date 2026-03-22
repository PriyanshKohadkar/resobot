import discord
import wavelink
from discord.ext import commands
from discord import app_commands
import asyncio

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
DJ_ROLE_NAME = 'DJ'  # Change to your DJ role name

LAVALINK_NODES = [
    wavelink.Node(
        uri='https://lavalinkv4.serenetia.com:443',
        password='https://dsc.gg/ajidevserver',
    ),
    wavelink.Node(
        uri='https://lavalink.serenetia.com:443',
        password='https://dsc.gg/ajidevserver',
    ),
]

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def has_dj_role(member: discord.Member) -> bool:
    return (
        member.guild_permissions.manage_guild or
        any(r.name == DJ_ROLE_NAME for r in member.roles)
    )

def format_ms(ms: int) -> str:
    if not ms:
        return 'Unknown'
    total_sec = ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    return f'{minutes}:{seconds:02d}'

def build_progress_bar(position: int, length: int, size: int = 20) -> str:
    if not length:
        return '▬' * size
    filled = round((position / length) * size)
    return '▬' * filled + '🔘' + '▬' * (size - filled)

def music_embed(title: str, description: str, color: int = 0x5865f2) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

def error_embed(msg: str) -> discord.Embed:
    return music_embed('❌ Error', msg, 0xed4245)

def success_embed(msg: str) -> discord.Embed:
    return music_embed('✅ Success', msg, 0x57f287)

# ─────────────────────────────────────────
#  MUSIC COG
# ─────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await wavelink.Pool.connect(nodes=LAVALINK_NODES, client=self.bot)

    # ── Wavelink Events ──────────────────
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f'✅ Lavalink node connected: {payload.node.identifier}')

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        track = payload.track
        channel = player.channel
        if not hasattr(player, 'text_channel') or not player.text_channel:
            return
        embed = discord.Embed(
            color=0x5865f2,
            title='🎵 Now Playing',
            description=f'**[{track.title}]({track.uri})**'
        )
        embed.add_field(name='Artist',   value=track.author   or 'Unknown', inline=True)
        embed.add_field(name='Duration', value=format_ms(track.length), inline=True)
        embed.add_field(name='Source',   value=track.source   or 'Unknown', inline=True)
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        requester = getattr(track.extras, 'requester', None)
        if requester:
            embed.set_footer(text=f'Requested by {requester}')
        await player.text_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player
        if not player.queue and not player.auto_queue:
            if hasattr(player, 'text_channel') and player.text_channel:
                await player.text_channel.send(
                    embed=discord.Embed(
                        color=0x5865f2,
                        description='✅ Queue finished. See you next time! 👋'
                    )
                )

    # ── /play ─────────────────────────────
    @app_commands.command(name='play', description='Play a song from YouTube, SoundCloud or Spotify')
    @app_commands.describe(query='Song name or URL')
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send(embed=error_embed('You must be in a voice channel!'))

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        
        vc.text_channel = interaction.channel

        try:
            tracks = await wavelink.Playable.search(query)
            if not tracks:
                return await interaction.followup.send(embed=error_embed('No results found!'))

            if isinstance(tracks, wavelink.Playlist):
                for track in tracks:
                    track.extras = wavelink.ExtrasNamespace({'requester': str(interaction.user)})
                    vc.queue.put(track)
                embed = discord.Embed(
                    color=0x5865f2,
                    title='📋 Playlist Added',
                    description=f'Added **{len(tracks)}** tracks to the queue'
                )
                embed.set_footer(text=f'Requested by {interaction.user}')
                await interaction.followup.send(embed=embed)
            else:
                track = tracks[0]
                track.extras = wavelink.ExtrasNamespace({'requester': str(interaction.user)})
                vc.queue.put(track)
                embed = discord.Embed(
                    color=0x5865f2,
                    title='🎵 Added to Queue',
                    description=f'**[{track.title}]({track.uri})**'
                )
                embed.add_field(name='Artist',   value=track.author   or 'Unknown', inline=True)
                embed.add_field(name='Duration', value=format_ms(track.length), inline=True)
                embed.add_field(name='Source',   value=track.source   or 'Unknown', inline=True)
                if track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                embed.set_footer(text=f'Requested by {interaction.user}')
                await interaction.followup.send(embed=embed)

            if not vc.playing:
                await vc.play(vc.queue.get())

        except Exception as e:
            await interaction.followup.send(embed=error_embed(f'Could not play that track.\n`{e}`'))

    # ── /skip ─────────────────────────────
    @app_commands.command(name='skip', description='Skip the current song')
    async def skip(self, interaction: discord.Interaction):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        await vc.skip()
        await interaction.response.send_message(embed=success_embed('⏭ Skipped!'))

    # ── /pause ────────────────────────────
    @app_commands.command(name='pause', description='Pause or resume playback')
    async def pause(self, interaction: discord.Interaction):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        await vc.pause(not vc.paused)
        await interaction.response.send_message(embed=success_embed('▶️ Resumed.' if vc.paused else '⏸ Paused.'))

    # ── /stop ─────────────────────────────
    @app_commands.command(name='stop', description='Stop music and disconnect')
    async def stop(self, interaction: discord.Interaction):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        vc.queue.clear()
        await vc.disconnect()
        await interaction.response.send_message(embed=success_embed('⏹ Stopped and disconnected.'))

    # ── /nowplaying ───────────────────────
    @app_commands.command(name='nowplaying', description='Show the currently playing song')
    async def nowplaying(self, interaction: discord.Interaction):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        track = vc.current
        bar = build_progress_bar(vc.position, track.length)
        embed = discord.Embed(
            color=0x5865f2,
            title='🎶 Now Playing',
            description=f'**[{track.title}]({track.uri})**\n\n{bar}\n`{format_ms(vc.position)} / {format_ms(track.length)}`'
        )
        embed.add_field(name='Artist', value=track.author or 'Unknown', inline=True)
        embed.add_field(name='Source', value=track.source or 'Unknown', inline=True)
        embed.add_field(name='Volume', value=f'{vc.volume}%', inline=True)
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        requester = getattr(track.extras, 'requester', None)
        if requester:
            embed.set_footer(text=f'Requested by {requester}')
        await interaction.response.send_message(embed=embed)

    # ── /queue ────────────────────────────
    @app_commands.command(name='queue', description='Show the current queue')
    @app_commands.describe(page='Page number')
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.queue:
            return await interaction.response.send_message(embed=error_embed('The queue is empty.'), ephemeral=True)
        tracks = list(vc.queue)
        per_page = 10
        page = max(1, page) - 1
        chunk = tracks[page * per_page:(page + 1) * per_page]
        pages = max(1, -(-len(tracks) // per_page))
        desc = '\n'.join(
            f'`{page * per_page + i + 1}.` **{t.title}** — {format_ms(t.length)}'
            for i, t in enumerate(chunk)
        )
        embed = discord.Embed(
            color=0x5865f2,
            title=f'📋 Queue — {len(tracks)} track(s)',
            description=desc
        )
        embed.set_footer(text=f'Page {page + 1} of {pages}')
        await interaction.response.send_message(embed=embed)

    # ── /volume ───────────────────────────
    @app_commands.command(name='volume', description='Set the volume (1-150)')
    @app_commands.describe(level='Volume level')
    async def volume(self, interaction: discord.Interaction, level: int):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        if level < 1 or level > 150:
            return await interaction.response.send_message(embed=error_embed('Volume must be between 1 and 150.'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        await vc.set_volume(level)
        await interaction.response.send_message(embed=success_embed(f'🔊 Volume set to **{level}%**'))

    # ── /shuffle ──────────────────────────
    @app_commands.command(name='shuffle', description='Shuffle the queue')
    async def shuffle(self, interaction: discord.Interaction):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.queue:
            return await interaction.response.send_message(embed=error_embed('Queue is empty.'), ephemeral=True)
        vc.queue.shuffle()
        await interaction.response.send_message(embed=success_embed('🔀 Queue shuffled!'))

    # ── /loop ─────────────────────────────
    @app_commands.command(name='loop', description='Set loop mode')
    @app_commands.describe(mode='Loop mode')
    @app_commands.choices(mode=[
        app_commands.Choice(name='Off',   value='off'),
        app_commands.Choice(name='Track', value='track'),
        app_commands.Choice(name='Queue', value='queue'),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.response.send_message(embed=error_embed('Nothing is playing.'), ephemeral=True)
        labels = {'off': '➡️ Off', 'track': '🔂 Track', 'queue': '🔁 Queue'}
        if mode == 'off':
            vc.queue.mode = wavelink.QueueMode.normal
        elif mode == 'track':
            vc.queue.mode = wavelink.QueueMode.loop
        elif mode == 'queue':
            vc.queue.mode = wavelink.QueueMode.loop_all
        await interaction.response.send_message(embed=success_embed(f'Loop mode set to **{labels[mode]}**'))

    # ── /filter ───────────────────────────
    @app_commands.command(name='filter', description='Apply an audio filter (DJ only)')
    @app_commands.describe(type='Filter to apply')
    @app_commands.choices(type=[
        app_commands.Choice(name='🔊 Bassboost', value='bassboost'),
        app_commands.Choice(name='⚡ Nightcore', value='nightcore'),
        app_commands.Choice(name='🌀 8D Audio',  value='8d'),
        app_commands.Choice(name='🌊 Vaporwave', value='vaporwave'),
        app_commands.Choice(name='❌ Clear All', value='clear'),
    ])
    async def filter(self, interaction: discord.Interaction, type: str):
        if not has_dj_role(interaction.user):
            return await interaction.response.send_message(embed=error_embed('🎧 You need the **DJ** role!'), ephemeral=True)
        await interaction.response.defer()
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            return await interaction.followup.send(embed=error_embed('Nothing is playing.'))

        filters = vc.filters

        if type == 'clear':
            await vc.set_filters()
            return await interaction.followup.send(embed=success_embed('🎛️ All filters cleared.'))
        elif type == 'bassboost':
            filters.equalizer.set(bands=[
                {'band': 0, 'gain': 0.6},
                {'band': 1, 'gain': 0.7},
                {'band': 2, 'gain': 0.5},
            ])
        elif type == 'nightcore':
            filters.timescale.set(speed=1.3, pitch=1.3, rate=1.0)
        elif type == '8d':
            filters.rotation.set(rotation_hz=0.2)
        elif type == 'vaporwave':
            filters.timescale.set(speed=0.8, pitch=0.8, rate=1.0)

        descriptions = {
            'bassboost': '🔊 Bass cranked up!',
            'nightcore': '⚡ Faster + higher pitch!',
            '8d':        '🌀 Spatial surround effect!',
            'vaporwave': '🌊 Slower + lower pitch!',
        }
        await vc.set_filters(filters)
        await interaction.followup.send(embed=success_embed(f'🎛️ **{type}** applied!\n{descriptions[type]}'))

    # ── /search ───────────────────────────
    @app_commands.command(name='search', description='Search and pick a song')
    @app_commands.describe(query='Search term')
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send(embed=error_embed('You must be in a voice channel!'))

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return await interaction.followup.send(embed=error_embed('No results found.'))

        top5 = tracks[:5]
        desc = '\n'.join(
            f'`{i + 1}.` **{t.title}** — {t.author} `{format_ms(t.length)}`'
            for i, t in enumerate(top5)
        )
        embed = discord.Embed(
            color=0x5865f2,
            title=f'🔍 Results for: {query}',
            description=f'{desc}\n\nType a number **1–{len(top5)}** to pick, or `cancel`.'
        )
        await interaction.followup.send(embed=embed)

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await self.bot.wait_for('message', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return await interaction.channel.send(embed=error_embed('Search timed out.'))

        if msg.content.lower() == 'cancel':
            return await interaction.channel.send(embed=error_embed('Search cancelled.'))

        try:
            pick = int(msg.content) - 1
            track = top5[pick]
        except (ValueError, IndexError):
            return await interaction.channel.send(embed=error_embed('Invalid choice.'))

        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            vc.text_channel = interaction.channel

        track.extras = wavelink.ExtrasNamespace({'requester': str(interaction.user)})
        vc.queue.put(track)
        if not vc.playing:
            await vc.play(vc.queue.get())

        await interaction.channel.send(embed=success_embed(f'▶️ Playing **{track.title}** by {track.author}'))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
