import io
import urllib.parse
import aiohttp
import discord
from discord.ext import commands

class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Reusing a persistent session is best practice for discord.py bots
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        # Clean up the session when the cog unloads
        self.bot.loop.create_task(self.session.close())

    @commands.hybrid_command(name="gen", description="Generate an image using AI.")
    async def generate(self, ctx: commands.Context, *, prompt: str):
        """Generates an image from a text prompt using Pollinations.ai"""
        # Defer the response immediately since image generation takes a few seconds
        await ctx.defer()

        # URL-encode the prompt to handle spaces and special characters safely
        encoded_prompt = urllib.parse.quote(prompt)
        api_url = f"https://image.pollinations.ai/p/{encoded_prompt}"

        try:
            # Fetch the image asynchronously so it doesn't freeze your bot
            async with self.session.get(api_url) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    
                    # Convert bytes into a file-like object discord can send
                    file_data = io.BytesIO(image_bytes)
                    discord_file = discord.File(file_data, filename="generated_image.png")

                    # Create a clean embed to display the image nicely
                    embed = discord.Embed(
                        title="✨ Image Generated!",
                        description=f"**Prompt:** {prompt}",
                        color=discord.Color.blurple()
                    )
                    embed.set_image(url="attachment://generated_image.png")
                    embed.set_footer(text="Powered by Pollinations.ai")

                    # Send the embed along with the file attachment
                    await ctx.send(embed=embed, file=discord_file)
                else:
                    await ctx.send("❌ Failed to generate image. The API might be busy.")
                    
        except Exception as e:
            print(f"Error in image generation command: {e}")
            await ctx.send("⚠️ An error occurred while trying to process your request.")

# Standard setup function to load the cog into your main runner
async def setup(bot):
    await bot.add_cog(ImageCog(bot))
