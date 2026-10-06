"""统一请求：超时 15s、指数退避重试（最多 3 次）、按 host 限速。"""
from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

TIMEOUT = 15
RETRIES = 3
UA = {"User-Agent": "alpha-perp-monitor/0.1 (+screening)"}

# host 子串 → 两次请求最小间隔（秒）
MIN_INTERVAL = {"coingecko": 6.0, "dexscreener": 0.25, "binance": 0.05}
_last_call = {}  # type: dict


class HttpError(Exception):
    def __init__(self, url, status=None, msg=""):
        self.url, self.status = url, status
        super().__init__("HTTP %s %s %s" % (status, url, msg))


def _throttle(url):
    host = urlparse(url).netloc
    for key, gap in MIN_INTERVAL.items():
        if key in host:
            wait = _last_call.get(key, 0) + gap - time.time()
            if wait > 0:
                time.sleep(wait)
            _last_call[key] = time.time()
            return


def get_json(url, params=None):
    last = None
    for attempt in range(RETRIES):
        _throttle(url)
        try:
            r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            last = HttpError(url, r.status_code, r.text[:120])
            if r.status_code in (400, 401, 403, 404, 451):  # 重试无意义
                raise last
        except HttpError:
            raise
        except (requests.RequestException, ValueError) as e:
            last = HttpError(url, None, repr(e))
        time.sleep(2 ** attempt * (3 if getattr(last, "status", None) == 429 else 1))
    raise last
