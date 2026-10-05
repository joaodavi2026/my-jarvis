"""jarvis-show: listens for two claps, then starts the Jarvis voice experience. Everything stays local."""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque

from . import system
from .clap import BLOCK, SAMPLE_RATE, ClapActivation, ClapConfig, ClapDetector, DoubleClapMatcher
from .console import AudioFeed, announce_device, calibrate, monitor, print_device_table, say
from .devices import resolve_device
from .lock import AlreadyRunning, InstanceLock
from .orchestrator import Actions, Orchestrator
from .settings import Settings


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


def listen(s: Settings, device: int | None, orchestrator: Orchestrator, args, sd) -> int:
    config = ClapConfig(thresh=s.clap_thresh)
    pipe = ClapActivation(ClapDetector(config), DoubleClapMatcher())
    say("[JARVIS] threshold: %.1f (maior = menos sensivel; JARVIS_CLAP_THRESH)" % config.thresh)
    say("[JARVIS] calibrando ruido ambiente (0.5 s)...")
    recent_peaks = deque(maxlen=8)
    ready_said = False
    first_at = None
    last_status = time.time()
    window_peak = 0.0
    last_reject_print = 0.0
    with AudioFeed(sd, device) as feed:
        try:
            while True:
                block = feed.get()
                if block is None:
                    say("[JARVIS] AVISO: nenhum audio chegando do microfone (1 s sem dados)")
                    continue
                peak = float(abs(block).max())
                recent_peaks.append(peak)
                window_peak = max(window_peak, peak)
                before = len(pipe.history)
                pipe.process(block)
                now_s = pipe._blocks * BLOCK / SAMPLE_RATE
                if not ready_said and pipe.detector._seen > config.warmup_blocks:
                    ready_said = True
                    say("[JARVIS] ruido ambiente: %.4f | pico minimo para contar como palma: %.4f" % (pipe.detector.noise, pipe.detector.required_peak()))
                    say("[JARVIS] aguardando duas palmas...  (Ctrl+C para sair)")
                rejections = pipe.detector.pop_rejections()
                if not args.quiet:
                    for r in rejections:
                        if time.time() - last_reject_print > 0.25:
                            last_reject_print = time.time()
                            say("[ignorado] pico=%.3f (minimo %.3f) crest=%.1f agudos=%.2f -> %s" % (r["peak"], r["need"], r["crest"], r["hf"], r["reason"]))
                if len(pipe.history) > before:
                    m, shown = pipe.matcher, max(recent_peaks)
                    if m.last == "first":
                        first_at = now_s
                        say("[PALMA 1] detectada (pico=%.3f)" % shown)
                    elif m.last == "restart":
                        first_at = now_s
                        say("[PALMA 1] detectada (pico=%.3f) - a anterior foi ha %.0f ms, recomecando" % (shown, m.last_gap * 1000))
                    elif m.last == "fire":
                        say("[PALMA 2] detectada (pico=%.3f) - intervalo %.0f ms" % (shown, m.last_gap * 1000))
                        say("[JARVIS] ATIVADO")
                        first_at = None
                        if args.dry_run:
                            say("[JARVIS] (--dry-run: nao inicia o Jarvis; continuo ouvindo)")
                        else:
                            say("[JARVIS] iniciando: jingle, Ollama, servidor, navegador e voz...")
                            say("[JARVIS] passos: " + ", ".join(orchestrator.activate()))
                            if not args.keep_listening:
                                return 0
                    elif m.last == "same_event":
                        say("[palma ignorada] %.0f ms depois da anterior: parece eco do mesmo som (minimo 150 ms)" % (m.last_gap * 1000))
                    elif m.last == "cooldown":
                        say("[palma ignorada] cooldown apos ativacao")
                if first_at is not None and now_s - first_at > pipe.matcher.cfg.max_gap:
                    say("[JARVIS] so 1 palma na janela de %.0f ms; zerando e aguardando de novo" % (pipe.matcher.cfg.max_gap * 1000))
                    pipe.matcher.reset()
                    first_at = None
                if time.time() - last_status >= 5.0:
                    say("[JARVIS] ouvindo... ruido=%.4f  pico(ultimos 5 s)=%.3f" % (pipe.detector.noise, window_peak))
                    last_status, window_peak = time.time(), 0.0
        except KeyboardInterrupt:
            say("[JARVIS] encerrado (Ctrl+C)")
            return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="jarvis-show", description=__doc__)
    parser.add_argument("--list-devices", action="store_true", help="show the available input devices and exit")
    parser.add_argument("--monitor", action="store_true", help="show peak and rms live (no audio is stored)")
    parser.add_argument("--calibrate", action="store_true", help="measure noise, ask for ONE clap, suggest JARVIS_CLAP_THRESH")
    parser.add_argument("--dry-run", action="store_true", help="detect and show claps, but do not start Jarvis")
    parser.add_argument("--quiet", action="store_true", help="do not print ignored sounds")
    parser.add_argument("--activate-now", action="store_true", help="skip the claps and run the activation sequence")
    parser.add_argument("--keep-listening", action="store_true", help="keep listening after an activation (default: exit)")
    parser.add_argument("--no-voice", action="store_true", help="do not start the voice chat (normal mode)")
    parser.add_argument("--no-jingle", action="store_true", help="do not play the jingle")
    parser.add_argument("--no-browser", action="store_true", help="do not open the web interface")
    args = parser.parse_args(argv)

    say("[JARVIS] iniciando...")
    settings = Settings.from_env()
    orchestrator = build_orchestrator(settings, open_browser=not args.no_browser, voice=not args.no_voice, jingle=not args.no_jingle)
    if args.activate_now:
        say("[JARVIS] passos: " + ", ".join(orchestrator.activate()))
        return 0

    import sounddevice as sd

    if args.list_devices:
        print_device_table(sd)
        return 0
    try:
        device = resolve_device(settings.mic, list(sd.query_devices()))
    except ValueError as exc:
        say("[JARVIS] ERRO em JARVIS_MIC: %s. Rode: jarvis-show.cmd --list-devices" % exc)
        return 2
    announce_device(sd, device)
    try:
        with InstanceLock():
            if args.monitor:
                with AudioFeed(sd, device) as feed:
                    monitor(feed)
                return 0
            if args.calibrate:
                with AudioFeed(sd, device) as feed:
                    return 0 if calibrate(feed, sd, ClapConfig(thresh=settings.clap_thresh)) else 1
            return listen(settings, device, orchestrator, args, sd)
    except AlreadyRunning:
        say("[JARVIS] ja existe um jarvis-show rodando (so uma instancia por vez).")
        return 1
    except KeyboardInterrupt:
        say("[JARVIS] encerrado (Ctrl+C)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
