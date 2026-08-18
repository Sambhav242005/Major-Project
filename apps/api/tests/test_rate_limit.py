from fastapi import Request

from core.rate_limit import _rate_limit_key


def make_request(user_id=None, client_host="127.0.0.1"):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }

    request = Request(scope)
    request.state.user_id = user_id

    return request


def test_rate_limit_key_uses_user_id():
    request = make_request(user_id=101)

    assert _rate_limit_key(request) == "user:101"


def test_different_users_get_different_buckets():
    user_1 = make_request(user_id=101)
    user_2 = make_request(user_id=202)

    key_1 = _rate_limit_key(user_1)
    key_2 = _rate_limit_key(user_2)

    assert key_1 == "user:101"
    assert key_2 == "user:202"
    assert key_1 != key_2


def test_rate_limit_key_falls_back_to_ip():
    request = make_request(
        user_id=None,
        client_host="192.168.1.10",
    )

    assert _rate_limit_key(request) == "ip:192.168.1.10"
    
def test_same_user_gets_same_bucket():
    request_1 = make_request(user_id=101)
    request_2 = make_request(user_id=101)

    assert _rate_limit_key(request_1) == _rate_limit_key(request_2)
    assert _rate_limit_key(request_1) == "user:101"


def test_different_ips_get_different_buckets():
    request_1 = make_request(
        user_id=None,
        client_host="192.168.1.10",
    )
    request_2 = make_request(
        user_id=None,
        client_host="192.168.1.20",
    )

    assert _rate_limit_key(request_1) == "ip:192.168.1.10"
    assert _rate_limit_key(request_2) == "ip:192.168.1.20"
    assert _rate_limit_key(request_1) != _rate_limit_key(request_2)


def test_zero_user_id_falls_back_to_ip():
    request = make_request(
        user_id=0,
        client_host="192.168.1.10",
    )

    assert _rate_limit_key(request) == "ip:192.168.1.10"