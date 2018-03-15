import pkg_resources

from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool

from kinto_facebook.authentication import facebook_ping

#: Module version, as defined in PEP-0396.
__version__ = pkg_resources.get_distribution(__package__).version


DEFAULT_SETTINGS = {
    'facebook.authorization_endpoint': 'https://www.facebook.com/v2.12/dialog/oauth',
    'facebook.token_endpoint': 'https://graph.facebook.com/v2.12/oauth/access_token',
    'facebook.userinfo_endpoint': 'https://graph.facebook.com/debug_token',
    'facebook.app_access_token': None,
    'facebook.client_id': None,
    'facebook.client_secret': None,
    'facebook.relier.enabled': True,
    'facebook.header_type': 'Bearer',
    'facebook.requested_scope': 'public_profile email',
    'facebook.cache_ttl_seconds': 5 * 60,
    'facebook.state.ttl_seconds': 3600,  # 1 hour
    'facebook.heartbeat_timeout_seconds': 3,
    'facebook.webapp.authorized_domains': '',
}


def includeme(config):
    if not hasattr(config.registry, 'heartbeats'):
        message = ('kinto-facebook should be included once Kinto is initialized. '
                   'Use setting ``kinto.includes`` instead of ``pyramid.includes`` '
                   'or include it manually.')
        raise ConfigurationError(message)

    settings = config.get_settings()

    defaults = {k: v for k, v in DEFAULT_SETTINGS.items() if k not in settings}
    config.add_settings(defaults)

    # Register heartbeat to ping Facebook server.
    config.registry.heartbeats['facebook'] = facebook_ping

    config.add_api_capability(
        "facebook",
        version=__version__,
        description="You can authenticate to that server "
                    "using Facebook Auth.",
        url="https://github.com/Kinto/kinto-facebook")

    # Ignore Facebook Auth relier endpoint in case it's not activated.
    relier_enabled = asbool(settings['facebook.relier.enabled'])
    if relier_enabled:
        config.scan('kinto_facebook.views')
