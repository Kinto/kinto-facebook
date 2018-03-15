Facebook Auth support in Kinto
==============================

|travis| |master-coverage|

.. |travis| image:: https://travis-ci.org/Kinto/kinto-facebook.svg?branch=master
    :target: https://travis-ci.org/Kinto/kinto-facebook

.. |master-coverage| image::
    https://coveralls.io/repos/Kinto/kinto-facebook/badge.png?branch=master
    :alt: Coverage
    :target: https://coveralls.io/r/Kinto/kinto-facebook

*Kinto-facebook* enables authentication in *Kinto* applications using
*Facebook* OAuth2 bearer tokens.

It provides:

* An authentication policy class;
* Integration with *Kinto* cache backend for token verifications;
* Integration with *Kinto* for heartbeat view checks;
* Some optional endpoints to perform the *OAuth* dance (*optional*).


* `Kinto documentation <http://kinto.readthedocs.io/en/latest/>`_
* `Issue tracker <https://github.com/Kinto/kinto-facebook/issues>`_


Installation
------------

First of all, `create a Facebook Auth app <https://developers.facebook.com/apps/>`_.

You need to grab the `client_id`, `client_secret` and
`app_client_token` in the app general settings page:

::

   https://developers.facebook.com/apps/{client_id}/settings/basic/
   https://developers.facebook.com/apps/{client_id}/settings/advanced/


Install the Python package:

::

    pip install kinto-facebook


Include the package in the project configuration:

::

    kinto.includes = kinto_facebook

And configure authentication policy using `pyramid_multiauth
<https://github.com/mozilla-services/pyramid_multiauth#deployment-settings>`_ formalism:

::

    multiauth.policies = facebook
    multiauth.policy.facebook.use = kinto_facebook.authentication.FacebookAuthenticationPolicy

By default, it will rely on the cache configured in *Kinto*.


Configuration
-------------

Fill those settings with the values obtained during the application registration:

::

    facebook.client_id = 89513028159972bc
    facebook.client_secret = 9aced230585cc0aaea0a3467dd800
    facebook.app_access_token = 30ce836499a146428464b28816b1618b
    facebook.webapp.authorized_domains = *
    # facebook.cache_ttl_seconds = 300
    # facebook.state.ttl_seconds = 3600


In case the application shall not behave as a relier (a.k.a. OAuth dance
endpoints disabled):

::

    facebook.relier.enabled = false


If necessary, override default values for authentication policy:

::

    facebook.header_type = Bearer+Facebook


Login flow
----------

OAuth Bearer token
::::::::::::::::::

Use the OAuth token with this header:

::

    Authorization: Bearer <access_token>


:notes:

    If the token is not valid, this will result in a ``401`` error response.


Obtain token using Web UI
:::::::::::::::::::::::::

* Navigate the client to ``GET /facebook/login?redirect=http://app-endpoint/%23``.
  There, a session cookie will be set, and the client will be redirected to a login
  form on the Facebook content server;
* After submitting the credentials on the login page, the client will
  be redirected to ``http://app-endpoint/#{token}`` (the web-app).
