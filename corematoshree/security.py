"""Security helpers: database-backed throttling and structured audit events.

The rate-limit table stores keyed hashes, not raw IP addresses or usernames.
This keeps limits shared between application workers without requiring Redis.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import ipaddress
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def client_ip(request) -> str:
    """Return the peer IP. Only trust X-Forwarded-For when explicitly enabled."""
    candidate = request.META.get("REMOTE_ADDR") or ""
    if getattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


def audit_event(request, action: str, *, actor=None, model_name: str = "", object_id: str = "", details=None) -> None:
    """Write an audit row without ever recording submitted passwords/tokens."""
    from .models import AuditLog

    remote = client_ip(request)
    try:
        AuditLog.objects.create(
            actor=actor if actor is not None else (
                request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            ),
            action=action[:100],
            model_name=model_name[:100],
            object_id=str(object_id or "")[:100],
            details=details or {},
            ip_address=remote if remote != "unknown" else None,
        )
    except Exception:
        # Security telemetry must not leak credentials or take down an ordinary page.
        logger.exception("Could not persist audit event: %s", action)


def _fingerprint(scope: str, value: str) -> str:
    secret = str(settings.SECRET_KEY).encode("utf-8")
    raw = f"{scope}:{value}".encode("utf-8", errors="ignore")
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()


def _consume_limits(keys: list[str], *, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Atomically check/increment all relevant fixed-window counters."""
    from .models import RateLimitBucket

    now = timezone.now()
    window = timedelta(seconds=window_seconds)
    try:
        with transaction.atomic():
            for key in keys:
                try:
                    RateLimitBucket.objects.get_or_create(
                        key=key, defaults={"window_started": now, "count": 0}
                    )
                except IntegrityError:
                    # Concurrent first requests may race on the unique key.
                    pass
            buckets = list(
                RateLimitBucket.objects.select_for_update().filter(key__in=keys).order_by("key")
            )
            blocked = False
            retry_after = 1
            for bucket in buckets:
                if now - bucket.window_started >= window:
                    bucket.window_started = now
                    bucket.count = 0
                if bucket.count >= limit:
                    blocked = True
                    remaining = window - (now - bucket.window_started)
                    retry_after = max(retry_after, int(remaining.total_seconds()) + 1)
            if blocked:
                return True, retry_after
            for bucket in buckets:
                bucket.count += 1
                bucket.save(update_fields=["count", "window_started", "updated_at"])
        # Opportunistically keep the security table compact without a scheduler.
        if secrets.randbelow(100) == 0:
            RateLimitBucket.objects.filter(window_started__lt=now - timedelta(days=2)).delete()
        return False, 0
    except DatabaseError:
        logger.exception("Rate-limit storage is unavailable; rejecting protected request safely")
        raise


def rate_limit(scope: str, *, limit: int = 10, window_seconds: int = 900, identity_fields=(), methods=None):
    """Limit requests by peer IP and optionally by submitted account identifier."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if methods is not None and request.method not in methods:
                return view_func(request, *args, **kwargs)
            ip = client_ip(request)
            keys = [_fingerprint(f"{scope}:ip", ip)]
            if request.method in {"POST", "PUT", "PATCH"}:
                for field in identity_fields:
                    value = (request.POST.get(field) or "").strip().casefold()
                    if value:
                        keys.append(_fingerprint(f"{scope}:{field}", value[:254]))
            try:
                blocked, retry_after = _consume_limits(keys, limit=limit, window_seconds=window_seconds)
            except DatabaseError:
                response = HttpResponse("Security throttling is temporarily unavailable. Please retry shortly.", status=503)
                response["Cache-Control"] = "no-store"
                return response
            if blocked:
                audit_event(request, "rate_limit_blocked", details={"scope": scope})
                response = HttpResponse("Too many attempts. Please wait and try again.", status=429)
                response["Retry-After"] = str(retry_after)
                response["Cache-Control"] = "no-store"
                return response
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
