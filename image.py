import io
import aiohttp
import discord
from discord.ext import commands
import os

class HFImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        # You choose which model repo to hit
        self.model_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        self.headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.hybrid_command(name="sdgenerate", description="Generate an image using Stable Diffusion XL.")
    async def sdgenerate(self, ctx: commands.Context, *, prompt: str):
        await ctx.defer()
        
        payload = {"inputs": prompt}
        
        try:
            async with self.session.post(self.model_url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    file_data = io.BytesIO(image_bytes)
                    discord_file = discord.File(file_data, filename="sdxl_output.png")
                    
                    embed = discord.Embed(title="🚀 SDXL Generation", description=f"**Prompt:** {prompt}", color=0x2ecc71)
                    embed.set_image(url="attachment://sdxl_output.png")
                    
                    await ctx.send(embed=embed, file=discord_file)
                elif response.status == 503:
                    await ctx.send("⏳ The model is currently loading up on Hugging Face. Please try again in a few seconds!")
                else:
                    await ctx.send(f"❌ Failed to generate (Status: {response.status}).")
        except Exception as e:
            print(f"Hugging Face Error: {e}")
            await ctx.send("⚠️ An error occurred contacting Hugging Face.")

async def setup(bot):
    await bot.add_cog(HFImage(bot))
