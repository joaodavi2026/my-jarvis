from __future__ import annotations

from pathlib import Path

from jarvis_show.orchestrator import Actions, Orchestrator

URL = "http://127.0.0.1:8000"
OLLAMA = "http://127.0.0.1:11434"
OLLAMA_PING = OLLAMA + "/api/version"


class Fake:
    def __init__(self, up=None, comes_up=None, jingle_error=False, browser_opens=True):
        self.browser_opens = browser_opens
        self.calls = []
        self.up = set(up or [])
        self.comes_up = comes_up or {}  # url -> polls before it answers once started
        self.polls = {}
        self.clock = 0.0
        self.jingle_error = jingle_error

    def actions(self) -> Actions:
        def play(path):
            self.calls.append("jingle")
            if self.jingle_error:
                raise RuntimeError("no audio device")

        def http_ok(url):
            if url in self.up:
                return True
            if url in self.comes_up:
                self.polls[url] = self.polls.get(url, 0) + 1
                return self.polls[url] > self.comes_up[url]
            return False

        def open_browser(url):
            self.calls.append("browser")
            return self.browser_opens

        def advance(seconds):
            self.clock += seconds

        return Actions(
            play_jingle=play,
            http_ok=http_ok,
            start_ollama=lambda: self.calls.append("start_ollama"),
            start_server=lambda: self.calls.append("start_server"),
            open_browser=open_browser,
            start_voice_chat=lambda: self.calls.append("voice_chat"),
            sleep=advance,
            now=lambda: self.clock,
        )


def make(fake, jingle=Path("jingle.mp3"), **kw) -> Orchestrator:
    return Orchestrator(jingle, URL, OLLAMA, fake.actions(), **kw)


def test_everything_already_running_runs_the_full_sequence_in_order():
    fake = Fake(up={OLLAMA_PING, URL})
    steps = make(fake).activate()
    assert steps == ["jingle", "ollama_ok", "server_ok", "browser", "voice_chat"]
    assert fake.calls == ["jingle", "browser", "voice_chat"]


def test_starts_missing_services_and_waits_for_them():
    fake = Fake(up={OLLAMA_PING}, comes_up={URL: 3})
    steps = make(fake).activate()
    assert "start_server" in fake.calls and "start_ollama" not in fake.calls
    assert steps[-3:] == ["server_ok", "browser", "voice_chat"]


def test_no_jingle_is_not_an_error():
    fake = Fake(up={OLLAMA_PING, URL})
    steps = make(fake, jingle=None).activate()
    assert steps[0] == "no_jingle" and steps[-1] == "voice_chat"


def test_failing_jingle_does_not_stop_the_sequence():
    fake = Fake(up={OLLAMA_PING, URL}, jingle_error=True)
    steps = make(fake).activate()
    assert steps[0] == "jingle_failed" and steps[-1] == "voice_chat"


def test_ollama_that_never_comes_up_stops_before_the_voice_chat():
    fake = Fake(up={URL})
    steps = make(fake, wait_s=3).activate()
    assert steps[-1] == "ollama_unavailable"
    assert "voice_chat" not in fake.calls and "start_ollama" in fake.calls


def test_server_that_never_comes_up_still_starts_the_voice_chat_without_browser():
    fake = Fake(up={OLLAMA_PING})
    steps = make(fake, wait_s=2).activate()
    assert "server_unavailable" in steps and "browser" not in steps and steps[-1] == "voice_chat"


def test_browser_is_opened_once_even_if_activated_repeatedly():
    fake = Fake(up={OLLAMA_PING, URL})
    orch = make(fake)
    orch.activate()
    fake.clock += 10
    orch.activate()
    assert fake.calls.count("browser") == 1
    fake.clock += 500
    orch.activate()
    assert fake.calls.count("browser") == 2


def test_no_browser_option():
    fake = Fake(up={OLLAMA_PING, URL})
    steps = make(fake, open_browser=False).activate()
    assert "browser" not in steps


def test_browser_that_was_recently_opened_by_another_run_is_reported_as_skipped():
    fake = Fake(up={OLLAMA_PING, URL}, browser_opens=False)
    steps = make(fake).activate()
    assert "browser_skipped" in steps and "browser" not in steps


def test_normal_mode_has_no_voice_chat_step():
    fake = Fake(up={OLLAMA_PING, URL})
    actions = fake.actions()
    actions.start_voice_chat = None
    steps = Orchestrator(None, URL, OLLAMA, actions).activate()
    assert "voice_chat" not in steps and steps[-1] == "browser"
