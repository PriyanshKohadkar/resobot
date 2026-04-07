import discord
from discord.ext import commands
from discord import app_commands
import mcstatus

SERVER_IP = "Resodrippers.aternos.me:45879"  # ← Change this to your server IP

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mcstatus", description="Check if the Minecraft server is online")
    async def mcstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            server = mcstatus.JavaServer.lookup(SERVER_IP)
            status = server.status()

            embed = discord.Embed(
                title="🟢 Server is Online!",
                color=discord.Color.green()
            )
            embed.add_field(name="IP", value=SERVER_IP, inline=True)
            embed.add_field(name="Players", value=f"{status.players.online}/{status.players.max}", inline=True)
            embed.add_field(name="Ping", value=f"{round(status.latency)}ms", inline=True)
            embed.add_field(name="Version", value=status.version.name, inline=True)

            if status.players.sample:
                names = [p.name for p in status.players.sample]
                embed.add_field(name="Online Players", value="\n".join(names), inline=False)

            await interaction.followup.send(embed=embed)

        except Exception:
            embed = discord.Embed(
                title="🔴 Server is Offline!",
                description="Could not connect to the server.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Minecraft(bot))
