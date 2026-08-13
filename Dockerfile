FROM debian:trixie-slim
ARG TARGETARCH
ARG TARGETVARIANT

# Optional dependencies to install. The default image is Piper-only; the
# separate omnivoice image adds "omnivoice" here, which pulls in torch and
# transformers (see .github/workflows/publish.yml).
ARG EXTRAS="zeroconf,zh,web"

# Install piper
WORKDIR /usr/src

COPY ./pyproject.toml ./
# The package has to exist for setuptools' packages.find to see it, or the
# editable install maps nothing and importing wyoming_piper only works from
# /usr/src. Just the __init__.py, so the install layer stays cached until the
# version changes -- which changes pyproject.toml above anyway.
COPY ./wyoming_piper/__init__.py ./wyoming_piper/
RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
    \
    && python3 -m venv .venv \
    # pip must be upgraded too: bookworm ships 23.0.1, which rejects the PyTorch
    # index's wheels as "inconsistent Name: expected 'typing-extensions', but
    # metadata has 'typing_extensions'" and then silently backtracks to an
    # ancient torch instead of failing.
    && .venv/bin/pip3 install --no-cache-dir -U \
        pip \
        setuptools \
        wheel \
    \
    # Install CPU-only torch up front. Both piper-tts[zh] and omnivoice require
    # torch, and as an --extra-index-url the CPU index was merely merged with
    # PyPI, so pip resolved the default wheels and ~2.7 GB of unused CUDA libs.
    # --index-url is what actually pins it to the CPU builds.
    && TORCH="torch" \
    && WANT_OMNIVOICE="" \
    && INSTALL_EXTRAS="${EXTRAS}" \
    && if echo ",${EXTRAS}," | grep -q ",omnivoice,"; then \
        TORCH="torch torchaudio"; \
        WANT_OMNIVOICE="1"; \
        # Install the omnivoice package separately, without its dependencies:
        # it requires gradio, librosa, webdataset and tensorboardx for its demo
        # and training paths, which this backend never imports (42 packages,
        # ~600 MB). The omnivoice-deps extra pins what is actually needed.
        INSTALL_EXTRAS="$(echo "${EXTRAS}" | sed 's/\bomnivoice\b/omnivoice-deps/')"; \
    fi \
    && .venv/bin/pip3 install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        ${TORCH} \
    \
    && .venv/bin/pip3 install --no-cache-dir \
        --extra-index-url https://www.piwheels.org/simple \
        -e ".[${INSTALL_EXTRAS}]" \
    \
    && if [ -n "${WANT_OMNIVOICE}" ]; then \
        .venv/bin/pip3 install --no-cache-dir --no-deps omnivoice; \
    fi \
    \
    && rm -rf /var/lib/apt/lists/*

COPY ./ ./

EXPOSE 10200
EXPOSE 5000

ENTRYPOINT ["bash", "docker_run.sh"]
