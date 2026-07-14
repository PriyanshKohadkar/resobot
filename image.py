import io
import os
import discord
from discord.ext import commands
from google import genai
from google.genai import types

class GeminiImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Instantiates the client natively (uses your working GEMINI_API_KEY env)
        self.client = genai.Client()

    @commands.hybrid_command(name="generate", description="Generate high-quality images via Gemini 3.1.")
    async def generate(self, ctx: commands.Context, *, prompt: str):
        """Generates an image using the official response_modalities framework."""
        await ctx.defer()
        
        try:
            # We run the blocking client call in an executor so your bot doesn't hang
            response = await self.bot.loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(
                    model='gemini-3.1-flash-image',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio="1:1" # Renders a standard square block
                        )
                    )
                )
            )
            
            # Find and parse the binary image block out of the response data parts
            image_bytes = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        # The new SDK provides the unencoded image bytes here directly
                        image_bytes = part.inline_data.data
                        break
            
            if image_bytes:
                # Pipe bytes straight into a streaming object for Discord
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
                await ctx.send("❌ No image data was returned. Your prompt might have triggered a safety filter.")
                
        except Exception as e:
            print(f"Gemini Gen AI Image Cog Error: {e}")
            await ctx.send("❌ Failed to process image request. Double-check your daily image model quota.")

async def setup(bot):
    await bot.add_cog(GeminiImage(bot))
