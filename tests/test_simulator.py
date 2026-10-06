import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pytest

from client.python_logger import simulate


def generate(path, n_sessions=20, seed=42):
    run_id = simulate(n_sessions, seed=seed, send_http=False, output=path)
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return run_id, events


@pytest.mark.parametrize("n_sessions", [20, 21, 40])
def test_complete_sessions_and_coordinates(tmp_path, n_sessions):
    _, events = generate(tmp_path / "events.jsonl", n_sessions)
    sessions = defaultdict(list)
    for event in events:
        sessions[event["session_id"]].append(event)
    assert len(sessions) == n_sessions
    assert {event["level"] for event in events} == {"L1", "L2"}
    for session in sessions.values():
        types = [event["event_type"] for event in session]
        assert types.count("session_start") == types.count("session_end") == 1
        assert types[0] == "session_start" and types[-1] == "session_end"
        assert len({event["player_id"] for event in session}) == 1
        assert [event["ts"] for event in session] == sorted(event["ts"] for event in session)
        assert 90 <= session[-1]["ts"] - session[0]["ts"] <= 420
        if "level_complete" in types:
            assert types.index("checkpoint") < types.index("level_complete")
        for event in session:
            if event["event_type"] == "death":
                assert isinstance(event["x"], float) and isinstance(event["y"], float)


def test_retention_funnel_and_clusters(tmp_path):
    _, events = generate(tmp_path / "events.jsonl")
    days = defaultdict(set)
    for event in events:
        if event["event_type"] == "session_start":
            days[event["player_id"]].add(datetime.fromtimestamp(event["ts"], timezone.utc).date())
    assert len(days) == 12
    assert sum(min(dates) + timedelta(days=1) in dates for dates in days.values()) == 4
    assert sum(min(dates) + timedelta(days=2) in dates for dates in days.values()) == 4
    assert sum(event["event_type"] == "checkpoint" for event in events) == 16
    assert sum(event["event_type"] == "level_complete" for event in events) == 8
    for level in ("L1", "L2"):
        deaths = [event for event in events if event["event_type"] == "death" and event["level"] == level]
        clustered = [event for event in deaths if event["cause"] == "spikes"]
        assert len(clustered) > len(deaths) / 2
        center_x = 12.5 if level == "L1" else 70.0
        assert all(abs(event["x"] - center_x) < 5 for event in clustered)


def test_reproducible_content_with_separate_ids(tmp_path):
    first_id, first = generate(tmp_path / "first.jsonl")
    second_id, second = generate(tmp_path / "second.jsonl")
    assert first_id != second_id
    assert {event["player_id"] for event in first}.isdisjoint(event["player_id"] for event in second)
    assert {event["session_id"] for event in first}.isdisjoint(event["session_id"] for event in second)
    for left, right in zip(first, second, strict=True):
        assert left["session_id"].removeprefix(first_id) == right["session_id"].removeprefix(second_id)
        assert left["player_id"].removeprefix(first_id) == right["player_id"].removeprefix(second_id)
        assert {key: value for key, value in left.items() if key not in {"session_id", "player_id"}} == {
            key: value for key, value in right.items() if key not in {"session_id", "player_id"}
        }
    _, other_seed = generate(tmp_path / "other.jsonl", seed=7)
    assert [event["ts"] for event in first] != [event["ts"] for event in other_seed]


@pytest.mark.parametrize("n_sessions", [0, -1, 19, True, 20.5])
def test_invalid_session_count(tmp_path, n_sessions):
    path = tmp_path / "events.jsonl"
    with pytest.raises(ValueError):
        simulate(n_sessions, send_http=False, output=path)
    assert not path.exists()
