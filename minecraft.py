import discord
from discord.ext import commands
from discord import app_commands
import mcstatus
import asyncio
import errno

SERVER_IP = "Resodrippers.aternos.me:45879"
MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds between retries

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mcstatus", description="Check if the Minecraft server is online")
    async def mcstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()

        loop = asyncio.get_event_loop()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                server = await loop.run_in_executor(None, mcstatus.JavaServer.lookup, SERVER_IP)
                status = await loop.run_in_executor(None, server.status)

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
                return  # success, stop here

            except OSError as e:
                if e.errno == errno.EPIPE:  # Broken pipe — retry
                    last_error = "broken_pipe"
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                else:
                    last_error = str(e)
                    break  # different OSError, no point retrying

            except Exception as e:
                last_error = str(e)
                break  # any other error, stop retrying

        # All attempts exhausted or non-retryable error
        if last_error == "broken_pipe":
            embed = discord.Embed(
                title="🔴 Server is Offline!",
                description=f"Tried {MAX_RETRIES} times but the server kept dropping the connection.\nIt may be starting up or going to sleep.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="🔴 Server is Offline!",
                description=f"Could not connect to the server.\n`{last_error}`",
                color=discord.Color.red()
            )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Minecraft(bot))
