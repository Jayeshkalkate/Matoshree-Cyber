"""Password login/logout auditing and Google OAuth 2.0 (OIDC userinfo) flows."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from .models import SocialIdentity, User
from .security import audit_event, rate_limit

logger = logging.getLogger(__name__)


class AuditedLoginView(LoginView):
    """Django's standard password authentication with audit and session expiry."""

    template_name = "login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("remember"):
            self.request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 14))
        else:
            self.request.session.set_expiry(0)
        audit_event(self.request, "login_success", actor=form.get_user(), details={"method": "password"})
        return response

    def form_invalid(self, form):
        identifier = (self.request.POST.get("username") or "").strip()[:150]
        audit_event(self.request, "login_failed", details={"method": "password", "identifier": identifier})
        return super().form_invalid(form)


class AuditedLogoutView(LogoutView):
    """Require the framework's normal POST/CSRF-protected logout behavior."""

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            audit_event(request, "logout", actor=request.user, details={"method": "password_or_google"})
        return super().post(request, *args, **kwargs)


def _google_credentials():
    return (
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""),
        getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", ""),
    )


def _safe_next(request, candidate):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("home")


def _username_for_email(email: str) -> str:
    base = slugify(email.split("@", 1)[0])[:130] or "google-user"
    username = base
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base[:115]}-{secrets.token_hex(4)}"
    return username


@rate_limit("google-oauth-start", limit=20, window_seconds=300)
@require_GET
def google_oauth_start(request):
    client_id, client_secret = _google_credentials()
    if not client_id or not client_secret:
        messages.info(
            request,
            "Google sign-in is not configured yet. You can still sign in with your username and password.",
        )
        return redirect("login")

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")

    # Preserve several parallel login tabs, use each state only once, and never put
    # state/verifier in a query string or log.
    flows = request.session.get("google_oauth_flows", {})
    flows[state] = {
        "verifier": verifier,
        "link_user_id": request.user.pk if request.user.is_authenticated else None,
        "next": request.GET.get("next", ""),
    }
    request.session["google_oauth_flows"] = dict(list(flows.items())[-5:])

    redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or request.build_absolute_uri(
        reverse("google_oauth_callback")
    )
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return HttpResponseRedirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@rate_limit("google-oauth-callback", limit=20, window_seconds=300)
@require_GET
def google_oauth_callback(request):
    state = request.GET.get("state", "")
    flows = request.session.get("google_oauth_flows", {})
    flow = flows.pop(state, None) if state else None
    request.session["google_oauth_flows"] = flows
    if not flow:
        audit_event(request, "oauth_state_rejected", details={"provider": "google"})
        messages.error(request, "Google sign-in could not be verified. Please start again.")
        return redirect("login")

    if request.GET.get("error"):
        messages.info(request, "Google sign-in was cancelled or declined.")
        return redirect("login")

    code = request.GET.get("code", "")
    if not code:
        messages.error(request, "Google did not return an authorization code. Please try again.")
        return redirect("login")

    client_id, client_secret = _google_credentials()
    if not client_id or not client_secret:
        messages.error(request, "Google sign-in is not configured. Use username and password instead.")
        return redirect("login")

    redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or request.build_absolute_uri(
        reverse("google_oauth_callback")
    )
    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": flow["verifier"],
            },
            timeout=(3.05, 10),
        )
        token_response.raise_for_status()
        token = token_response.json()
        if not isinstance(token, dict):
            raise ValueError("Google token response was not a JSON object")
        access_token = token.get("access_token")
        if not access_token or str(token.get("token_type", "Bearer")).casefold() != "bearer":
            raise ValueError("Google token response did not contain a bearer access token")
        userinfo_response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=(3.05, 10),
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
        if not isinstance(userinfo, dict):
            raise ValueError("Google userinfo response was not a JSON object")
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Google OAuth exchange failed (%s)", type(exc).__name__)
        audit_event(request, "oauth_exchange_failed", details={"provider": "google"})
        messages.error(request, "Google sign-in could not be completed. Please try again.")
        return redirect("login")

    subject = str(userinfo.get("sub", ""))
    email = str(userinfo.get("email", "")).strip().casefold()
    email_verified = userinfo.get("email_verified") is True or str(userinfo.get("email_verified", "")).casefold() == "true"
    if not subject or "@" not in email or not email_verified:
        audit_event(request, "oauth_profile_rejected", details={"provider": "google"})
        messages.error(request, "Google must provide a verified email address before you can sign in.")
        return redirect("login")

    existing_identity = SocialIdentity.objects.select_related("user").filter(provider="google", subject=subject).first()
    link_user_id = flow.get("link_user_id")
    if link_user_id is not None:
        if not request.user.is_authenticated or str(request.user.pk) != str(link_user_id):
            messages.error(request, "Your session changed while linking Google. Sign in and try again.")
            return redirect("login")
        user = request.user
        if existing_identity and existing_identity.user_id != user.pk:
            messages.error(request, "That Google account is already linked to another account.")
            return redirect("profile")
        email_owner = User.objects.filter(email__iexact=email).exclude(pk=user.pk).first()
        if email_owner:
            messages.error(
                request,
                "That Google email is already used by another local account. Sign in to that account before linking it.",
            )
            return redirect("profile")
        SocialIdentity.objects.update_or_create(
            provider="google", subject=subject,
            defaults={"user": user, "email": email},
        )
        audit_event(request, "oauth_identity_linked", actor=user, details={"provider": "google", "email": email})
        messages.success(request, "Google sign-in is now linked to your account.")
        return redirect(_safe_next(request, flow.get("next")) if flow.get("next") else "profile")

    if existing_identity:
        user = existing_identity.user
        if not user.is_active:
            messages.error(request, "This account is inactive. Contact the site administrator.")
            return redirect("login")
        existing_identity.email = email
        existing_identity.save(update_fields=["email", "updated_at"])
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 14))
        audit_event(request, "login_success", actor=user, details={"method": "google"})
        return redirect(_safe_next(request, flow.get("next")))

    # Never auto-link a Google identity to an existing password account merely
    # because the emails match. The owner must sign in and explicitly link it.
    if User.objects.filter(email__iexact=email).exists():
        audit_event(request, "oauth_email_collision", details={"provider": "google", "email": email})
        messages.error(
            request,
            "An account already uses this email. Sign in with that account first, then use Profile → Connect Google.",
        )
        return redirect("login")

    try:
        with transaction.atomic():
            username = _username_for_email(email)
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=str(userinfo.get("given_name", ""))[:150],
                last_name=str(userinfo.get("family_name", ""))[:150],
                password=None,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            SocialIdentity.objects.create(provider="google", subject=subject, email=email, user=user)
    except IntegrityError:
        existing_identity = SocialIdentity.objects.select_related("user").filter(provider="google", subject=subject).first()
        if not existing_identity:
            logger.exception("Google social identity could not be persisted")
            messages.error(request, "Your Google account could not be created. Please try again.")
            return redirect("login")
        user = existing_identity.user

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 14))
    audit_event(request, "registration_success", actor=user, details={"method": "google"})
    messages.success(request, "Your account is ready. Welcome!")
    return redirect(_safe_next(request, flow.get("next")))
