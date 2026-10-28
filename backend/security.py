"""Single-admin sessions. No hardcoded credentials and no network transports."""
import asyncio
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timezone, timedelta
from http.cookies import SimpleCookie

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

COOKIE = 'safeguard_session'


def utc_now():
    # Existing SQLite columns use naive UTC; retain their on-disk convention.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def password_hash(password):
    if not 12 <= len(password) <= 1024:
        raise ValueError('Admin password must contain 12 to 1024 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return f'pbkdf2_sha256$600000${salt.hex()}${digest.hex()}'


def password_matches(password, encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token):
    return hmac.new(token.encode(), b'safeguard-csrf', hashlib.sha256).hexdigest()


class AuthService:
    def __init__(self, session_factory, models, config):
        self.sessions, self.models, self.config = session_factory, models, config
        self.failures = {}
        self.lock = threading.Lock()

    def bootstrap(self):
        try:
            from credentials import migrate_cameras
        except ModuleNotFoundError:
            from backend.credentials import migrate_cameras
        with self.sessions() as db:
            first_run = db.query(self.models.AdminUser).first() is None
        encoded = password_hash(self.config.ADMIN_PASSWORD) if first_run else None
        migrate_cameras(self.sessions, self.models.Camera, self.config.CREDENTIAL_KEY)
        with self.sessions() as db:
            if first_run:
                db.add(self.models.AdminUser(username=self.config.ADMIN_USERNAME, password_hash=encoded))
            db.query(self.models.AuthSession).filter(self.models.AuthSession.expires_at <= utc_now()).delete()
            db.commit()

    def login(self, username, password, address):
        now = time.monotonic()
        key = (address, username)
        with self.lock:
            self.failures = {k: v for k, v in self.failures.items() if now - v[1] < 60}
            count, _ = self.failures.get(key, (0, now))
            if count >= 5 or len(self.failures) >= 1024:
                raise HTTPException(429, 'Too many login attempts. Wait a minute and retry.')
            # Reserve before the expensive hash so parallel requests are bounded.
            self.failures[key] = (count + 1, now)
        with self.sessions() as db:
            user = db.query(self.models.AdminUser).filter_by(username=username).first()
            if user is None or not password_matches(password, user.password_hash):
                raise HTTPException(401, 'Invalid username or password.')
            token = secrets.token_urlsafe(32)
            db.add(self.models.AuthSession(token_hash=token_hash(token), user_id=user.id,
                                          expires_at=utc_now() + timedelta(hours=8)))
            db.commit()
        with self.lock:
            self.failures.pop(key, None)
        return token

    def lookup(self, token):
        if not token or len(token) > 128:
            return None
        with self.sessions() as db:
            session = db.get(self.models.AuthSession, token_hash(token))
            if session is None or session.expires_at <= utc_now():
                return None
            user = db.get(self.models.AdminUser, session.user_id)
            return {'username': user.username, 'csrf_token': csrf_token(token)} if user else None

    def logout(self, token):
        with self.sessions() as db:
            db.query(self.models.AuthSession).filter_by(token_hash=token_hash(token)).delete()
            db.commit()


class AccessMiddleware:
    """Protect API, docs, WebSockets and evidence before reaching their handlers."""
    def __init__(self, app, service):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get('headers', [])}
        origin = headers.get('origin')
        method = scope.get('method', 'GET')
        unsafe = method not in ('GET', 'HEAD', 'OPTIONS')
        if origin and origin not in self.service.config.ALLOWED_ORIGINS and (unsafe or scope['type'] == 'websocket'):
            return await self.reject(scope, receive, send, 403, 'Origin not allowed.')
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get('cookie', ''))
            token = cookie[COOKIE].value if COOKIE in cookie else ''
        except Exception:
            token = ''
        public = scope['path'] in ('/api/auth/login', '/api/auth/session') or method == 'OPTIONS'
        try:
            user = await asyncio.to_thread(self.service.lookup, token) if token else None
        except Exception:
            return await self.reject(scope, receive, send, 503, 'Authentication storage is unavailable.')
        if not public and not user:
            return await self.reject(scope, receive, send, 401, 'Login required.')
        if unsafe and not public and not hmac.compare_digest(headers.get('x-csrf-token', ''), csrf_token(token)):
            return await self.reject(scope, receive, send, 403, 'Invalid security token. Reload and retry.')
        scope.setdefault('state', {}).update(user=user, session_token=token)
        limit = 64 * 1024
        if scope['path'].startswith('/api/upload/'):
            kind = 'IMAGE' if scope['path'].endswith('/image') else 'VIDEO'
            limit += getattr(self.service.config, f'MAX_{kind}_UPLOAD_BYTES')
        try:
            length = int(headers.get('content-length', '0'))
        except ValueError:
            return await self.reject(scope, receive, send, 400, 'Invalid content length.')
        if length < 0 or length > limit:
            return await self.reject(scope, receive, send, 413, 'Request exceeds the size limit.')
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > limit:
                    raise HTTPException(413, 'Request exceeds the size limit.')
            return message

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).extend([
                    (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store'),
                    (b'referrer-policy', b'no-referrer'), (b'x-frame-options', b'DENY')])
            await send(message)
        await self.app(scope, limited_receive, secure_send)

    @staticmethod
    async def reject(scope, receive, send, status, detail):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 4401 if status == 401 else 4403})
        else:
            await JSONResponse({'detail': detail}, status_code=status)(scope, receive, send)


router = APIRouter()


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=120, pattern=r'^[\w.@-]+$')
    password: str = Field(min_length=1, max_length=1024)


@router.get('/api/auth/session')
def current_session(request: Request):
    return {'authenticated': bool(request.state.user), **(request.state.user or {})}


@router.post('/api/auth/login')
def login(value: Login, request: Request, response: Response):
    service = request.app.state.auth
    token = service.login(value.username, value.password, request.client.host if request.client else 'local')
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True, samesite='strict',
                        secure=service.config.COOKIE_SECURE, path='/')
    return {'authenticated': True, 'username': value.username, 'csrf_token': csrf_token(token)}


@router.post('/api/auth/logout')
def logout(request: Request, response: Response):
    request.app.state.auth.logout(request.state.session_token)
    response.delete_cookie(COOKIE, path='/')
    return {'authenticated': False}
