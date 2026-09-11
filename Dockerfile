FROM debian:trixie-slim
ARG TARGETARCH
ARG TARGETVARIANT

# Optional dependencies to install. The default image is Piper-only; the
# separate omnivoice image adds "omnivoice" here, which pulls in torch and
# transformers (see .github/workflows/publish.yml).
# "th" is deliberately absent: TLTK drags in gensim, scikit-learn, scipy and
# pandas for ~500 MB, so Thai is left to a manual `pip install '.[th]'`.
# "ja" is out for now as well; install it by hand with `pip install '.[ja]'`.
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
    && .venv/bin/pip3 install --no-cache-dir -U \
        pip \
        setuptools \
        wheel \
    \
    && WANT_OMNIVOICE="" \
    && INSTALL_EXTRAS="${EXTRAS}" \
    && if echo ",${EXTRAS}," | grep -q ",omnivoice,"; then \
        WANT_OMNIVOICE="1"; \
        # Install the omnivoice package separately, without its dependencies:
        # it requires gradio, librosa, webdataset and tensorboardx for its demo
        # and training paths, which this backend never imports (42 packages,
        # ~600 MB). The omnivoice-deps extra pins what is actually needed.
        INSTALL_EXTRAS="$(echo "${EXTRAS}" | sed 's/\bomnivoice\b/omnivoice-deps/')"; \
    fi \
    \
    # Install CPU-only torch up front, but only when omnivoice is in play: as an
    # --extra-index-url the CPU index was merely merged with PyPI, so pip
    # resolved the default wheels and ~2.7 GB of unused CUDA libs. --index-url
    # is what actually pins it to the CPU builds. Piper needs no torch at all --
    # not even for zh, since 1.6.1 trimmed that extra -- so the default image
    # skips this. Keyed off the post-sed extras so that passing "omnivoice-deps"
    # directly is covered too, not just "omnivoice".
    && if echo ",${INSTALL_EXTRAS}," | grep -q ",omnivoice-deps,"; then \
        .venv/bin/pip3 install --no-cache-dir \
            --index-url https://download.pytorch.org/whl/cpu \
            torch torchaudio; \
    fi \
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

# The server only starts listening once the backend is loaded, which means
# downloading a model on first run -- hence the long start period, during which
# failures don't count against --retries. --retries covers the other direction:
# synthesis runs on the event loop, so a check can time out behind a long
# request without the server being unhealthy.
HEALTHCHECK --interval=30s --timeout=20s --start-period=5m --retries=3 \
    CMD ["/usr/src/.venv/bin/python3", "-m", "wyoming_piper.health_check"]

ENTRYPOINT ["bash", "docker_run.sh"]
