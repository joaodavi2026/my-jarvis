"""Visible console output for jarvis-show: everything the user needs to SEE that it is listening."""

from __future__ import annotations

import queue
import time
from collections import deque

import numpy as np

from .clap import BLOCK, SAMPLE_RATE, ClapActivation, ClapConfig, ClapDetector


def say(message: str) -> None:
    print(message, flush=True)


def describe_device(sd, device: int | None) -> dict:
    """Facts about the input device that is really going to be opened."""
    default_in = sd.default.device[0]
    index = default_in if device is None else device
    info = sd.query_devices(index)
    return {
        "index": index,
        "name": info["name"],
        "hostapi": sd.query_hostapis(info["hostapi"])["name"],
        "channels": info["max_input_channels"],
        "native_rate": int(info["default_samplerate"]),
        "is_default": device is None or device == default_in,
        "default_index": default_in,
    }


def print_device_table(sd) -> None:
    say("[JARVIS] dispositivos de ENTRADA (indice | nome | api | canais | taxa nativa):")
    default_in = sd.default.device[0]
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            mark = "  <-- padrao do Windows" if i == default_in else ""
            api = sd.query_hostapis(d["hostapi"])["name"]
            say("  [%3d] %-46s | %-18s | %d ch | %d Hz%s" % (i, d["name"][:46], api, d["max_input_channels"], d["default_samplerate"], mark))


def announce_device(sd, device: int | None) -> dict:
    d = describe_device(sd, device)
    origin = "padrao do Windows" if d["is_default"] else "escolhido por JARVIS_MIC"
    say("[JARVIS] microfone: [%d] %s | %s | %d canais | taxa nativa %d Hz (%s)" % (d["index"], d["name"], d["hostapi"], d["channels"], d["native_rate"], origin))
    say("[JARVIS] abrindo em %d Hz mono (sem gravar nada em disco)" % SAMPLE_RATE)
    return d


class AudioFeed:
    """Opens the microphone and yields blocks of BLOCK samples. Raises a clear error if the device cannot be opened."""

    def __init__(self, sd, device: int | None) -> None:
        self.blocks: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=400)
        self.dropped = 0
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK, dtype="float32",
                                     device=device, callback=self._callback)

    def _callback(self, indata, frames, time_info, status) -> None:
        try:
            self.blocks.put_nowait(np.array(indata[:, 0], copy=True))
        except queue.Full:
            self.dropped += 1

    def __enter__(self) -> "AudioFeed":
        self.stream.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stream.stop()
        self.stream.close()

    def get(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self.blocks.get(timeout=timeout)
        except queue.Empty:
            return None


def bar(value: float, full_scale: float = 0.5, width: int = 30) -> str:
    n = int(min(1.0, value / full_scale) * width)
    return "#" * n + "." * (width - n)


def monitor(feed: AudioFeed, seconds: float | None = None) -> None:
    """--monitor: shows peak and rms several times per second so you can SEE the microphone reacting."""
    say("[JARVIS] MONITOR: bata palmas, fale, faça barulho. O pico deve subir. Ctrl+C para sair.")
    window, last, t0 = [], time.time(), time.time()
    top = 0.0
    while seconds is None or time.time() - t0 < seconds:
        block = feed.get()
        if block is None:
            say("[JARVIS] AVISO: nenhum audio chegando do microfone (1 s sem dados)")
            continue
        window.append(block)
        if time.time() - last >= 0.2:
            x = np.concatenate(window)
            window = []
            last = time.time()
            peak = float(np.max(np.abs(x)))
            rms = float(np.sqrt(np.mean(x * x)))
            top = max(top, peak)
            say("peak=%.4f  rms=%.4f  |%s|  max=%.4f" % (peak, rms, bar(peak), top))


def calibrate(feed: AudioFeed, sd, config: ClapConfig) -> float | None:
    """--calibrate: measure the room, ask for ONE clap, measure it, suggest JARVIS_CLAP_THRESH."""
    say("[CALIBRAR] 1/3 medindo ruido ambiente por 3 s. Fique em silencio...")
    levels = []
    t0 = time.time()
    while time.time() - t0 < 3.0:
        b = feed.get()
        if b is not None:
            levels.append(float(np.sqrt(np.mean(b * b))))
    noise = float(np.median(levels)) if levels else 0.0
    say("[CALIBRAR] ruido ambiente (rms mediano) = %.5f" % noise)
    say("")
    say("AÇÃO NECESSÁRIA: BATA UMA PALMA AGORA (esperando por ate 15 s)...")
    say("")
    best, t0, floor = 0.0, time.time(), max(noise * 6.0, 0.02)
    heard_at = None
    while time.time() - t0 < 15.0:
        b = feed.get()
        if b is None:
            continue
        peak = float(np.max(np.abs(b)))
        if peak >= floor and heard_at is None:
            heard_at = time.time()
        best = max(best, peak)
        if heard_at is not None and time.time() - heard_at > 0.6:
            break
    if heard_at is None:
        say("[CALIBRAR] nenhuma palma ouvida (pico maximo %.4f, minimo esperado %.4f)." % (best, floor))
        say("[CALIBRAR] confira o microfone com: jarvis-show.cmd --monitor")
        return None
    say("[CALIBRAR] pico da palma = %.4f (%.0fx o ruido ambiente)" % (best, best / max(noise, 1e-5)))
    suggested = round(max(2.0, min(60.0, 0.5 * best / max(noise, 1e-5))), 1)
    required = max(config.min_peak, suggested * max(noise, 1e-5))
    say("[CALIBRAR] JARVIS_CLAP_THRESH recomendado = %.1f  (pico minimo aceito %.4f, a sua palma tem %.4f)" % (suggested, required, best))
    if best < config.min_peak * 1.5:
        say("[CALIBRAR] ATENCAO: sua palma foi fraca (< %.3f). Bata mais perto do microfone ou mais forte." % (config.min_peak * 1.5))
    say("[CALIBRAR] para usar:  set JARVIS_CLAP_THRESH=%.1f   (so esta janela)   |   setx JARVIS_CLAP_THRESH %.1f   (permanente)" % (suggested, suggested))
    return suggested
