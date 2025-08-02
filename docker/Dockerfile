# Use official Nvidia CUDA base image for GPU support
FROM nvidia/cuda:12.2.0-base-ubuntu22.04

# Install wget, tar, ca-certificates for downloading and extracting
RUN apt-get update && apt-get install -y wget tar ca-certificates

# Download the T-Rex Miner binary
RUN wget https://github.com/trexminer/T-Rex/releases/download/0.26.8/t-rex-0.26.8-linux.tar.gz \
    && tar -xvf t-rex-0.26.8-linux.tar.gz \
    && mv t-rex /usr/local/bin/ \
    && rm t-rex-0.26.8-linux.tar.gz

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use entrypoint script to start miner with environment variables
ENTRYPOINT ["/entrypoint.sh"]
