import io
import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os

class GeminiImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Make sure GEMINI_API_KEY is in your local .env file
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    @commands.hybrid_command(name="gen", description="Generate high-quality images via Gemini.")
    async def generate(self, ctx: commands.Context, *, prompt: str):
        await ctx.defer()
        
        try:
            # Call the model asynchronously inside an executor so it doesn't block the bot loop
            result = await self.bot.loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_images(
                    model='gemini-2.5-flash-image-lite',
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/png",
                        aspect_ratio="1:1"
                    )
                )
            )
            
            # Extract raw image bytes from response
            generated_image = result.generated_images[0]
            image_bytes = generated_image.image.image_bytes
            
            # Send file directly via BytesIO
            file_data = io.BytesIO(image_bytes)
            discord_file = discord.File(file_data, filename="gemini_output.png")
            
            embed = discord.Embed(title="🎨 Gemini Image Generation", description=f"**Prompt:** {prompt}", color=0x3498db)
            embed.set_image(url="attachment://gemini_output.png")
            
            await ctx.send(embed=embed, file=discord_file)
            
        except Exception as e:
            print(f"Gemini Image Error: {e}")
            await ctx.send("❌ Error generating image with Gemini. Check your limits or prompt.")

async def setup(bot):
    await bot.add_cog(GeminiImage(bot))
