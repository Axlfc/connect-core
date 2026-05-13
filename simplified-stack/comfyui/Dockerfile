ARG BASE_IMAGE=ghcr.io/ai-dock/comfyui:cu121-2.1.0-2-20240409
FROM ${BASE_IMAGE}

# Set shell to bash for 'source' and other bashisms
SHELL ["/bin/bash", "-c"]

# 1) System deps for GL and threading
RUN apt-get update && apt-get install -y \
      libgl1-mesa-glx \
      libglib2.0-0 \
      libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Build-time argument for Torch index URL (default to CUDA 12.1)
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121

# 2) Optional: Update torch only if requested or if we need specific versions
# For most ai-dock images, torch is already pre-installed and optimized.
# We'll only re-install if we want to ensure specific versions.
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir \
      torch==2.3.0 \
      torchvision==0.18.0 \
      torchaudio==2.3.0 \
      --index-url ${TORCH_INDEX_URL}

# 3) Re-install xformers (only for CUDA) and pin transformers/diffusers
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir \
      transformers==4.37.0 \
      diffusers==0.16.1 && \
    if [[ "${TORCH_INDEX_URL}" == *"cu"* ]]; then \
      pip install --no-cache-dir xformers; \
    fi

# --- ACTUALIZACIÓN DEL REPOSITORIO BASE ---
WORKDIR /opt/ComfyUI
# 4. CRÍTICO: Asegurar que estamos en la rama 'master' antes de hacer el pull.
RUN git checkout master
# 5. Actualizar el repositorio base de ComfyUI (Pinned to a specific version for reproducibility)
RUN git fetch --all && git reset --hard 672439a3f28328df00438699195e347895f46452

# 6. INSTALAR REQUISITOS BASE DE COMFYUI
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# --- INYECCIÓN DE CUSTOM NODES DE LA COMUNIDAD (Paso CRÍTICO) ---

WORKDIR /opt/ComfyUI/custom_nodes

# Function to clone and install requirements of a node with specific commits for stability
RUN source /opt/environments/python/comfyui/bin/activate && \
    declare -A REPOS=( \
      ["comfyui_controlnet_aux"]="https://github.com/Fannovel16/comfyui_controlnet_aux|6562089f21d6006e88514930644365b682e0571d" \
      ["ComfyUI_IPAdapter_plus"]="https://github.com/cubiq/ComfyUI_IPAdapter_plus|03c19d45863c4573359d33b52d9a941a546738b8" \
      ["comfyui-tooling-nodes"]="https://github.com/Acly/comfyui-tooling-nodes|74972e008d3e23637e19277d71d0e51410d44007" \
      ["comfyui-inpaint-nodes"]="https://github.com/Acly/comfyui-inpaint-nodes|e620352554628a5065c71a399f666b3d30ad3d7e" \
    ) && \
    for REPO_NAME in "${!REPOS[@]}"; do \
      IFS='|' read -r REPO_URL REPO_COMMIT <<< "${REPOS[$REPO_NAME]}"; \
      echo "Installing ${REPO_NAME} at commit ${REPO_COMMIT}..."; \
      git clone "${REPO_URL}" "${REPO_NAME}" && \
      cd "${REPO_NAME}" && \
      git reset --hard "${REPO_COMMIT}" && \
      if [ -f "requirements.txt" ]; then \
        pip install --no-cache-dir -r "requirements.txt"; \
      fi && \
      cd ..; \
    done

# Volver al directorio de trabajo principal del contenedor
WORKDIR /opt/ComfyUI

# --- FIN DE CUSTOM NODES ---

# 7) Enable CUDA debug flags (optional)
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_USE_CUDA_DSA=1

# 8) Guarded sanity check
RUN source /opt/environments/python/comfyui/bin/activate && \
    python3 - <<'EOF'
import torch
print("PyTorch:", torch.__version__)
print("CUDA available?", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA toolkit:", torch.version.cuda)
    print("Compute capability:", torch.cuda.get_device_capability(0))
EOF
