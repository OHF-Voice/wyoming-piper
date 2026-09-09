"""Wyoming server for piper."""

import os
from importlib.metadata import version

# onnxruntime 1.29.0 added telemetry on non-Windows platforms: the 1DS provider
# uploads trace events to Microsoft over HTTPS, on by default in the official
# wheels that piper-tts and the omnivoice backend pull in. Opt out before
# anything imports onnxruntime -- the provider latches this at initialization,
# so it has to be set first. setdefault, so an explicit
# ORT_DISABLE_TELEMETRY=0 in the environment still wins.
# https://github.com/OHF-Voice/wyoming-piper/issues/64
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

__version__ = version("wyoming_piper")

__all__ = ["__version__"]
