# -------- Base Image --------
FROM python:3.14-slim

# -------- Prevent Python buffering --------
ENV PYTHONUNBUFFERED=1

# -------- Install system dependencies + Chromium --------
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# -------- Set Chrome paths --------
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# -------- Set working directory --------
WORKDIR /app

# -------- Install Python dependencies --------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------- Copy project files --------
COPY . .

# -------- Start the bot --------
CMD ["python", "MyBot.py"]
