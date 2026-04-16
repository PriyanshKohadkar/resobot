# logger.py
import discord
from discord.ext import commands

BACKUP_GUILD_ID = 1491694084882960444        # 🔁 your backup server ID
BACKUP_CHANNEL_NAME = "server-logs-backup"  # channel name in backup server

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_backup_channel(self):
        guild = self.bot.get_guild(BACKUP_GUILD_ID)
        if guild is None:
            return None
        return discord.utils.get(guild.text_channels, name=BACKUP_CHANNEL_NAME)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        backup = await self.get_backup_channel()
        if backup is None:
            return

        embed = discord.Embed(
            description=message.content or "*[no text content]*",
            color=discord.Color.blurple(),
            timestamp=message.created_at
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=f"#{message.channel.name}", inline=True)
      #  embed.add_field(name="Message ID", value=message.id, inline=True)
       # embed.add_field(name="Origin Server", value=message.guild.name, inline=True)
        if message.attachments:
            embed.add_field(name="Attachments", value="\n📎 " + ", ".join(a.url for a in message.attachments), inline=False)
    #    embed.set_footer(text=f"Server: {message.guild.name}")

        await backup.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return
        if not before.guild:
            return

        backup = await self.get_backup_channel()
        if backup is None:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=after.edited_at or after.created_at
        )
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel", value=f"#{before.channel.name}", inline=True)
     #   embed.add_field(name="Message ID", value=before.id, inline=True)
     #   embed.add_field(name="Origin Server", value=before.guild.name, inline=True)
        embed.add_field(name="Before", value=before.content or "*[empty]*", inline=False)
        embed.add_field(name="After", value=after.content or "*[empty]*", inline=False)
      #  embed.set_footer(text=f"Server: {before.guild.name}")

        await backup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logger(bot))
