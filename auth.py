"""Simple file-based authentication for the web interface."""

from __future__ import annotations

import json
import os
from functools import wraps
from typing import Callable, Dict, Any

from flask import redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


class Auth:
    """Manage a single username/password stored in ``credentials.json``."""

    def __init__(self, path: str = "credentials.json") -> None:
        self.path = path
        if not os.path.exists(self.path):
            self.set_password("admin", "admin")

    # ------------------------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    def verify(self, username: str, password: str) -> bool:
        data = self._read()
        stored_user = data.get("username")
        stored_hash = data.get("password_hash", "")
        return username == stored_user and check_password_hash(stored_hash, password)

    # ------------------------------------------------------------------
    def set_password(self, username: str, password: str) -> None:
        data = {"username": username, "password_hash": generate_password_hash(password)}
        with open(self.path, "w", encoding="utf8") as fh:
            json.dump(data, fh)


def login_required(fn: Callable) -> Callable:
    """Decorator to ensure a user is logged in."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not session.get("user"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper
