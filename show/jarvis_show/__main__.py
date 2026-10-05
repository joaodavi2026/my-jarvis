"""jarvis-show: listens for two claps, then starts the Jarvis voice experience. Everything stays local."""

from __future__ import annotations

import argparse
import logging
import queue
import sys

import numpy as np

from . import system
from .clap import BLOCK, SAMPLE_RATE, ClapActivation, ClapConfig, ClapDetector
from .devices import input_devices, resolve_device
from .lock import AlreadyRunning, InstanceLock
from .orchestrator import Actions, Orchestrator
from .settings import Settings

log = logging.getLogger("jarvis_show")


def build_orchestrator(s: Settings, open_browser: bool, voice: bool = True, jingle: bool = True) -> Orchestrator:
    actions = Actions(
        play_jingle=system.play_jingle,
        http_ok=system.http_ok,
        start_ollama=system.start_ollama,
        start_server=lambda: system.start_server(s.openjarvis_dir),
        open_browser=system.open_browser,
        start_voice_chat=system.start_voice_chat if voice else None,
    )
    return Orchestrator(s.jingle if jingle else None, s.url, s.ollama_url, actions, open_browser=open_browser)


def listen(s: Settings, orchestrator: Orchestrator, keep_listening: bool, calibrate: bool) -> int:
    import sounddevice as sd

    device = resolve_device(s.mic, list(sd.query_devices()))
    pipe = ClapActivation(ClapDetector(ClapConfig(thresh=s.clap_thresh)))
    blocks = queue.Queue(maxsize=200)

    def callback(indata, frames, time_info, status):  # audio thread: only copy, never block
        try:
            blocks.put_nowait(np.array(indata[:, 0], copy=True))
        except queue.Full:
            pass

    where = "default microphone" if device is None else "device %d" % device
    print("jarvis-show listening on the %s (JARVIS_CLAP_THRESH=%.1f). Clap twice. Ctrl+C to stop." % (where, s.clap_thresh))
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK, dtype="float32", device=device, callback=callback):
        try:
            while True:
                block = blocks.get()
                if calibrate:
                    if pipe.detector.process(block):
                        print("clap detected (noise floor %.4f)" % pipe.detector.noise)
                    continue
                if pipe.process(block):
                    print("double clap -> starting Jarvis")
                    steps = orchestrator.activate()
                    print("steps:", ", ".join(steps))
                    if not keep_listening:
                        return 0
        except KeyboardInterrupt:
            return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis-show", description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="show the available input devices and exit")
    parser.add_argument("--calibrate", action="store_true", help="only report detected claps, to tune JARVIS_CLAP_THRESH")
    parser.add_argument("--activate-now", action="store_true", help="skip the claps and run the activation sequence")
    parser.add_argument("--keep-listening", action="store_true", help="keep listening after an activation (default: exit)")
    parser.add_argument("--no-voice", action="store_true", help="do not start the voice chat (normal mode: services + interface only)")
    parser.add_argument("--no-jingle", action="store_true", help="do not play the jingle")
    parser.add_argument("--no-browser", action="store_true", help="do not open the web interface")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()

    if args.list_devices:
        import sounddevice as sd

        for index, name in input_devices(list(sd.query_devices())):
            print("%3d  %s" % (index, name))
        return 0
    orchestrator = build_orchestrator(settings, open_browser=not args.no_browser, voice=not args.no_voice, jingle=not args.no_jingle)
    if args.activate_now:
        print("steps:", ", ".join(orchestrator.activate()))
        return 0
    try:
        with InstanceLock():
            return listen(settings, orchestrator, args.keep_listening, args.calibrate)
    except AlreadyRunning:
        print("jarvis-show is already running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
