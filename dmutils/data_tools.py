# -*- coding: utf-8 -*-

import decimal
import re


class ValidationError(ValueError):
    def __init__(self, message):
        self.message = message


def normalise_acn(original_acn):
    """
    Takes an Australian Company Number (ACN) as a string, and returns a canonical version.

    E.g.:
    ' 004085616 ' -> '004 085 616'

    Raises ValidationError on invalid ACN.
    """
    # Strip all whitespace and dashes
    acn = re.sub('(\s|-)', '', original_acn)

    if re.match('[0-9]{9}', acn) is None:
        raise ValidationError('Invalid ACN: {}'.format(original_acn))

    # See the following for algorithm details:
    # https://www.asic.gov.au/for-business/starting-a-company/how-to-start-a-company/australian-company-numbers/australian-company-number-digit-check/
    weights = (8, 7, 6, 5, 4, 3, 2, 1, 1)
    digits = map(int, acn)
    total = sum(w * d for w, d in zip(weights, digits))
    if total % 10 != 0:
        raise ValidationError('Checksum failure for ACN: {}'.format(original_acn))

    acn = '{} {} {}'.format(acn[0:3], acn[3:6], acn[6:9])
    return acn


def normalise_abn(original_abn):
    """
    Takes an Australian Business Number (ABN) as a string, and returns a canonical version.

    E.g.:
    ' 51824 753556 ' -> '51 824 753 556'

    Raises ValidationError on invalid ABN.
    """
    # Strip all whitespace and dashes
    abn = re.sub('(\s|-)', '', original_abn)

    if re.match('[1-9][0-9]{10}', abn) is None:
        raise ValidationError('Invalid ABN: {}'.format(original_abn))

    # See the following for algorithm details:
    # https://abr.business.gov.au/HelpAbnFormat.aspx
    weights = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    digits = map(int, abn)
    digits[0] -= 1
    total = sum(w * d for w, d in zip(weights, digits))
    if total % 89 != 0:
        raise ValidationError('Checksum failure for ABN: {}'.format(original_abn))

    abn = '{} {} {} {}'.format(abn[0:2], abn[2:5], abn[5:8], abn[8:11])
    return abn


def parse_money(money_string):
    """
    Converts a string representation of money to a Python decimal.

    E.g.:
    '$5,200 ' -> 5200
    ' 1.50' -> 1.5

    Raises ValidationError on invalid format.
    """
    stripped = money_string.strip().replace(',', '')

    if stripped.startswith('$'):
        stripped = stripped[1:]

    try:
        return decimal.Decimal(stripped)
    except decimal.InvalidOperation:
        raise ValidationError('Invalid money format: {}'.format(money_string))
