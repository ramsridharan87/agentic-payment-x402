import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_security)) -> None:
    """Gate every route behind TRIGGER_API_KEY - this dashboard can trigger
    real payments, so it can't be left open on a public host.

    Fails closed: TRIGGER_API_KEY is required, not optional. A clonable,
    potentially-public repo shouldn't have a mode where forgetting to set
    one env var silently exposes a live payment-triggering dashboard.
    """
    expected = os.environ.get("TRIGGER_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "TRIGGER_API_KEY is not set. Refusing to serve an unauthenticated "
                "dashboard that can trigger real payments - set TRIGGER_API_KEY "
                "in your environment before running this."
            ),
        )

    valid = credentials is not None and secrets.compare_digest(
        credentials.password, expected
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
