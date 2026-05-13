FROM qdrant/qdrant:v1.9.2

USER root

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create a non-root user with specific UID/GID
RUN groupadd -g 1000 qdrant && \
    useradd -u 1000 -g qdrant -s /bin/bash qdrant

# Change ownership of the entire qdrant directory
RUN chown -R qdrant:qdrant /qdrant

# Switch to the non-root user
USER qdrant

WORKDIR /qdrant

EXPOSE 6333 6334
