# CUDI Video – Container für die Cloud (z. B. Hugging Face Spaces, Render, eigener Server)
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-inter fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces startet Container als Benutzer 1000.
RUN useradd -m -u 1000 cudi
WORKDIR /app
COPY cudi_video/requirements.txt cudi_video/requirements.txt
RUN pip install --no-cache-dir -r cudi_video/requirements.txt
COPY cudi_video cudi_video
COPY presets presets

ENV CUDI_VIDEO_OUTPUT=/tmp/cudi/video_output \
    CUDI_VIDEO_CACHE=/tmp/cudi/cache \
    PORT=7860
USER cudi
EXPOSE 7860
CMD ["sh", "-c", "python -m cudi_video web --port ${PORT}"]
