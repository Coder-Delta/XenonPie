FROM python:3.13-slim

# system deps for pytesseract + pdf2image
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install python deps first (layer cache)
COPY pyproject.toml .
RUN pip install --upgrade pip
RUN pip install \
    httpx \
    beautifulsoup4 \
    feedparser \
    pytesseract \
    pdf2image \
    pdfplumber \
    openai \
    anthropic \
    groq \
    google-generativeai \
    langchain \
    langgraph \
    pgvector \
    sentence-transformers \
    redis \
    asyncpg \
    "sqlalchemy[asyncio]" \
    alembic \
    python-telegram-bot \
    twilio \
    resend \
    pydantic-settings \
    pyyaml \
    loguru \
    apscheduler \
    pytest \
    pytest-asyncio \
    python-dotenv \
    playwright

# install playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# copy source
COPY . .

# create dirs
RUN mkdir -p logs .cache

EXPOSE 8000

CMD ["python", "main.py"]