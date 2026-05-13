# Option 1: Use official unprivileged image (RECOMMENDED)
# Simply use this in your docker-compose.yml instead:
# image: qdrant/qdrant:v1.9.2-unprivileged

# Option 2: Build custom non-root image from standard image
FROM qdrant/qdrant:v1.9.2

# Create a non-root user with specific UID/GID
RUN groupadd -g 1000 qdrant && \
    useradd -u 1000 -g qdrant -s /bin/bash qdrant

# Change ownership of the entire qdrant directory
RUN chown -R qdrant:qdrant /qdrant

# Switch to the non-root user
USER qdrant

# Set the working directory (the entrypoint script expects to be run from here)
WORKDIR /qdrant

# Expose the default ports
EXPOSE 6333 6334

# Use the existing entrypoint from the base image
# The base image has CMD ["./entrypoint.sh"] which will work with the existing ENTRYPOINT