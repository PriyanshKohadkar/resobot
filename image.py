import io
import os
import discord
from discord.ext import commands
from google import genai
from google.genai import types

class GeminiImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Automatically detects GEMINI_API_KEY from your environment/.env file
        self.client = genai.Client()

    @commands.hybrid_command(name="generate", description="Generate high-quality images via Gemini 3.1.")
    async def generate(self, ctx: commands.Context, *, prompt: str):
        """Generates an image using the official google-genai image modality workflow."""
        await ctx.defer()
        
        try:
            # Wrap the blocking API call inside an executor to keep the bot responsive
            response = await self.bot.loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(
                    model='gemini-3.1-flash-image',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio="1:1" # Standard square size
                        )
                    )
                )
            )
            
            # Loop through the response parts to look for the image block
            image_bytes = None
            for part in response.parts:
                if part.inline_data:
                    # Extract raw image bytes directly from the part data
                    image_bytes = part.inline_data.data
                    break
            
            if image_bytes:
                # Direct streaming to Discord via BytesIO
                file_data = io.BytesIO(image_bytes)
                discord_file = discord.File(file_data, filename="gemini_output.png")
                
                embed = discord.Embed(
                    title="🎨 Gemini Image Generation", 
                    description=f"**Prompt:** {prompt}", 
                    color=discord.Color.blue()
                )
                embed.set_image(url="attachment://gemini_output.png")
                embed.set_footer(text="Powered by Gemini 3.1 Flash Image")
                
                await ctx.send(embed=embed, file=discord_file)
            else:
                await ctx.send("❌ No image data was returned by the model. Check your prompt content.")
                
        except Exception as e:
            print(f"Gemini Gen AI Error: {e}")
            await ctx.send("❌ An unexpected error occurred. Double-check your API key environment configuration.")

async def setup(bot):
    await bot.add_cog(GeminiImage(bot))
