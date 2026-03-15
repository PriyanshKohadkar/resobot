import os 
import time
import asyncio
from google import genai
from google.genai import types
from discord.ext import commands

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    async def wait_if_needed(self):
        now = time.time()
        # Remove calls that are older than the period (60s)
        self.calls = [c for c in self.calls if c > now - self.period]
        
        if len(self.calls) >= self.max_calls:
            # Calculate how long to wait until the oldest call is outside the window
            sleep_time = self.calls[0] + self.period - now
            if sleep_time > 0:
                print(f"Rate Limit reached. Waiting {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)
            # Re-clean after sleeping to be safe
            return await self.wait_if_needed()
            
        self.calls.append(time.time())

# Initialize limiter: 8 calls per 60 seconds
limiter = RateLimiter(max_calls=8, period=60)

class Intel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        # Using the specific version you requested
        self.model_id = "gemini-2.5-flash-lite" 

    @commands.command(name="intel")
    async def intel(self, ctx, *, query: str = None):
        if not self.client:
            return await ctx.send("❌ API Key missing! Check your environment variables.")

        if not query and not ctx.message.attachments:
            return await ctx.send("🧐 Kuch toh likho ya image bhejo!")

        async with ctx.typing():
            try:
                # 1. Wait for Rate Limiter
                await limiter.wait_if_needed()

                # 2. Process Image if exists
                image_part = None
                if ctx.message.attachments:
                    attachment = ctx.message.attachments[0]
                    if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
                        img_bytes = await attachment.read()
                        image_part = types.Part.from_bytes(
                            data=img_bytes, 
                            mime_type=attachment.content_type
                        )

                prompt_text = f"Fetch latest news and explain in Hinglish: {query if query else 'Analyze this image'}"
                contents = [prompt_text]
                if image_part:
                    contents.append(image_part)

                # 3. Try with Search first
                try:
                    response = self.client.models.generate_content(
                        model=self.model_id,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())]
                        )
                    )
                except Exception as search_error:
                    # Fallback if Search specifically is exhausted
                    if "429" in str(search_error) or "RESOURCE_EXHAUSTED" in str(search_error):
                        await ctx.send("⚠️ *Search quota full, answering from memory...*")
                        response = self.client.models.generate_content(
                            model=self.model_id,
                            contents=contents
                        )
                    else:
                        raise search_error

                # 4. Send the result
                if response.text:
                    for i in range(0, len(response.text), 2000):
                        await ctx.send(response.text[i:i+2000])
                else:
                    await ctx.send("⚠️ Model empty response diya. Try again.")

            except Exception as e:
                await ctx.send(f"⚠️ **Error:** `{str(e)[:150]}`")

async def setup(bot):
    await bot.add_cog(Intel(bot))
