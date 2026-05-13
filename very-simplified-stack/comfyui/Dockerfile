ARG BASE_IMAGE=ghcr.io/ai-dock/comfyui:latest-cuda
FROM ${BASE_IMAGE}

# 1) System deps for GL and threading
RUN apt-get update && apt-get install -y \
      libgl1-mesa-glx \
      libglib2.0-0 \
      libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2) Remove any old torch/xformers/etc.
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip uninstall -y torch torchvision torchaudio xformers flash-attn

# 3) Set the arch list to include sm_120
ENV TORCH_CUDA_ARCH_LIST="5.0;6.0;7.0;7.5;8.0;8.6;9.0;12.0"

# 4) Install STABLE torch/torchvision/torchaudio for CUDA 12.1
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir \
      torch==2.3.0 \
      torchvision==0.18.0 \
      torchaudio==2.3.0 \
      --index-url https://download.pytorch.org/whl/cu121

# 5) Re-install xformers and pin transformers/diffusers
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir \
      transformers==4.37.0 \
      diffusers==0.16.1 \
      xformers

# --- ACTUALIZACIÓN DEL REPOSITORIO BASE ---
WORKDIR /opt/ComfyUI
# 6. CRÍTICO: Asegurar que estamos en la rama 'master' antes de hacer el pull.
RUN git checkout master
# 7. Actualizar el repositorio base de ComfyUI
RUN git fetch --all && git pull origin master

# 8. INSTALAR REQUISITOS BASE DE COMFYUI (Si el pull los actualizó)
# Esto garantiza que el entorno base esté listo para los custom nodes.
RUN source /opt/environments/python/comfyui/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# --- INYECCIÓN DE CUSTOM NODES DE LA COMUNIDAD (Paso CRÍTICO) ---

WORKDIR /opt/ComfyUI/custom_nodes

# Función para clonar e instalar requisitos de un nodo
RUN source /opt/environments/python/comfyui/bin/activate && \
    declare -a REPOS=( \
      "https://github.com/Fannovel16/comfyui_controlnet_aux" \
      "https://github.com/cubiq/ComfyUI_IPAdapter_plus" \
      "https://github.com/Acly/comfyui-tooling-nodes" \
      "https://github.com/Acly/comfyui-inpaint-nodes" \
    ) && \
    for REPO_URL in "${REPOS[@]}"; do \
      REPO_NAME=$(basename "${REPO_URL}"); \
      echo "Installing ${REPO_NAME}..."; \
      git clone "${REPO_URL}" "${REPO_NAME}" && \
      cd "${REPO_NAME}" && \
      if [ -f "requirements.txt" ]; then \
        pip install --no-cache-dir -r "requirements.txt"; \
      fi && \
      cd ..; \
    done

# Volver al directorio de trabajo principal del contenedor
WORKDIR /opt/ComfyUI

# --- FIN DE CUSTOM NODES ---

# 9) Enable CUDA debug flags (optional)
ENV CUDA_LAUNCH_BLOCKING=1
ENV TORCH_USE_CUDA_DSA=1

# 10) Guarded sanity check
RUN source /opt/environments/python/comfyui/bin/activate && \
    python3 - <<'EOF'
import torch
print("PyTorch:", torch.__version__)
print("CUDA available?", torch.cuda.is_available())
print("CUDA toolkit:", torch.version.cuda)
if torch.cuda.is_available():
    print("Compute capability:", torch.cuda.get_device_capability(0))
EOF