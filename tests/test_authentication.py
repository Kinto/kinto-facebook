import time
import unittest

import mock
import pytest
import requests
from pyramid import httpexceptions

from kinto.core.cache import memory as memory_backend
from kinto.core.testing import DummyRequest

from kinto_facebook import authentication, DEFAULT_SETTINGS


class FacebookAuthenticationPolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = authentication.FacebookAuthenticationPolicy()
        self.backend = memory_backend.Cache(cache_prefix="tests",
                                            cache_max_size_bytes=float("inf"))

        self.request = self._build_request()
        self.profile_data = {
            "app_id": 138483919580948,
            "type": "USER",
            "application": "Social Cafe",
            "expires_at": 1352419328,
            "is_valid": True,
            "issued_at": 1347235328,
            "metadata": {
                "sso": "iphone-safari"
            },
            "scopes": [
                "email",
                "publish_actions"
            ],
            "user_id": "33"
        }

    def tearDown(self):
        self.backend.flush()

    def _build_request(self):
        request = DummyRequest()
        request.bound_data = {}
        request.registry.cache = self.backend
        settings = DEFAULT_SETTINGS.copy()
        settings['userid_hmac_secret'] = '1234'
        settings['facebook.cache_ttl_seconds'] = '0.01'
        request.registry.settings = settings
        request.headers['Authorization'] = 'Bearer foo'
        return request

    def test_returns_none_if_authorization_header_is_missing(self):
        self.request.headers.pop('Authorization')
        user_id = self.policy.unauthenticated_userid(self.request)
        self.assertIsNone(user_id)

    def test_returns_none_if_token_is_malformed(self):
        self.request.headers['Authorization'] = 'Bearerfoo'
        user_id = self.policy.unauthenticated_userid(self.request)
        self.assertIsNone(user_id)

    def test_returns_none_if_token_is_unknown(self):
        self.request.headers['Authorization'] = 'Carrier foo'
        user_id = self.policy.authenticated_userid(self.request)
        self.assertIsNone(user_id)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_returns_facebook_userid(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        user_id = self.policy.authenticated_userid(self.request)
        assert "33" == user_id

    @mock.patch('kinto_facebook.authentication.requests')
    def test_returns_facebook_user_id_in_principals(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        principals = self.policy.effective_principals(self.request)
        self.assertIn("33", principals)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_oauth_handle_invalid_tokens(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": {'is_valid': False}}
        principals = self.policy.effective_principals(self.request)
        self.assertNotIn("33", principals)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_oauth_verification_is_cached(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        # First request from client.
        request = self._build_request()
        self.policy.authenticated_userid(request)
        # Second request from same client.
        request = self._build_request()
        self.policy.authenticated_userid(request)
        # Cache backend was used.
        self.assertEqual(1, api_mocked.get.call_count)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_oauth_verification_is_done_once_per_request(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        # First request from client.
        self.policy.authenticated_userid(self.request)
        # Within the same request cycle, token won't be verified.
        self.request.headers['Authorization'] = 'Bearer another'
        self.policy.authenticated_userid(self.request)
        # Request bound data is used.
        self.assertEqual(1, api_mocked.get.call_count)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_oauth_verification_uses_cache_by_token(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        # First request from client.
        request = self._build_request()
        self.policy.authenticated_userid(request)
        # Second request from another client.
        request = self._build_request()
        request.headers['Authorization'] = 'Bearer another'
        self.policy.authenticated_userid(request)
        # Cache backend key was different.
        self.assertEqual(2, api_mocked.get.call_count)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_oauth_verification_cache_has_ttl(self, api_mocked):
        api_mocked.get.return_value.json.return_value = {"data": self.profile_data}
        # First request from client.
        request = self._build_request()
        self.policy.authenticated_userid(request)
        # Second request from same client after TTL.
        time.sleep(0.02)
        request = self._build_request()
        self.policy.authenticated_userid(request)
        # Cache backend key was expired.
        self.assertEqual(2, api_mocked.get.call_count)

    @mock.patch('kinto_facebook.authentication.requests')
    def test_handle_facebook_server_misbehaviours(self, request_mock):
        request_mock.get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError
        # Since we mock requests, we need to provide requests.exceptions here too
        request_mock.exceptions.HTTPError = requests.exceptions.HTTPError

        with pytest.raises(httpexceptions.HTTPServiceUnavailable):
            request = self._build_request()
            self.policy.authenticated_userid(request)

    def test_forget_uses_realm(self):
        policy = authentication.FacebookAuthenticationPolicy(realm='Who')
        headers = policy.forget(self.request)
        self.assertEqual(headers[0],
                         ('WWW-Authenticate', 'Bearer realm="Who"'))


class FacebookPingTest(unittest.TestCase):
    def setUp(self):
        self.request = DummyRequest()
        self.request.registry.settings = DEFAULT_SETTINGS
        self.request.registry.settings['facebook.authorization_endpoint'] = 'http://graph.facebook'

    def test_returns_none_if_oauth_deactivated(self):
        self.request.registry.settings['facebook.authorization_endpoint'] = None
        self.assertIsNone(authentication.facebook_ping(self.request))

    @mock.patch('requests.get')
    def test_returns_true_if_ok(self, get_mocked):
        httpOK = requests.models.Response()
        httpOK.status_code = 200
        get_mocked.return_value = httpOK
        self.assertTrue(authentication.facebook_ping(self.request))

    @mock.patch('requests.get')
    def test_returns_false_if_ko(self, get_mocked):
        get_mocked.side_effect = requests.exceptions.HTTPError()
        self.assertFalse(authentication.facebook_ping(self.request))
