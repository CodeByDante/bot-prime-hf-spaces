FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for bot operations)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs containers under UID 1000. Create a corresponding non-root user.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . $HOME/app

# Ensure user owns the entire home directory (important for SQLite directory-level writes)
RUN chown -R user:user $HOME

# Switch to the non-root user
USER user

# Expose web application port
EXPOSE 7080
ENV PORT=7080

CMD ["python", "app.py"]
