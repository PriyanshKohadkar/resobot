# logger.py
import discord
from discord.ext import commands

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_log_channel(self, guild):
        return discord.utils.get(guild.text_channels, name="server-logs")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        log_channel = self.get_log_channel(message.guild)
        if log_channel is None or message.channel.id == log_channel.id:
            return

        attachments = ""
        if message.attachments:
            attachments = "\n📎 " + ", ".join(a.url for a in message.attachments)

        embed = discord.Embed(
            description=message.content or "*[no text content]*",
            color=discord.Color.blurple(),
            timestamp=message.created_at
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=f"#{message.channel.name}", inline=True)
        embed.add_field(name="Message ID", value=message.id, inline=True)
        if message.attachments:
            embed.add_field(name="Attachments", value=attachments, inline=False)
        embed.set_footer(text=f"Server: {message.guild.name}")

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # Ignore bots and if content didn't actually change
        if before.author.bot or before.content == after.content:
            return
        if not before.guild:
            return

        log_channel = self.get_log_channel(before.guild)
        if log_channel is None:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=after.edited_at or after.created_at
        )
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel", value=f"#{before.channel.name}", inline=True)
        embed.add_field(name="Message ID", value=before.id, inline=True)
        embed.add_field(name="Before", value=before.content or "*[empty]*", inline=False)
        embed.add_field(name="After", value=after.content or "*[empty]*", inline=False)
        embed.set_footer(text=f"Server: {before.guild.name}")

        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logger(bot))
