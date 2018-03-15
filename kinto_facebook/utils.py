def facebook_conf(request, name):
    key = 'facebook.%s' % name
    return request.registry.settings[key]
