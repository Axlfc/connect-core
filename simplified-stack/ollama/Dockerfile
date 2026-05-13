# Dockerfile for running Ollama in the simplified stack
ARG BASE_IMAGE=ollama/ollama:latest
FROM ${BASE_IMAGE}

# We use root to ensure compatibility with bind mounts in the simplified stack,
# avoiding permission issues when the host directory is created by Docker.
USER root

# Create a home directory for the models and set permissions
RUN mkdir -p /root/.ollama

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the home directory
ENV HOME /root
WORKDIR /root

# Expose the default port
EXPOSE 11434

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
