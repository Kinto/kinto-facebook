import logging

import requests
from pyramid import authentication as base_auth
from pyramid import httpexceptions
from pyramid.interfaces import IAuthenticationPolicy
from zope.interface import implementer

from kinto.core import utils as core_utils
from kinto_facebook.utils import facebook_conf

logger = logging.getLogger(__name__)

REIFY_KEY = 'facebook_verified_token'


@implementer(IAuthenticationPolicy)
class FacebookAuthenticationPolicy(base_auth.CallbackAuthenticationPolicy):
    def __init__(self, realm='Realm'):
        self.realm = realm
        self._cache = None

    def unauthenticated_userid(self, request):
        """Return the Facebook user_id or ``None`` if token could not be verified.
        """
        authorization = request.headers.get('Authorization', '')
        try:
            authmeth, token = authorization.split(' ', 1)
        except ValueError:
            return None
        if authmeth.lower() != facebook_conf(request, 'header_type').lower():
            return None

        user_id = self._verify_token(token, request)
        return user_id

    def forget(self, request):
        """A no-op. Credentials are sent on every request.
        Return WWW-Authenticate Realm header for Bearer token.
        """
        return [('WWW-Authenticate', '{} realm="{}"'.format(
            facebook_conf(request, 'header_type'), self.realm))]

    def _verify_token(self, access_token, request):
        """Verify the token extracted from the Authorization header.

        This method stores the result in two locations to avoid hitting the
        auth remote server as much as possible:

        - on the request object, in case the Pyramid authentication methods
          like `effective_principals()` or `authenticated_userid()` are called
          several times during the request cycle;

        - in the cache backend, to reuse validated token from one request to
          another (during ``cache_ttl_seconds`` seconds.)
        """
        # First check if this request was already verified.
        # `request.bound_data` is an attribute provided by Kinto to store
        # some data that is shared among sub-requests (e.g. default bucket
        # or batch requests)
        if REIFY_KEY not in request.bound_data:
            settings = request.registry.settings
            hmac_secret = settings['userid_hmac_secret']

            cache_ttl = float(facebook_conf(request, 'cache_ttl_seconds'))

            hmac_token = core_utils.hmac_digest(hmac_secret, access_token)
            cache_key = 'facebook:verify:{}'.format(hmac_token)

            payload = request.registry.cache.get(cache_key)

            if payload is None:
                # Verify token from Facebook
                url = facebook_conf(request, 'userinfo_endpoint')
                params = {
                    'input_token': access_token,
                    'access_token': facebook_conf(request, 'app_access_token'),
                }

                # XXX: Implement token validation for Facebook
                resp = requests.get(url, params=params)
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    logger.exception("Facebook Token Protocol Error")
                    raise httpexceptions.HTTPServiceUnavailable()
                else:
                    body = resp.json()
                    if not body['data']['is_valid']:
                        payload = {}
                    else:
                        payload = body['data']

            request.registry.cache.set(cache_key, payload, ttl=cache_ttl)

            # Save for next call.
            request.bound_data[REIFY_KEY] = payload.get('user_id')

        return request.bound_data[REIFY_KEY]


def facebook_ping(request):
    """Verify if the OAuth server is ready."""
    heartbeat_url = facebook_conf(request, 'authorization_endpoint')

    facebook = None
    if heartbeat_url is not None:
        try:
            timeout = float(facebook_conf(request, 'heartbeat_timeout_seconds'))
            r = requests.get(heartbeat_url, timeout=timeout)
            r.raise_for_status()
            facebook = True
        except requests.exceptions.HTTPError:
            pass

    return facebook
