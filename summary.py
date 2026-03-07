import os
import re
import asyncio
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import requests

load_dotenv()

MODEL_NAME = "gemini-3.1-flash-lite-preview"
SYSTEM_PROMPT = (
    "You summarize Discord chats clearly and neutrally. "
    "Return concise bullet points with key decisions, action items, "
    "and open questions."
)

BLOCKED_WORDS = {
    "rape",
    "assault",
    "gangbang",
    "gangrape",
    "sex",
    "cum",
}
BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(BLOCKED_WORDS)) + r")\b",
    flags=re.IGNORECASE,
)


class Summary(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._api_key = os.getenv("GEMINI_API_KEY")

    @app_commands.command(
        name="summary",
        description="Summarize recent messages in this channel with Gemini",
    )
    @app_commands.describe(
        count="How many recent messages to summarize (5-200)"
    )
    async def summary(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 5, 200] = 25,
    ):
        if not self._api_key:
            await interaction.response.send_message(
                "GEMINI_API_KEY is missing. Add it to your environment first.",
                ephemeral=True,
            )
            return

        if not interaction.channel or not isinstance(
            interaction.channel, discord.abc.Messageable
        ):
            await interaction.response.send_message(
                "This command can only run in a text channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        messages: List[discord.Message] = []
        async for msg in interaction.channel.history(limit=count):
            if msg.author.bot:
                continue
            content = msg.clean_content.strip()
            if not content:
                continue
            if BLOCKED_PATTERN.search(content):
                continue
            messages.append(msg)

        if not messages:
            await interaction.followup.send(
                "No user messages found to summarize."
            )
            return

        messages.reverse()
        transcript = "\n".join(
            f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.display_name}: {m.clean_content}"
            for m in messages
        )

        prompt = (
            "Summarize the following Discord conversation.\n"
            "Format:\n"
            "1) TL;DR (2-3 lines)\n"
            "2) Key points (bullets)\n"
            "3) Action items (bullets)\n"
            "4) Open questions (bullets)\n\n"
            f"Conversation:\n{transcript}"
        )

        try:
            summary_text = await self._generate_summary(prompt)
        except Exception as exc:
            await interaction.followup.send(
                f"Failed to generate summary: {type(exc).__name__}: {exc}"
            )
            return

        if not summary_text:
            await interaction.followup.send("Gemini returned an empty summary.")
            return

        # Discord message hard limit is 2000 chars.
        if len(summary_text) <= 2000:
            await interaction.followup.send(summary_text)
            return

        chunks = [
            summary_text[i:i + 1900]
            for i in range(0, len(summary_text), 1900)
        ]
        for idx, chunk in enumerate(chunks, start=1):
            header = f"Summary ({idx}/{len(chunks)})\n"
            await interaction.followup.send(header + chunk)

    async def _generate_summary(self, prompt: str) -> str:
        # Use the Interactions API with store=false so this request is not persisted
        # as a retrievable Interaction object on Gemini.
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": f"models/{MODEL_NAME}",
            "store": False,
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "input": {
                "parts": [{"text": prompt}]
            },
        }

        def _post():
            return requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=45,
            )

        response = await asyncio.to_thread(_post)
        response.raise_for_status()
        data = response.json()

        outputs = data.get("output") or []
        text_parts: List[str] = []
        for item in outputs:
            for part in item.get("parts", []):
                text = part.get("text")
                if text:
                    text_parts.append(text)

        return "\n".join(text_parts).strip()


async def setup(bot: commands.Bot):
    await bot.add_cog(Summary(bot))
