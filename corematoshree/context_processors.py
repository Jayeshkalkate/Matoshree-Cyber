import json

from django.conf import settings
from django.templatetags.static import static

from .models import BusinessInfo
from .utils import get_payment_settings

# Pages that must never be indexed (private, transactional, auth or admin).
NOINDEX_PREFIXES = (
    "/admin", "/admin-dashboard", "/superadmin-dashboard", "/dashboard-section", "/reports",
    "/profile", "/my-applications", "/application", "/notifications", "/payment-",
    "/create-razorpay-order", "/razorpay-webhook", "/download-receipt", "/document/",
    "/split-pdf", "/mark-payment-done", "/login", "/register", "/logout", "/auth/",
    "/password-", "/track-application", "/apply/", "/i18n",
)


def business_info(request):
    try:
        info = BusinessInfo.objects.first()
    except Exception:
        info = None
    return {'business': info, 'business_info': info}


def payment_settings(request):
    return {'payment_settings': get_payment_settings()}


def seo(request):
    """Canonical URL (no query string), social image, noindex flag and JSON-LD."""
    try:
        info = BusinessInfo.objects.first()
    except Exception:
        info = None

    canonical = request.build_absolute_uri(request.path)
    path = request.path
    noindex = path.startswith(NOINDEX_PREFIXES)

    image = ""
    try:
        if info and info.logo:
            image = request.build_absolute_uri(info.logo.url)
    except Exception:
        image = ""
    if not image:
        image = request.build_absolute_uri(static("images/matoshreelogo.png"))

    name = (info.business_name if info else "") or "Matoshree Cyber Center"
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "url": request.build_absolute_uri("/"),
        "image": image,
    }
    if info:
        if info.address:
            data["address"] = str(info.address).strip()
        if info.phone:
            data["telephone"] = str(info.phone)
        if info.email:
            data["email"] = str(info.email)
        if getattr(info, "business_hours", ""):
            data["openingHours"] = str(info.business_hours).strip()
    # Only emit a rating when real approved reviews exist (empty values are invalid markup).
    try:
        from django.db.models import Avg, Count
        from .models import Review
        agg = Review.objects.filter(approved=True).aggregate(avg=Avg("rating"), n=Count("id"))
        if agg["n"]:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(float(agg["avg"]), 1),
                "reviewCount": agg["n"],
            }
    except Exception:
        pass

    return {"seo": {
        "canonical": canonical,
        "noindex": noindex,
        "image": image,
        "site_name": name,
        # "</" is escaped so the JSON can never close the <script> tag early.
        "jsonld": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
    }}
