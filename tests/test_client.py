import json
from unittest.mock import MagicMock

import pytest
import requests

from client.python_logger import TelemetryLogger, demo


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_file_only_demo(tmp_path, monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(requests, "post", post)
    path = tmp_path / "events.jsonl"
    logger = TelemetryLogger("p1", send_http=False, output=path, session_id="s1")
    demo(logger)
    events = read_events(path)
    assert len(events) == 5
    assert {event["session_id"] for event in events} == {"s1"}
    assert {event["player_id"] for event in events} == {"p1"}
    assert events[-1]["ts"] - events[0]["ts"] == 300
    assert logger.buffer == []
    logger.flush()
    assert len(read_events(path)) == 5
    post.assert_not_called()


def test_automatic_batch_and_confirmation(tmp_path, monkeypatch):
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"accepted": 2}'
    response._content_consumed = True
    post = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
    path = tmp_path / "events.jsonl"
    logger = TelemetryLogger("p1", batch_size=2, output=path, server_url="http://test/events")
    logger.log("session_start", level="L1", ts=0)
    assert len(read_events(path)) == 1
    post.assert_not_called()
    logger.log("session_end", level="L1", ts=60, reason="quit")
    sent = post.call_args.kwargs["json"]
    assert sent == read_events(path)
    assert post.call_args.args == ("http://test/events",)
    assert post.call_args.kwargs["timeout"] == 5
    assert post.call_args.kwargs["allow_redirects"] is False
    assert logger.buffer == []
    logger.flush()
    post.assert_called_once()


@pytest.mark.parametrize("failure", ["timeout", "422", "503", "redirect", "wrong_count", "invalid_json"])
def test_failed_delivery_preserves_events_and_blocks_retry(tmp_path, monkeypatch, failure):
    response = requests.Response()
    response.status_code = {"422": 422, "503": 503, "redirect": 307}.get(failure, 201)
    response._content = b'not JSON' if failure == "invalid_json" else b'{"accepted": 0}'
    response._content_consumed = True
    post = MagicMock(return_value=response)
    if failure == "timeout":
        post.side_effect = requests.Timeout("timeout")
    monkeypatch.setattr(requests, "post", post)
    path = tmp_path / "events.jsonl"
    logger = TelemetryLogger("p1", batch_size=1, output=path)
    with pytest.raises(RuntimeError, match="Отправка не подтверждена"):
        logger.log("session_start", level="L1", ts=0)
    assert logger.buffer == read_events(path)
    assert len(logger.buffer) == 1
    with pytest.raises(RuntimeError):
        logger.flush()
    with pytest.raises(RuntimeError):
        logger.log("session_end", level="L1", ts=60)
    assert len(read_events(path)) == 1
    post.assert_called_once()


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5])
def test_invalid_batch_size(tmp_path, batch_size):
    with pytest.raises(ValueError):
        TelemetryLogger("p1", batch_size=batch_size, output=tmp_path / "events.jsonl")


def test_unknown_type_and_reserved_fields(tmp_path):
    path = tmp_path / "events.jsonl"
    logger = TelemetryLogger("p1", send_http=False, output=path)
    with pytest.raises(ValueError):
        logger.log("unknown", level="L1")
    with pytest.raises(ValueError):
        logger.log("session_start", level="L1", session_id="another_session")
    with pytest.raises(ValueError):
        logger.log("death", level="L1", x=float("nan"), y=0)
    assert not path.exists()


def test_file_error_does_not_send_http(tmp_path, monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(requests, "post", post)
    logger = TelemetryLogger("p1", batch_size=1, output=tmp_path)
    with pytest.raises(OSError):
        logger.log("session_start", level="L1")
    assert logger.buffer == []
    post.assert_not_called()
