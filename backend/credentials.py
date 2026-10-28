"""Camera secrets: authenticated encryption and deliberately limited presentation."""
from urllib.parse import urlsplit, urlunsplit, unquote
from cryptography.fernet import Fernet, InvalidToken

PREFIX = 'enc:v1:'


def cipher(key=None):
    if key is None:
        from config import settings
        key = settings.CREDENTIAL_KEY
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError):
        raise ValueError('Set SAFEGUARD_CREDENTIAL_KEY to a valid Fernet key.') from None


def reveal(value, key=None):
    if not value or not value.startswith(PREFIX):
        return value
    try:
        return cipher(key).decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        raise ValueError('Camera credentials cannot be decrypted with this key.') from None


def protect(value, key=None):
    if not value:
        return value
    if value.startswith(PREFIX):
        reveal(value, key)  # Never silently accept a different/lost key.
        return value
    return PREFIX + cipher(key).encrypt(value.encode()).decode()


def public_url(value, key=None):
    url = reveal(value, key) or ''
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    # Query strings can contain access tokens. Keep them encrypted, never echoed.
    return urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, '', ''))


def protect_camera(values, key=None):
    result = dict(values)
    url = reveal(result.get('url'), key)
    if url and '://' in url:
        parts = urlsplit(url)
        if parts.username is not None:
            result['username'] = unquote(parts.username)
            result['password'] = unquote(parts.password or '')
            url = urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, parts.query, ''))
        result['url'] = protect(url, key)
    for field in ('username', 'password'):
        if field in result:
            result[field] = protect(result[field], key)
    return result


def migrate_cameras(session_factory, model, key):
    cipher(key)
    # One atomic transaction; failure leaves legacy camera values intact.
    with session_factory() as db:
        for row in db.query(model).all():
            values = protect_camera({field: getattr(row, field) for field in ('url', 'username', 'password')}, key)
            for field, value in values.items():
                setattr(row, field, value)
        db.commit()
