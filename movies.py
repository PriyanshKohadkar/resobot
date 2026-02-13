import os
import random
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

BASE_URL = "https://api.themoviedb.org/3"
OMDB_BASE_URL = "http://www.omdbapi.com/"

# ---------------- IMDb Top 250 ---------------- #

IMDB_TOP_250_IDS = [
"tt0111161","tt0068646","tt0071562","tt0468569","tt0050083",
"tt0108052","tt0167260","tt0110912","tt0060196","tt0120737",
"tt0109830","tt0137523","tt1375666","tt0080684","tt0167261",
"tt0099685","tt0073486","tt0047478","tt0114369","tt0317248",
"tt0102926","tt0038650","tt0118799","tt0076759","tt0120815",
"tt0245429","tt0120689","tt0816692","tt0114814","tt0110413",
"tt0056058","tt0021749","tt0253474","tt0103064","tt1675434",
"tt0027977","tt0407887","tt0088763","tt0120586","tt2582802",
"tt0482571","tt0110357","tt0910970","tt0034583","tt0095327",
"tt0054215","tt0082971","tt0064116","tt0047396","tt0078748",
"tt0078788","tt0209144","tt0364569","tt0057012","tt0032553",
"tt0053125","tt0095765","tt0211915","tt0114709","tt0081505",
"tt1345836","tt0022100","tt4154796","tt0090605","tt0169547",
"tt7286456","tt0086190","tt0052357","tt4633694","tt0112573",
"tt1187043","tt0087843","tt0091251","tt0119698","tt5311514",
"tt0045152","tt8267604","tt0361748","tt2380307","tt0119217",
"tt0053604","tt0180093","tt0113277","tt0457430","tt0086879",
"tt8503618","tt0056592","tt0044741","tt0119488","tt0059578",
"tt0043014","tt0055630","tt0093058","tt2106476","tt0033467",
"tt0082096","tt0040522","tt0053291","tt1255953","tt0042192",
"tt0012349","tt0025316","tt0097576","tt0367110","tt0112641",
"tt0095016","tt5074352","tt0086250","tt0040897","tt0015864",
"tt0105236","tt1832382","tt0036775","tt0208092","tt0056172",
"tt0070735","tt0117951","tt0041959","tt0211915","tt0053198",
"tt0089881","tt0071853","tt0091763","tt0046438","tt0046912",
"tt1392214","tt10272386","tt1895587","tt0477348","tt0405094",
"tt0051792","tt0032138","tt0116282","tt0080678","tt0042876",
"tt0071315","tt0057115","tt0031381","tt0435761","tt0079944",
"tt0075314","tt0266543","tt0347149","tt1305806","tt2096673",
"tt0050986","tt1130884","tt0083658","tt0047296","tt0017136",
"tt0096283","tt0050212","tt0993846","tt0048473","tt1205489",
"tt0061512","tt0107207","tt4016934","tt0118849","tt0031679",
"tt0032976","tt0020629","tt0092005","tt0093779","tt0052618",
"tt1745960","tt3170832","tt2278388","tt0017925","tt0050976",
"tt0046268","tt12593682","tt1392190","tt1950186","tt2024544",
"tt0469494","tt0266697","tt0097165","tt0118715","tt0033870",
"tt0036868","tt0107290","tt0405159","tt0084787","tt0072684",
"tt0105695","tt0268978","tt0040746","tt0081398","tt0073195",
"tt0758758","tt0113247","tt0245712","tt0032551","tt0080678",
"tt0046911","tt0103074","tt0050783","tt0060827","tt0074958",
"tt0395169","tt0119485","tt0039689","tt0052311","tt0044079",
"tt0099348","tt0047528","tt1454029","tt0101414","tt0045112",
"tt0089880","tt0075148","tt0049833","tt0077416","tt0033871",
"tt0051201","tt0103639","tt0057115","tt0032138","tt0032551"
]


# ------------------------------------------------ #

class MovieCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch(self, url, params=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()

    async def get_imdb_rating(self, title, year=None):
        params = {"apikey": OMDB_API_KEY, "t": title}
        if year:
            params["y"] = year

        data = await self.fetch(OMDB_BASE_URL, params)
        if data.get("Response") == "True":
            return data.get("imdbRating", "N/A")
        return "N/A"

    def compact_embed(self, title, rating, poster_path):
        embed = discord.Embed(
            title=f"🎬 {title}",
            color=discord.Color.blue()
        )
        embed.add_field(name="⭐ IMDb Rating", value=str(rating), inline=False)
        embed.set_footer(text="Powered by TMDB + OMDb")

        if poster_path:
            embed.set_thumbnail(
                url=f"https://image.tmdb.org/t/p/w200{poster_path}"
            )

        return embed

    # ==============================
    # 🏆 Recommend (IMDb Top 250)
    # ==============================

    @app_commands.command(name="recommend", description="Recommend from IMDb Top 250")
    async def recommend(self, interaction: discord.Interaction):

        await interaction.response.defer()

        imdb_id = random.choice(IMDB_TOP_250_IDS)

        data = await self.fetch(
            OMDB_BASE_URL,
            {"apikey": OMDB_API_KEY, "i": imdb_id}
        )

        if data.get("Response") != "True":
            await interaction.followup.send("❌ Could not fetch movie.")
            return

        embed = discord.Embed(
            title=f"🏆 {data['Title']}",
            color=discord.Color.gold()
        )

        embed.add_field(name="⭐ IMDb Rating", value=data.get("imdbRating", "N/A"), inline=False)
        embed.add_field(name="📅 Year", value=data.get("Year", "N/A"), inline=True)
        embed.add_field(name="🎭 Genre", value=data.get("Genre", "N/A"), inline=False)
        embed.set_thumbnail(url=data.get("Poster"))
        embed.set_footer(text="IMDb Top 250 • Data via OMDb")

        await interaction.followup.send(embed=embed)

    # ==============================
    # 🔎 Search Movie (Dropdown)
    # ==============================

    class MovieSelect(discord.ui.Select):
        def __init__(self, movies, cog):
            self.movies = movies
            self.cog = cog

            options = [
                discord.SelectOption(
                    label=f"{m['title']} ({m.get('release_date','')[:4]})",
                    value=str(i)
                )
                for i, m in enumerate(movies)
            ]

            super().__init__(
                placeholder="Select the correct movie...",
                min_values=1,
                max_values=1,
                options=options
            )

        async def callback(self, interaction: discord.Interaction):
            index = int(self.values[0])
            movie = self.movies[index]

            imdb_rating = await self.cog.get_imdb_rating(
                movie["title"],
                movie.get("release_date", "")[:4]
            )

            embed = self.cog.compact_embed(
                movie["title"],
                imdb_rating,
                movie.get("poster_path")
            )

            await interaction.response.edit_message(embed=embed, view=None)

    class MovieSelectView(discord.ui.View):
        def __init__(self, movies, cog):
            super().__init__(timeout=60)
            self.add_item(MovieCommands.MovieSelect(movies, cog))

    @app_commands.command(name="movie", description="Search a movie by name")
    async def search_movie(self, interaction: discord.Interaction, movie_name: str):

        await interaction.response.defer()

        data = await self.fetch(
            f"{BASE_URL}/search/movie",
            {"api_key": TMDB_API_KEY, "query": movie_name}
        )

        if not data["results"]:
            await interaction.followup.send("❌ Movie not found.")
            return

        movies = data["results"][:5]

        view = MovieCommands.MovieSelectView(movies, self)

        await interaction.followup.send(
            "🎬 Select the correct movie:",
            view=view
        )

    # ==============================
    # 📺 Search Series (unchanged)
    # ==============================

    @app_commands.command(name="series", description="Search a TV series")
    async def search_series(self, interaction: discord.Interaction, series_name: str):

        await interaction.response.defer()

        data = await self.fetch(
            f"{BASE_URL}/search/tv",
            {"api_key": TMDB_API_KEY, "query": series_name}
        )

        if not data["results"]:
            await interaction.followup.send("❌ Series not found.")
            return

        series = data["results"][0]

        imdb_rating = await self.get_imdb_rating(
            series["name"],
            series.get("first_air_date", "")[:4]
        )

        embed = discord.Embed(
            title=f"📺 {series['name']}",
            color=discord.Color.green()
        )

        embed.add_field(name="⭐ IMDb Rating", value=str(imdb_rating), inline=False)
        embed.set_footer(text="Powered by TMDB + OMDb")

        if series.get("poster_path"):
            embed.set_thumbnail(
                url=f"https://image.tmdb.org/t/p/w200{series['poster_path']}"
            )

        await interaction.followup.send(embed=embed)

    # ==============================
    # 🔥 Trending (unchanged)
    # ==============================

    @app_commands.command(name="trending", description="Get trending movies")
    async def trending(self, interaction: discord.Interaction):

        await interaction.response.defer()

        data = await self.fetch(
            f"{BASE_URL}/trending/movie/week",
            {"api_key": TMDB_API_KEY}
        )

        movie = random.choice(data["results"][:10])

        imdb_rating = await self.get_imdb_rating(
            movie["title"],
            movie.get("release_date", "")[:4]
        )

        embed = self.compact_embed(
            movie["title"],
            imdb_rating,
            movie.get("poster_path")
        )

        await interaction.followup.send(embed=embed)

    # ==============================
    # 🎞 Similar Movies (unchanged)
    # ==============================

    @app_commands.command(name="similar_movies", description="Get movies similar to another")
    async def similar_movies(self, interaction: discord.Interaction, movie_name: str):

        await interaction.response.defer()

        search = await self.fetch(
            f"{BASE_URL}/search/movie",
            {"api_key": TMDB_API_KEY, "query": movie_name}
        )

        if not search["results"]:
            await interaction.followup.send("❌ Movie not found.")
            return

        movie_id = search["results"][0]["id"]

        similar = await self.fetch(
            f"{BASE_URL}/movie/{movie_id}/similar",
            {"api_key": TMDB_API_KEY}
        )

        if not similar["results"]:
            await interaction.followup.send("No similar movies found.")
            return

        movie = random.choice(similar["results"][:10])

        imdb_rating = await self.get_imdb_rating(
            movie["title"],
            movie.get("release_date", "")[:4]
        )

        embed = self.compact_embed(
            movie["title"],
            imdb_rating,
            movie.get("poster_path")
        )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MovieCommands(bot))
