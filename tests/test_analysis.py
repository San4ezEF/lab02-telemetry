import pandas as pd

from analysis.analyze import completion_rate, retention, session_length


def _df():
    return pd.DataFrame([
        {"session_id": "s1", "player_id": "p1", "event_type": "session_start", "ts": 0, "x": 0, "y": 0},
        {"session_id": "s1", "player_id": "p1", "event_type": "level_complete", "ts": 60, "x": 0, "y": 0},
        {"session_id": "s2", "player_id": "p1", "event_type": "session_end", "ts": 100, "x": 0, "y": 0},
        {"session_id": "s3", "player_id": "p2", "event_type": "session_end", "ts": 100, "x": 0, "y": 0},
    ])


def test_metrics():
    df = _df()
    assert session_length(df)["s1"] == 60
    assert retention(df) == 0.5
    assert abs(completion_rate(df) - 1 / 3) < 1e-9
