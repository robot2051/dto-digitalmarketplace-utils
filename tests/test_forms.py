# -*- coding: utf-8 -*-

from dmutils.forms import DmForm, email_regex, FakeCsrf, render_template_with_csrf, StripWhitespaceStringField

from helpers import BaseApplicationTest


class TestForm(DmForm):
    stripped_field = StripWhitespaceStringField('Stripped', id='stripped_field')


class TestFormHandling(BaseApplicationTest):

    def test_whitespace_stripping(self):
        with self.flask.app_context():
            form = TestForm(stripped_field='  asdf ', csrf_token=FakeCsrf.valid_token)
            assert form.validate()
            assert form.stripped_field.data == 'asdf'

    def test_csrf_protection(self):
        with self.flask.app_context():
            form = TestForm(stripped_field='asdf', csrf_token='bad')
            assert not form.validate()
            assert 'csrf_token' in form.errors

    def test_does_not_crash_on_missing_csrf_token(self):
        with self.flask.app_context():
            form = TestForm(stripped_field='asdf')
            assert not form.validate()
            assert 'csrf_token' in form.errors

    def test_render_template_with_csrf(self):
        with self.flask.app_context():
            response, status_code = render_template_with_csrf('test_form.html', 123)
        assert status_code == 123
        assert response.cache_control.private
        assert response.cache_control.max_age == self.flask.config['CSRF_TIME_LIMIT']
        assert FakeCsrf.valid_token in response.data


def test_valid_email_formats():
    cases = [
        'good@example.com',
        'good-email@example.com',
        'good-email+plus@example.com',
        'good@subdomain.example.com',
        'good@hyphenated-subdomain.example.com',
    ]
    for address in cases:
        assert email_regex.regex.match(address) is not None, address


def test_invalid_email_formats():
    cases = [
        '',
        'bad',
        'bad@@example.com',
        'bad @example.com',
        'bad@.com',
        'bad.example.com',
        '@',
        '@example.com',
        'bad@',
        'bad@example.com,bad2@example.com',
        'bad@example.com bad2@example.com',
        'bad@example.com,other.example.com',
    ]
    for address in cases:
        assert email_regex.regex.match(address) is None, address
