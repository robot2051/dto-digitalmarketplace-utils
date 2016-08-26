from flask import Flask
from flask_login import LoginManager

from dmutils.flask_init import init_app, init_frontend_app

from datetime import datetime
import mock


class IsDatetime(object):
    def __eq__(self, other):
        return isinstance(other, datetime)


def mock_file(filename, length, name=None):
    mock_file = mock.MagicMock()
    mock_file.read.return_value = '*' * length
    mock_file.filename = filename
    mock_file.name = name

    return mock_file


class Config(object):

    CSRF_ENABLED = False
    CSRF_FAKED = True
    CSRF_TIME_LIMIT = 30
    DM_DEFAULT_CACHE_MAX_AGE = 60
    DM_CACHE_TYPE = 'dev'
    SECRET_KEY = 'secret'
    ASSET_PATH = '/static'


class BaseApplicationTest(object):

    config = Config()
    login_manager = LoginManager()
    cache = None

    def setup(self):
        self.flask = Flask('test_app', template_folder='tests/templates/')
        self.login_manager = LoginManager()
        init_app(
            self.flask,
            self.config,
            login_manager=self.login_manager,
            cache=self.cache,
        )
        init_frontend_app(self.flask, None, self.login_manager)
        self.app = self.flask.test_client()
