from datetime import timedelta
from functools import wraps
import re

from flask import abort, current_app, render_template, request, Response, session
from jinja2.filters import do_striptags
from wtforms import Form, StringField
from wtforms.csrf.core import CSRF
from wtforms.csrf.session import SessionCSRF
from wtforms.validators import Regexp, ValidationError


email_validator = Regexp(r'^[^@^\s]+@[\d\w-]+(\.[\d\w-]+)+$',
                         flags=re.UNICODE,
                         message='You must provide a valid email address')


_GOV_EMAIL_DOMAINS = [
    'gov.au',
    'digital.cabinet-office.gov.uk',
]


def is_government_email(email_address):
    domain = email_address.split('@')[-1]
    return any(domain == d or domain.endswith('.' + d) for d in _GOV_EMAIL_DOMAINS)


def government_email_validator(form, field):
    """
    A WTForms validator that uses the api to check the email against a government domain whitelist.

    Adds a flag 'non_gov' to the field for detecting if the user needs to be warned about a government email
    restriction.  This flag is only true if the given email address is known to be non-government (and not just typoed).
    """
    setattr(field.flags, 'non_gov', False)
    email_validator(form, field)
    if not is_government_email(field.data):
        setattr(field.flags, 'non_gov', True)
        # wtforms wraps the label in a <label> tag
        label = do_striptags(field.label)
        raise ValidationError('{} needs to be a government email address'.format(label))


class StripWhitespaceStringField(StringField):
    def __init__(self, label=None, **kwargs):

        kwargs['filters'] = kwargs.get('filters', []) + [strip_whitespace]
        super(StringField, self).__init__(label, **kwargs)


def strip_whitespace(value):
    if value is not None and hasattr(value, 'strip'):
        return value.strip()
    return value


class FakeCsrf(CSRF):
    """
    For testing purposes only.
    """

    valid_token = 'valid_fake_csrf_token'

    def generate_csrf_token(self, csrf_token):
        return self.valid_token

    def validate_csrf_token(self, form, field):
        if field.data != self.valid_token:
            raise ValueError('Invalid (fake) CSRF token')


class DmForm(Form):

    class Meta:
        csrf = True
        csrf_class = SessionCSRF
        csrf_secret = None
        csrf_time_limit = None

        @property
        def csrf_context(self):
            return session

    def __init__(self, *args, **kwargs):
        if current_app.config['CSRF_ENABLED']:
            self.Meta.csrf_secret = current_app.config['SECRET_KEY']
            self.Meta.csrf_time_limit = timedelta(seconds=current_app.config['CSRF_TIME_LIMIT'])
        elif current_app.config.get('CSRF_FAKED', False):
            self.Meta.csrf_class = FakeCsrf
        else:
            # FIXME: deprecated
            self.Meta.csrf = False
            self.Meta.csrf_class = None
        super(DmForm, self).__init__(*args, **kwargs)


def render_template_with_csrf(template_name, status_code=200, **kwargs):
    if 'form' not in kwargs:
        kwargs['form'] = DmForm()
    response = Response(render_template(template_name, **kwargs))

    # CSRF tokens are user-specific, even if the user isn't logged in
    response.cache_control.private = True

    max_age = current_app.config['DM_DEFAULT_CACHE_MAX_AGE']
    max_age = min(max_age, current_app.config.get('CSRF_TIME_LIMIT', max_age))
    response.cache_control.max_age = max_age

    return response, status_code


def is_csrf_token_valid():
    if not current_app.config['CSRF_ENABLED'] and not current_app.config.get('CSRF_FAKED', False):
        return True
    if 'csrf_token' not in request.form:
        return False
    form = DmForm(csrf_token=request.form['csrf_token'])
    return form.validate()


def valid_csrf_or_abort():
    if is_csrf_token_valid():
        return
    current_app.logger.info(
        u'csrf.invalid_token: Aborting request, user_id: {user_id}',
        extra={'user_id': session.get('user_id', '<unknown')})
    abort(400, 'Invalid CSRF token. Please try again.')


def check_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        valid_csrf_or_abort()
        return view(*args, **kwargs)
    return wrapped
