import logging
import uuid
from fnmatch import fnmatch
from urllib.parse import urlparse, urlencode

import colander
import requests
from cornice.validators import colander_validator
from pyramid import httpexceptions
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.settings import aslist

from kinto.core import Service
from kinto.core.errors import http_error, ERRORS, json_error_handler, raise_invalid
from kinto.core.resource.schema import URL

from kinto_facebook.utils import facebook_conf


logger = logging.getLogger(__name__)


login = Service(name='facebook-login',
                path='/facebook/login',
                error_handler=json_error_handler)

token = Service(name='facebook-token',
                path='/facebook/token',
                error_handler=json_error_handler)


def persist_state(request):
    """Persist arbitrary string in cache.
    It will be matched when the user returns from the OAuth server login
    page.
    """
    state = uuid.uuid4().hex
    redirect_url = request.validated['querystring']['redirect']
    expiration = float(facebook_conf(request, 'cache_ttl_seconds'))

    request.registry.cache.set(state, redirect_url, expiration)

    return state


class FacebookLoginQueryString(colander.MappingSchema):
    redirect = URL()


class FacebookLoginRequest(colander.MappingSchema):
    querystring = FacebookLoginQueryString()


def authorized_redirect(req, **kwargs):
    authorized = aslist(facebook_conf(req, 'webapp.authorized_domains'))
    if not req.validated:
        # Schema was not validated. Give up.
        return False

    redirect = req.validated['querystring']['redirect']

    domain = urlparse(redirect).netloc

    if not any((fnmatch(domain, auth) for auth in authorized)):
        req.errors.add('querystring', 'redirect',
                       'redirect URL is not authorized')


@login.get(schema=FacebookLoginRequest, permission=NO_PERMISSION_REQUIRED,
           validators=(colander_validator, authorized_redirect))
def facebook_login(request):
    """Helper to redirect client towards Facebook login form."""
    state = persist_state(request)

    params = {
        'client_id': facebook_conf(request, 'client_id'),
        'redirect_uri': request.route_url(token.name),
        'state': state
    }

    login_form_url = '{}?{}'.format(facebook_conf(request, 'authorization_endpoint'),
                                    urlencode(params))

    request.response.status_code = 302
    request.response.headers['Location'] = login_form_url

    return {}


class OAuthQueryString(colander.MappingSchema):
    code = colander.SchemaNode(colander.String())
    state = colander.SchemaNode(colander.String())


class OAuthRequest(colander.MappingSchema):
    querystring = OAuthQueryString()


@token.get(schema=OAuthRequest, permission=NO_PERMISSION_REQUIRED,
           validators=(colander_validator,))
def facebook_token(request):
    """Return OAuth token from authorization code.
    """
    state = request.validated['querystring']['state']
    code = request.validated['querystring']['code']

    # Require on-going session
    stored_redirect = request.registry.cache.get(state)

    # Make sure we cannot try twice with the same code
    request.registry.cache.delete(state)
    if not stored_redirect:
        error_msg = 'The Facebook Auth session was not found, please re-authenticate.'
        return http_error(httpexceptions.HTTPRequestTimeout(),
                          errno=ERRORS.MISSING_AUTH_TOKEN,
                          message=error_msg)

    url = facebook_conf(request, 'token_endpoint')
    params = {
        'client_id': facebook_conf(request, 'client_id'),
        'client_secret': facebook_conf(request, 'client_secret'),
        'redirect_uri': request.route_url(token.name),
        'code': code,
    }

    resp = requests.get(url, params=params)
    if resp.status_code == 400:
        response_body = resp.json()
        logger.error("Facebook Token Validation Failed: {}".format(response_body))
        error_details = {
            'name': 'code',
            'location': 'querystring',
            'description': 'Facebook OAuth code validation failed.'
        }
        raise_invalid(request, **error_details)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.exception("Facebook Token Protocol Error")
        raise httpexceptions.HTTPServiceUnavailable()
    else:
        response_body = resp.json()
        access_token = response_body['access_token']

    return httpexceptions.HTTPFound(location='%s%s' % (stored_redirect, access_token))
