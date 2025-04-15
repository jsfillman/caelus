FROM python:3.10-slim

# Install system dependencies with proper JACK support
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    libsndfile1 \
    libjack-jackd2-dev \
    jackd2 \
    pulseaudio \
    pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application code
COPY . /app/

# Create virtual environment
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir python-osc pyo mido python-rtmidi numpy JACK-Client

# Set up a dummy sound card with null sink for JACK
RUN echo "pcm.dummy { type hw card 0 }" > /etc/asound.conf && \
    echo "ctl.dummy { type hw card 0 }" >> /etc/asound.conf

# Make caelus executable
RUN chmod +x /app/caelus

# Create directory for presets
RUN mkdir -p /app/presets

# Script to start Jack server before launching the app
COPY start-worker.sh /app/
RUN chmod +x /app/start-worker.sh

# Use the startup script as entrypoint
ENTRYPOINT ["/app/start-worker.sh"]
