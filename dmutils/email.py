import base64
import hashlib
import six
from string import Template
import sys
import textwrap

import boto3
import botocore.exceptions
from flask import current_app, flash
from flask._compat import string_types

from datetime import datetime
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .formats import DATETIME_FORMAT

ONE_DAY_IN_SECONDS = 86400
SEVEN_DAYS_IN_SECONDS = 604800


class EmailError(Exception):
    pass


def send_email(to_email_addresses, email_body, subject, from_email, from_name, reply_to=None):
    if isinstance(to_email_addresses, string_types):
        to_email_addresses = [to_email_addresses]

    if current_app.config.get('DM_SEND_EMAIL_TO_STDERR', False):
        template = Template(textwrap.dedent("""\
            To: $to
            Subject: $subject
            From: $from_line
            Reply-To: $reply_to

            $body"""))
        sys.stderr.write(template.substitute(
            to=', '.join(to_email_addresses),
            subject=subject,
            from_line='{} <{}>'.format(from_name, from_email),
            reply_to=reply_to,
            body=email_body
        ))
    else:
        try:
            email_client = boto3.client('ses')

            result = email_client.send_email(
                Source=u"{} <{}>".format(from_name, from_email),
                Destination={
                    'ToAddresses': to_email_addresses
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': email_body,
                            'Charset': 'UTF-8'
                        }
                    }
                },
                ReplyToAddresses=[reply_to or from_email],
            )
        except botocore.exceptions.ClientError as e:
            current_app.logger.error("An SES error occurred: {error}", extra={'error': e.response['Error']['Message']})
            raise EmailError(e.response['Error']['Message'])

        current_app.logger.info("Sent email: id={id}, email={email_hash}",
                                extra={'id': result['ResponseMetadata']['RequestId'],
                                       'email_hash': hash_email(to_email_addresses[0])})


def generate_token(data, secret_key, salt):
    ts = URLSafeTimedSerializer(secret_key)
    return ts.dumps(data, salt=salt)


def decode_token(token, secret_key, salt, max_age_in_seconds=86400):
    ts = URLSafeTimedSerializer(secret_key)
    decoded, timestamp = ts.loads(
        token,
        salt=salt,
        max_age=max_age_in_seconds,
        return_timestamp=True
    )
    return decoded, timestamp


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def decode_password_reset_token(token, data_api_client):
    try:
        decoded, timestamp = decode_token(
            token,
            current_app.config["SECRET_KEY"],
            current_app.config["RESET_PASSWORD_SALT"],
            ONE_DAY_IN_SECONDS
        )
    except SignatureExpired:
        current_app.logger.info("Password reset attempt with expired token.")
        return {'error': 'token_expired'}
    except BadSignature as e:
        current_app.logger.info("Error changing password: {error}", extra={'error': six.text_type(e)})
        return {'error': 'token_invalid'}

    user = data_api_client.get_user(decoded["user"])
    user_last_changed_password_at = datetime.strptime(
        user['users']['passwordChangedAt'],
        DATETIME_FORMAT
    )

    if token_created_before_password_last_changed(
            timestamp,
            user_last_changed_password_at
    ):
        current_app.logger.info("Error changing password: Token generated earlier than password was last changed.")
        return {'error': 'token_invalid'}

    return decoded


def decode_invitation_token(encoded_token, role):
    required_fields = ['email_address', 'supplier_id', 'supplier_name'] if role == 'supplier' else ['email_address']
    try:
        token, timestamp = decode_token(
            encoded_token,
            current_app.config['SHARED_EMAIL_KEY'],
            current_app.config['INVITE_EMAIL_SALT'],
            SEVEN_DAYS_IN_SECONDS
        )
        if all(field in token for field in required_fields):
            return token
        else:
            raise ValueError('Invitation token is missing required keys')
    except SignatureExpired as e:
        current_app.logger.info("Invitation attempt with expired token. error {error}",
                                extra={'error': six.text_type(e)})
        return None
    except BadSignature as e:
        current_app.logger.info("Invitation reset attempt with expired token. error {error}",
                                extra={'error': six.text_type(e)})
        return None
    except ValueError as e:
        current_app.logger.info("error {error}",
                                extra={'error': six.text_type(e)})
        return None


def token_created_before_password_last_changed(token_timestamp, user_timestamp):
    return token_timestamp < user_timestamp
