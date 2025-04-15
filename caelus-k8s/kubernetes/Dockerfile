
FROM python:3.10-slim

# Set up realtime privileges and audio group
RUN apt-get update && apt-get install -y \
    libcap2-bin \
    && groupadd -r audio \
    && setcap cap_sys_nice,cap_ipc_lock+ep /usr/bin/python3.10 \
    && setcap cap_sys_nice,cap_ipc_lock+ep /usr/bin/jackd

# Install system dependencies and audio packages
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    portaudio19-dev \
    libsndfile1 \
    python3-pyo \
    jackd2 \
    jacktrip \
    liblo-dev \
    libportmidi-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application code
COPY . /app/

# Create virtual environment
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Configure JACK for network audio
RUN echo "JACK_NO_AUDIO_RESERVATION=1" >> /etc/environment && \
    echo "JACK_PROMISCUOUS_SERVER=jack" >> /etc/environment

# Make caelus executable
RUN chmod +x /app/caelus

# Create directory for presets
RUN mkdir -p /app/presets

# Script to start Jack server before launching the app
COPY start-worker.sh /app/
RUN chmod +x /app/start-worker.sh

# Use the startup script as entrypoint
ENTRYPOINT ["/app/start-worker.sh"]
