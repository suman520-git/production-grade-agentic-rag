import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


request = Request(
    "http://127.0.0.1:8000/ready",
    headers={
        "X-API-Key": os.environ["APP_API_KEY"]
    },
)

try:
    with urlopen(request, timeout=12) as response:
        sys.exit(0 if response.status == 200 else 1)

except (HTTPError, URLError, TimeoutError):
    sys.exit(1)