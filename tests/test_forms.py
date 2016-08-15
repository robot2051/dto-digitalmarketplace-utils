# -*- coding: utf-8 -*-

from dmutils.forms import (
    DmForm, email_validator, FakeCsrf, government_email_validator, render_template_with_csrf, StripWhitespaceStringField
)

from helpers import BaseApplicationTest


class TestForm(DmForm):
    stripped_field = StripWhitespaceStringField('Stripped', id='stripped_field')
    buyer_email = StripWhitespaceStringField(
        'Buyer email address', id='buyer_email',
        validators=[
            government_email_validator,
        ]
    )


class TestFormHandling(BaseApplicationTest):

    complete_form_data = {
        'csrf_token': FakeCsrf.valid_token,
        'stripped_field': '',
        'buyer_email': 'asdf@example.gov.au',
    }

    def build_form(self, **kwargs):
        data = dict(self.complete_form_data)
        data.update(**kwargs)
        return TestForm(**data)

    def test_valid_form(self):
        with self.flask.app_context():
            form = self.build_form()
            assert form.validate()
            assert not form.buyer_email.flags.non_gov

    def test_whitespace_stripping(self):
        with self.flask.app_context():
            form = self.build_form(stripped_field='  asdf ')
            assert form.validate()
            assert form.stripped_field.data == 'asdf'

    def test_invalid_email(self):
        with self.flask.app_context():
            form = self.build_form(buyer_email='@@@')
            assert not form.validate()
            assert 'buyer_email' in form.errors
            assert 'valid' in form.errors['buyer_email'][0]
            assert not form.buyer_email.flags.non_gov

    def test_non_gov_email(self):
        with self.flask.app_context():
            form = self.build_form(buyer_email='valid@example.com')
            assert not form.validate()
            assert 'buyer_email' in form.errors
            assert 'government' in form.errors['buyer_email'][0]
            assert form.buyer_email.flags.non_gov

    def test_csrf_protection(self):
        with self.flask.app_context():
            form = self.build_form(csrf_token='bad')
            assert not form.validate()
            assert 'csrf_token' in form.errors

    def test_does_not_crash_on_missing_csrf_token(self):
        with self.flask.app_context():
            form = TestForm(csrf_token=None)
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
        assert email_validator.regex.match(address) is not None, address


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
        assert email_validator.regex.match(address) is None, address
