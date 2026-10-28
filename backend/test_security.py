"""Security integration tests: private temporary DB, no alert transports."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='safeguard-security-')
        root = Path(cls.temp.name)
        cls.key = Fernet.generate_key().decode()
        cls.password = 'isolated-test-password-only'
        cls.env = patch.dict(os.environ, {
            'DATABASE_URL': f'sqlite:///{root / "test.db"}',
            'SCREENSHOT_DIR': str(root / 'evidence'),
            'SAFEGUARD_ADMIN_PASSWORD': cls.password,
            'SAFEGUARD_CREDENTIAL_KEY': cls.key,
            'ALERT_DELIVERY_MODE': 'preview',
            'ENABLE_EMAIL_ALERTS': 'false', 'ENABLE_WHATSAPP_ALERTS': 'false',
        })
        cls.env.start()
        sys.path.insert(0, str(Path(__file__).parent))
        with patch('dotenv.load_dotenv'):
            import main
        cls.main = main
        cls.client_context = TestClient(main.app, raise_server_exceptions=False)
        cls.client = cls.client_context.__enter__()
        (root / 'evidence' / 'allowed.jpg').write_bytes(b'jpeg-test-fixture')

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.env.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client.cookies.clear()
        self.client.headers.pop('X-CSRF-Token', None)

    def login(self):
        response = self.client.post('/api/auth/login', json={'username': 'admin', 'password': self.password})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        return response

    def test_unauthenticated_routes_and_websocket_denied(self):
        for path in ['/health', '/api/violations', '/screenshots/allowed.jpg', '/docs']:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws/stream/1'):
                pass

    def test_login_hash_cookie_logout_and_revocation(self):
        response = self.login()
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        from security import password_matches
        with self.main.SessionLocal() as db:
            row = db.query(self.main.db_models.AdminUser).one()
            self.assertNotEqual(row.password_hash, self.password)
            self.assertTrue(password_matches(self.password, row.password_hash))
        token = self.client.cookies.get('safeguard_session')
        self.assertTrue(self.client.get('/api/auth/session').json()['authenticated'])
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 200)
        self.assertIsNone(self.main.auth_service.lookup(token))

    def test_csrf_origin_and_request_size(self):
        self.login()
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': ''}).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': 'https://evil.invalid'}).status_code, 403)
        self.assertEqual(self.client.post('/api/cameras', content='x' * 70000).status_code, 413)

    def test_encrypted_camera_roundtrip_never_exposes_secrets(self):
        self.login()
        response = self.client.post('/api/cameras', json={
            'name': 'security fixture', 'source_type': 'rtsp',
            'url': 'rtsp://operator:private-password@127.0.0.1:1/live?token=private-token'})
        self.assertEqual(response.status_code, 201, response.text)
        item = response.json()
        for secret in ['operator', 'private-password', 'private-token', 'enc:v1:']:
            self.assertNotIn(secret, response.text)
        self.assertTrue(item['has_credentials'])
        with self.main.SessionLocal() as db:
            row = db.get(self.main.db_models.Camera, item['id'])
            for value in [row.url, row.username, row.password]:
                self.assertTrue(value.startswith('enc:v1:'))
            before = row.url
        updated = self.client.put(f'/api/cameras/{item["id"]}', json={'url': item['url'], 'location': 'test'})
        self.assertEqual(updated.status_code, 200, updated.text)
        with self.main.SessionLocal() as db:
            self.assertEqual(db.get(self.main.db_models.Camera, item['id']).url, before)

    def test_download_paths_and_headers(self):
        self.login()
        good = self.client.get('/screenshots/allowed.jpg')
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.headers['x-content-type-options'], 'nosniff')
        from evidence import evidence_file
        from fastapi import HTTPException
        for filename in ['../test.db', '..\\test.db', 'test.svg', 'C:\\secret.jpg', 'missing.jpg']:
            with self.assertRaises(HTTPException):
                evidence_file(self.main.settings.SCREENSHOT_DIR, filename)

    def test_validation_does_not_echo_password(self):
        response = self.client.post('/api/auth/login', json={'username': 'bad name', 'password': 'private-value'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('private-value', response.text)
        self.assertNotIn('input', response.text)

    def test_bad_camera_scheme_rejected(self):
        self.login()
        for url in ['file:///C:/secret.jpg', '../secret.jpg']:
            response = self.client.post('/api/cameras', json={'name': 'unsafe', 'source_type': 'ip', 'url': url})
            self.assertEqual(response.status_code, 422)

    def test_expired_session(self):
        from security import utc_now, token_hash
        from datetime import timedelta
        self.login()
        token = self.client.cookies.get('safeguard_session')
        with self.main.SessionLocal() as db:
            db.get(self.main.db_models.AuthSession, token_hash(token)).expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get('/api/cameras').status_code, 401)

    def test_encryption_wrong_key_and_idempotent_migration(self):
        from credentials import protect, reveal, migrate_cameras
        encrypted = protect('secret', self.key)
        with self.assertRaises(ValueError):
            reveal(encrypted, Fernet.generate_key())
        migrate_cameras(self.main.SessionLocal, self.main.db_models.Camera, self.key)
        self.assertEqual(reveal(encrypted, self.key), 'secret')


if __name__ == '__main__':
    unittest.main()
