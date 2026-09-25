"""Polling retry and redacted thread exception output."""

import threading

import main
from core import logger as app_logger

TOKEN = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # pragma: allowlist secret


def test_run_polling_retries_after_crash_without_skipping_pending(monkeypatch):
    # Regresyon: skip_pending sırasındaki ağ hatası polling thread'ini öldürüyordu;
    # bot ana döngünün bir sonraki turuna (~5 dk) kadar yanıt vermiyordu.
    calls = []

    class _FakeBot:
        def infinity_polling(self, **kwargs):
            calls.append(kwargs["skip_pending"])
            if len(calls) == 1:
                raise ConnectionError("network down")

    monkeypatch.setattr(main, "bot", _FakeBot())
    monkeypatch.setattr(main.SHUTDOWN_EVENT, "wait", lambda _t: None)

    main._run_polling()

    assert calls == [True, False]


def test_thread_excepthook_redacts_token(capsys, monkeypatch):
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    app_logger.install_thread_excepthook()

    def boom():
        raise RuntimeError(f"url: /bot{TOKEN}/getUpdates")

    t = threading.Thread(target=boom, name="leaky")
    t.start()
    t.join()

    err = capsys.readouterr().err
    assert "Exception in thread leaky" in err
    assert TOKEN not in err
    assert "[REDACTED]" in err
