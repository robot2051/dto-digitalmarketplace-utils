# -*- coding: utf-8 -*-
from freezegun import freeze_time
import pytest
import mock
import six

from botocore.exceptions import ClientError
from datetime import datetime

from dmutils.config import init_app
from dmutils.email import (
    generate_token, decode_token, send_email, EmailError, hash_email, decode_invitation_token,
    decode_password_reset_token, parse_fernet_timestamp, InvalidToken)
from dmutils.formats import DATETIME_FORMAT
from .test_user import user_json

TEST_SECRET_KEY = 'TestKeyTestKeyTestKeyTestKeyTestKeyTestKeyX='


@pytest.yield_fixture
def email_client():
    with mock.patch('boto3.client') as boto_client:
        instance = boto_client.return_value
        yield instance


@pytest.yield_fixture
def email_app(app):
    init_app(app)
    app.config['SHARED_EMAIL_KEY'] = TEST_SECRET_KEY
    app.config['INVITE_EMAIL_SALT'] = "Salt"
    app.config['SECRET_KEY'] = TEST_SECRET_KEY
    app.config["RESET_PASSWORD_SALT"] = "PassSalt"
    yield app


def test_calls_send_email_with_correct_params(email_app, email_client):
    with email_app.app_context():
        send_email(
            "email_address",
            "body",
            "subject",
            "from_email",
            "from_name",
        )

    email_client.send_email.assert_called_once_with(
        ReplyToAddresses=['from_email'],
        Message={'Body': {'Html': {'Charset': 'UTF-8', 'Data': 'body'}},
                 'Subject': {'Charset': 'UTF-8', 'Data': 'subject'}},
        Destination={'ToAddresses': ['email_address']},
        Source=u'from_name <from_email>'
    )


def test_calls_send_email_to_multiple_addresses(email_app, email_client):
    with email_app.app_context():
        send_email(
            ["email_address1", "email_address2"],
            "body",
            "subject",
            "from_email",
            "from_name",
        )

        assert email_client.send_email.call_args[1]['Destination']['ToAddresses'] == [
            "email_address1",
            "email_address2",
        ]


def test_calls_send_email_with_alternative_reply_to(email_app, email_client):
    with email_app.app_context():
        send_email(
            "email_address",
            "body",
            "subject",
            "from_email",
            "from_name",
            reply_to="reply_address"
        )

    email_client.send_email.assert_called_once_with(
        ReplyToAddresses=['reply_address'],
        Message={'Body': {'Html': {'Charset': 'UTF-8', 'Data': 'body'}},
                 'Subject': {'Charset': 'UTF-8', 'Data': 'subject'}},
        Destination={'ToAddresses': ['email_address']},
        Source=u'from_name <from_email>'
    )


def test_should_throw_exception_if_email_client_fails(email_app, email_client):
    with email_app.app_context():

        email_client.send_email.side_effect = ClientError(
            {'Error': {'Message': "this is an error"}}, ""
        )

        with pytest.raises(EmailError):
            send_email(
                "email_address",
                "body",
                "subject",
                "from_email",
                "from_name",
            )


def test_can_generate_token():
    token = generate_token({
        "key1": "value1",
        "key2": "value2"},
        secret_key=TEST_SECRET_KEY,
        salt="1234567890")

    token = decode_token(token, TEST_SECRET_KEY, '1234567890')
    assert {
        "key1": "value1",
        "key2": "value2"} == token


def test_parse_timestamp_from_token():
    test_time = datetime(2000, 1, 1)
    with freeze_time(test_time):
        data = {}
        token = generate_token(data, TEST_SECRET_KEY, 'PassSalt')
    timestamp = parse_fernet_timestamp(token)
    assert timestamp == test_time


def test_cant_decode_token_with_wrong_salt():
    token = generate_token({
        "key1": "value1",
        "key2": "value2"},
        secret_key=TEST_SECRET_KEY,
        salt="1234567890")

    with pytest.raises(InvalidToken) as error:
        decode_token(token, TEST_SECRET_KEY, 'wrong salt')


def test_cant_decode_token_with_wrong_key():
    token = generate_token({
        "key1": "value1",
        "key2": "value2"},
        secret_key=TEST_SECRET_KEY,
        salt="1234567890")

    with pytest.raises(InvalidToken) as error:
        decode_token(token, 'WrongKeyWrongKeyWrongKeyWrongKeyWrongKeyXXX=', '1234567890')


