# Wyoming Piper

[Wyoming protocol](https://github.com/rhasspy/wyoming) server for the [Piper](https://github.com/rhasspy/piper/) text to speech system.

## Home Assistant Add-on

[![Show add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=core_piper)

[Source](https://github.com/home-assistant/addons/tree/master/piper)

## Local Install

Requires Python 3.10 or later.

Clone the repository and set up Python virtual environment:

``` sh
git clone https://github.com/rhasspy/wyoming-piper.git
cd wyoming-piper
script/setup
```

Run a Wyoming server that Home Assistant can connect to:

``` sh
script/run --voice en_US-lessac-medium --uri 'tcp://0.0.0.0:10200' --data-dir /data --download-dir /data 
```

For a demo web server, make sure to install the `http` dependencies first:

``` sh
script/setup --http
```

Then run in a separate terminal:

``` sh
script/run_http --uri 'tcp://localhost:10200'
```

and visit http://localhost:5000 to test.

## OmniVoice backend (experimental)

An alternative [OmniVoice](https://github.com/k2-fsa/OmniVoice) backend is
available, running a block-wise int4 ONNX export under `onnxruntime`. Install the
extra dependencies and select it with `--backend omnivoice`:

``` sh
script/setup --omnivoice
script/run --backend omnivoice \
    --uri 'tcp://0.0.0.0:10200' --data-dir /data --download-dir /data \
    --omnivoice-ref-dir /data/omnivoice_voices --omnivoice-steps 32
```

**Voices.** Point `--omnivoice-ref-dir` at a directory of voices organized as
`<language>/<voice_name>/`, for example:

```
omnivoice_voices/
  en_US/
    lessac/{ref.wav, ref.txt}
    ryan/{ref.wav, ref.txt}
    narrator/{instruct.txt}
  de_DE/
    thorsten/{ref.wav, ref.txt}
```

Each voice directory is one of two kinds:

- **Cloning** — `ref.wav` + `ref.txt` (the transcript of the recording); the
  voice is cloned from the reference audio.
- **Voice design** — `instruct.txt`; its text is a style instruction (e.g.
  `male, deep, slow`) describing the voice to generate, with no reference audio.
  See [voice design](https://github.com/k2-fsa/OmniVoice/blob/master/docs/voice-design.md) for valid attributes.
  Only used when the directory has no `ref.wav`/`ref.txt`.

A `default` voice is also advertised; requesting it (or an empty/unknown voice
name) uses OmniVoice's built-in speaker for the requested language.

OmniVoice lists 646 language codes, most of them ISO 639-3 only. Advertising all
of them buries the usable ones in Home Assistant's language picker, so `default`
is advertised for the ~128 that have an ISO 639-1 (two-letter) tag, plus
Cantonese, Standard Arabic and Odia. This limits only what is *advertised* —
`--omnivoice-language` and a per-request language still accept any code
OmniVoice knows, so the rest stay reachable.

On first use, each reference is encoded and cached next to `ref.wav` as
`ref.rvq` (regenerated whenever `ref.wav` is newer), so the reference isn't
re-encoded on every request.

The model is a block-wise int4 ONNX graph (see `script/quantize_omnivoice.py` to
reproduce it). If `omnivoice.int4.onnx` (and its `.data`) are found in a
`--data-dir`, that copy is used; otherwise it is downloaded into `--download-dir`
(used as the HuggingFace cache) from the repo set by `--omnivoice-onnx-repo`. Use
`--local-files-only` to run fully offline once the model is cached, and
`--omnivoice-steps` to trade quality for speed — int4 stays clean down to ~10
steps. OmniVoice is compute-heavy and best suited to a desktop/server CPU rather
than low-power devices.

## Voice management web UI

A small Flask web UI can run alongside the Wyoming server to manage custom
voices. It is designed to work as a Home Assistant add-on behind ingress.
Install the extra dependency and enable it with `--web-server`:

``` sh
script/setup --web
script/run --voice en_US-lessac-medium \
    --uri 'tcp://0.0.0.0:10200' --data-dir /data --download-dir /data \
    --web-server --web-server-port 5000
```

Then visit http://localhost:5000. The page has two sections:

- **Piper** — upload and delete custom voices (a `<voice>.onnx` model plus its
  `<voice>.onnx.json` config) stored in `--download-dir`. Some metadata (dataset,
  language, quality, sample rate) is read from each config file.
- **OmniVoice** — upload cloned voices (a reference WAV plus its required
  transcript) into `--omnivoice-ref-dir/<language>/<voice_name>/`, and delete a
  cloned voice's whole directory.

Each section shows a warning when its backend is not the one the server was
started with (via `--backend`), but the UI keeps working. The server picks up
added and removed voices on its own — no restart — but Home Assistant caches the
voice list, so **reload the Piper integration** for a new voice to appear in it.

`--web-server-host` / `--web-server-port` set the bind address (default
`127.0.0.1:5000`). The UI has no authentication and can upload and delete files
under `--download-dir` / `--omnivoice-ref-dir`, so only bind it to an address
reachable from a network you trust.

## Docker Image

``` sh
docker run -it \
    -p 10200:10200 \
    -v /path/to/local/data:/data \
    rhasspy/wyoming-piper \
    --voice en_US-lessac-medium
```

OmniVoice ships as a separate `omnivoice` tag, because it pulls in torch and
transformers. It is built for `linux/amd64` only — OmniVoice needs a
desktop/server CPU:

``` sh
docker run -it \
    -p 10200:10200 \
    -v /path/to/local/data:/data \
    rhasspy/wyoming-piper:omnivoice \
    --backend omnivoice \
    --omnivoice-ref-dir /data/cloned-voices \
    --omnivoice-steps 10  # higher = better quality but slower
```

The voice management web UI is **off by default**. It has no authentication, so
only enable it on a network you trust:

``` sh
docker run -it \
    -p 10200:10200 -p 5000:5000 \
    -v /path/to/local/data:/data \
    rhasspy/wyoming-piper \
    --voice en_US-lessac-medium \
    --web-server --web-server-host 0.0.0.0
```

[Source](https://github.com/rhasspy/wyoming-addons/tree/master/piper)
