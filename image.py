import io
import os
import base64
import discord
from discord.ext import commands
from google import genai
from google.genai import types

class GeminiImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Automatically detects the working GEMINI_API_KEY from your environment
        self.client = genai.Client()

    @commands.hybrid_command(name="generate", description="Generate images using Gemini 3.1 Flash Image.")
    async def generate(self, ctx: commands.Context, *, prompt: str):
        """Generates an image using the official Google GenAI Interactions setup."""
        await ctx.defer()
        
        try:
            # We wrap the blocking API generation call inside an executor
            interaction = await self.bot.loop.run_in_executor(
                None,
                lambda: self.client.models.create(
                    model='gemini-3.1-flash-image',
                    input=f"Create a picture of: {prompt}",
                    config=types.GenerateContentConfig(
                        image_config=types.ImageConfig(
                            image_size='1K'  # 1K is standard 1024x1024 output
                        )
                    )
                )
            )
            
            # Pull the image block safely from the convenience output_image property
            if interaction.output_image and interaction.output_image.data:
                # The SDK packs the data in base64 string format inside this property
                raw_base64 = interaction.output_image.data
                image_bytes = base64.b64decode(raw_base64)
                
                # Turn bytes into a streamable Discord file object
                file_data = io.BytesIO(image_bytes)
                discord_file = discord.File(file_data, filename="gemini_output.png")
                
                # Build your response Embed
                embed = discord.Embed(
                    title="🎨 Gemini Image Generation", 
                    description=f"**Prompt:** {prompt}", 
                    color=discord.Color.blue()
                )
                embed.set_image(url="attachment://gemini_output.png")
                embed.set_footer(text="Powered by Gemini 3.1 Flash Image")
                
                await ctx.send(embed=embed, file=discord_file)
            else:
                await ctx.send("❌ Google AI did not return a valid image block for this prompt.")
                
        except Exception as e:
            print(f"Gemini Gen AI Error: {e}")
            await ctx.send("❌ Error generating image. Check your prompt syntax or API usage limits.")

async def setup(bot):
    await bot.add_cog(GeminiImage(bot))
