import os
from flask_featureflags.contrib.inline import InlineFeatureFlag
from . import config, logging, proxy_fix, request_id, formats, filters
from flask import Markup, redirect, request, session
from flask.ext.script import Manager, Server
from flask_login import current_user

from asset_fingerprint import AssetFingerprinter
from user import User, user_logging_string


def init_app(
        application,
        config_object,
        bootstrap=None,
        data_api_client=None,
        db=None,
        feature_flags=None,
        login_manager=None,
        search_api_client=None,
):

    application.config.from_object(config_object)
    if hasattr(config_object, 'init_app'):
        config_object.init_app(application)

    # all belong to dmutils
    config.init_app(application)
    logging.init_app(application)
    proxy_fix.init_app(application)
    request_id.init_app(application)

    if bootstrap:
        bootstrap.init_app(application)
    if data_api_client:
        data_api_client.init_app(application)
    if db:
        db.init_app(application)
    if feature_flags:
        # Standardize FeatureFlags, only accept inline config variables
        feature_flags.init_app(application)
        feature_flags.clear_handlers()
        feature_flags.add_handler(InlineFeatureFlag())
    if login_manager:
        login_manager.init_app(application)
    if search_api_client:
        search_api_client.init_app(application)

    @application.before_request
    def set_scheme():
        request.environ['wsgi.url_scheme'] = application.config['DM_HTTP_PROTO']

    @application.after_request
    def add_header(response):
        response.headers['X-Frame-Options'] = 'DENY'
        return response


def init_frontend_app(application, data_api_client, login_manager):

    def request_log_handler(response):
        params = {
            'method': request.method,
            'url': request.url,
            'status': response.status_code,
            'user': user_logging_string(current_user),
        }
        application.logger.info('{method} {url} {status} {user}', extra=params)
    application.extensions['request_log_handler'] = request_log_handler

    @login_manager.user_loader
    def load_user(user_id):
        return User.load_user(data_api_client, user_id)

    @application.before_request
    def refresh_session():
        session.permanent = True
        session.modified = True

    @application.before_request
    def remove_trailing_slash():
        if request.path != application.config['URL_PREFIX'] + '/' and request.path.endswith('/'):
            if request.query_string:
                return redirect(
                    '{}?{}'.format(
                        request.path[:-1],
                        request.query_string.decode('utf-8')
                    ),
                    code=301
                )
            else:
                return redirect(request.path[:-1], code=301)

    @application.after_request
    def add_cache_control(response):
        if request.method != 'GET' or response.status_code in (301, 302):
            return response

        vary = response.headers.get('Vary', None)
        if vary:
            response.headers['Vary'] = vary + ', Cookie'
        else:
            response.headers['Vary'] = 'Cookie'

        if current_user.is_authenticated:
            response.cache_control.private = True
        if response.cache_control.max_age is None:
            response.cache_control.max_age = application.config['DM_DEFAULT_CACHE_MAX_AGE']

        return response

    @application.context_processor
    def inject_global_template_variables():
        template_data = {
            'pluralize': pluralize,
            'header_class': 'with-proposition',
            'asset_path': application.config['ASSET_PATH'] + '/',
            'asset_fingerprinter': AssetFingerprinter(asset_root=application.config['ASSET_PATH'] + '/')
        }
        return template_data

    @application.template_filter('markdown')
    def markdown_filter_flask(data):
        return Markup(filters.markdown_filter(data))
    application.add_template_filter(filters.format_links)
    application.add_template_filter(formats.timeformat)
    application.add_template_filter(formats.shortdateformat)
    application.add_template_filter(formats.dateformat)
    application.add_template_filter(formats.datetimeformat)
    application.add_template_filter(filters.smartjoin)


def pluralize(count, singular, plural):
    return singular if count == 1 else plural


def get_extra_files(paths):
    for path in paths:
        for dirname, dirs, files in os.walk(path):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    yield filename


def init_manager(application, port, extra_directories=()):

    manager = Manager(application)

    extra_files = list(get_extra_files(extra_directories))

    print("Watching {} extra files".format(len(extra_files)))

    manager.add_command(
        "runserver",
        Server(port=port, extra_files=extra_files)
    )

    @manager.command
    def runprodserver():
        from waitress import serve
        serve(application, port=port)

    @manager.command
    def list_routes():
        """List URLs of all application routes."""
        for rule in sorted(manager.app.url_map.iter_rules(), key=lambda r: r.rule):
            print("{:10} {}".format(", ".join(rule.methods - set(['OPTIONS', 'HEAD'])), rule.rule))

    return manager