def test_hash_email():
    tests = [
        (u'test@example.com', six.b('lz3-Rj7IV4X1-Vr1ujkG7tstkxwk5pgkqJ6mXbpOgTs=')),
        (u'☃@example.com', six.b('jGgXle8WEBTTIFhP25dF8Ck-FxQSCZ_N0iWYBWve4Ps=')),
    ]

    for test, expected in tests:
        assert hash_email(test) == expected


def test_decode_password_reset_token_ok_for_good_token(email_app):
    user = user_json()
    user['users']['passwordChangedAt'] = "2016-01-01T12:00:00.30Z"
    data_api_client = mock.Mock()
    data_api_client.get_user.return_value = user
    with email_app.app_context():
        data = {'user': 'test@example.com'}
        token = generate_token(data, TEST_SECRET_KEY, 'PassSalt')
        assert decode_password_reset_token(token, data_api_client) == data


def test_decode_password_reset_token_does_not_work_if_bad_token(email_app):
    user = user_json()
    user['users']['passwordChangedAt'] = "2016-01-01T12:00:00.30Z"
    data_api_client = mock.Mock()
    data_api_client.get_user.return_value = user
    data = {'user': 'test@example.com'}
    token = generate_token(data, TEST_SECRET_KEY, 'PassSalt')[1:]

    with email_app.app_context():
        assert decode_password_reset_token(token, data_api_client) == {'error': 'token_invalid'}


def test_decode_password_reset_token_does_not_work_if_token_expired(email_app):
    user = user_json()
    user['users']['passwordChangedAt'] = "2016-01-01T12:00:00.30Z"
    data_api_client = mock.Mock()
    data_api_client.get_user.return_value = user
    with freeze_time('2015-01-02 03:04:05'):
        # Token was generated a year before current time
        data = {'user': 'test@example.com'}
        token = generate_token(data, TEST_SECRET_KEY, 'PassSalt')

    with freeze_time('2016-01-02 03:04:05'):
        with email_app.app_context():
            assert decode_password_reset_token(token, data_api_client) == {'error': 'token_invalid'}


def test_decode_password_reset_token_does_not_work_if_password_changed_later_than_token(email_app):
    user = user_json()
    user['users']['passwordChangedAt'] = "2016-01-01T13:00:00.30Z"
    data_api_client = mock.Mock()
    data_api_client.get_user.return_value = user

    with freeze_time('2016-01-01T12:00:00.30Z'):
        # Token was generated an hour earlier than password was changed
        data = {'user': 'test@example.com'}
        token = generate_token(data, TEST_SECRET_KEY, 'PassSalt')

    with freeze_time('2016-01-01T14:00:00.30Z'):
        # Token is two hours old; password was changed an hour ago
        with email_app.app_context():
            assert decode_password_reset_token(token, data_api_client) == {'error': 'token_invalid'}


def test_decode_invitation_token_decodes_ok_for_buyer(email_app):
    with email_app.app_context():
        data = {'email_address': 'test-user@email.com'}
        token = generate_token(data, TEST_SECRET_KEY, 'Salt')
        assert decode_invitation_token(token, role='buyer') == data


def test_decode_invitation_token_decodes_ok_for_supplier(email_app):
    with email_app.app_context():
        data = {'email_address': 'test-user@email.com', 'supplier_code': 1234, 'supplier_name': 'A. Supplier'}
        token = generate_token(data, TEST_SECRET_KEY, 'Salt')
        assert decode_invitation_token(token, role='supplier') == data


def test_decode_invitation_token_does_not_work_if_there_are_missing_keys(email_app):
    with email_app.app_context():
        data = {'email_address': 'test-user@email.com', 'supplier_name': 'A. Supplier'}
        token = generate_token(data, TEST_SECRET_KEY, email_app.config['INVITE_EMAIL_SALT'])

        assert decode_invitation_token(token, role='supplier') is None


def test_decode_invitation_token_does_not_work_if_bad_token(email_app):
    with email_app.app_context():
        data = {'email_address': 'test-user@email.com', 'supplier_name': 'A. Supplier'}
        token = generate_token(data, TEST_SECRET_KEY, email_app.config['INVITE_EMAIL_SALT'])[1:]

        assert decode_invitation_token(token, role='supplier') is None


def test_decode_invitation_token_does_not_work_if_token_expired(email_app):
    with freeze_time('2015-01-02 03:04:05'):
        data = {'email_address': 'test-user@email.com', 'supplier_name': 'A. Supplier'}
        token = generate_token(data, TEST_SECRET_KEY, email_app.config['INVITE_EMAIL_SALT'])

    with email_app.app_context():
        assert decode_invitation_token(token, role='supplier') is None
