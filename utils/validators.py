"""
RSA shared input validators.

Small, dependency-free helpers used by the web layer and the lifecycle
service so validation rules live in one place.
"""

import math
import re


class ValidationError(ValueError):
    """Raised when user input is invalid; the message is safe to show to users."""


def parse_coordinates(latitude, longitude, required=False):
    """
    Parse a latitude/longitude pair.

    Returns ``(lat, lon)`` as floats, or ``(None, None)`` when both are blank
    and ``required`` is False. A missing location is never replaced by a
    default coordinate.
    """

    blank_lat = latitude is None or str(latitude).strip() == ""
    blank_lon = longitude is None or str(longitude).strip() == ""

    if blank_lat and blank_lon:
        if required:
            raise ValidationError("Location is required.")
        return None, None

    if blank_lat or blank_lon:
        raise ValidationError("Provide both latitude and longitude, or neither.")

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise ValidationError("Location coordinates must be numbers.") from None

    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValidationError("Location coordinates are invalid.")

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValidationError("Location coordinates are outside valid ranges.")

    if lat == 0 and lon == 0:
        # "Null Island" is what broken GPS/geolocation code reports, not a real roadside.
        raise ValidationError("Location coordinates look invalid (0, 0).")

    return lat, lon


def parse_optional_float(value, name, minimum=None, maximum=None):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number.") from None
    if not math.isfinite(number):
        raise ValidationError(f"{name} is invalid.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{name} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{name} must be at most {maximum}.")
    return number


def parse_int(value, name, minimum=None, maximum=None, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{name} is required.")
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a whole number.") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"{name} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{name} must be at most {maximum}.")
    return number


def clean_text(value, name, max_length, required=False, min_length=0):
    text = "" if value is None else str(value).strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if required and not text:
        raise ValidationError(f"{name} is required.")
    if text and len(text) < min_length:
        raise ValidationError(f"{name} must be at least {min_length} characters.")
    if len(text) > max_length:
        raise ValidationError(f"{name} must be at most {max_length} characters.")
    return text


_REGISTRATION_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-]{2,18}[A-Z0-9]$")


def normalize_registration_number(value):
    """Upper-case, collapse spaces; 4-20 chars of letters, digits, spaces, hyphens."""
    text = re.sub(r"\s+", " ", str(value or "").strip().upper())
    if not _REGISTRATION_RE.match(text):
        raise ValidationError(
            "Registration number must be 4-20 characters using letters, digits, spaces or hyphens."
        )
    return text


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def validate_email(value):
    email = str(value or "").strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise ValidationError("Enter a valid email address.")
    return email


_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{6,18}[0-9]$")


def validate_phone(value, required=False):
    phone = str(value or "").strip()
    if not phone:
        if required:
            raise ValidationError("Phone number is required.")
        return None
    if not _PHONE_RE.match(phone):
        raise ValidationError("Enter a valid phone number (digits, spaces, hyphens, optional +).")
    return phone
