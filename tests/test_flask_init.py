from flask.ext.cache import Cache

from dmutils.flask_init import pluralize, init_app, init_frontend_app, init_manager
from helpers import BaseApplicationTest, Config

import pytest


@pytest.mark.parametrize("count,singular,plural,output", [
    (0, "person", "people", "people"),
    (1, "person", "people", "person"),
    (2, "person", "people", "people"),
])
def test_pluralize(count, singular, plural, output):
    assert pluralize(count, singular, plural) == output


class TestDevCacheInit(BaseApplicationTest):

    def setup(self):
        self.cache = Cache()
        self.config.DM_CACHE_TYPE = 'dev'
        super(TestDevCacheInit, self).setup()

    def test_config(self):
        assert self.cache.config['CACHE_TYPE'] == 'simple'


class TestProdCacheInit(BaseApplicationTest):

    def setup(self):
        self.cache = Cache()
        self.config.DM_CACHE_TYPE = 'prod'
        super(TestProdCacheInit, self).setup()

    def test_config(self):
        assert self.cache.config['CACHE_TYPE'] == 'filesystem'


class TestInitManager(BaseApplicationTest):

    def test_init_manager(self):
        manager = init_manager(self.flask, 5000, [])
