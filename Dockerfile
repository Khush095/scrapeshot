# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to the terminal
ENV PYTHONUNBUFFERED 1

# --- Install system dependencies needed by Playwright/Chromium ---
# This replaces the need for packages.txt
RUN apt-get update && apt-get install -y \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Install the Playwright browser ---
# This command runs during the build, so you don't need to do it in app.py
RUN playwright install chromium

# Copy the rest of your application code
COPY . .

# Command to run your Streamlit application
# Render provides the PORT environment variable, so we use that.
CMD ["streamlit", "run", "src/streamlit_app.py", "--server.port", "$PORT"]