from scheduler import parse_user_ids


def test_parse_user_ids() -> None:
    assert parse_user_ids("1,2, 3") == [1, 2, 3]
    assert parse_user_ids("") == []
