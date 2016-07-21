# -*- coding: utf-8 -*-

from dmutils.data_tools import ValidationError, normalise_abn, normalise_acn

import pytest
from nose.tools import assert_equal, assert_in, assert_is_not_none, assert_true, assert_is


class TestNormaliseAcn(object):

    def test_basic_normalisation(self):
        assert_equal(normalise_acn(' 004085616 '), '004 085 616')

    def test_good_acn_formats(self):
        golden = '004 085 616'
        cases = [
            '004 085 616',
            '004-085-616',
            '004085616',
            ' 00    4085616 ',
            ' 004085616',
            ' 0 0 4 0 8 5 6 1 6 ',
            ' 0-0  4-0 856 1 6 ',
        ]
        for case in cases:
            assert_equal(normalise_acn(case), golden)

    def test_bad_acn_formats(self):
        cases = [
            'no',
            'foo@example.com',
            '',
            '1234',
            '1234567',
            '1?',
            'one two three',
        ]
        for case in cases:
            try:
                normalise_acn(case)
            except ValidationError, e:
                assert_in('Invalid ACN', e.message)
            else:
                raise Exception('Test failed for case: {}'.format(case))

    def test_bad_acn_checksums(self):
        cases = [
            '704085616',
            '074085616',
            '007085616',
            '004785616',
            '004075616',
            '004087616',
            '004085716',
            '004085676',
            '004085617',
        ]
        for case in cases:
            try:
                normalise_acn(case)
            except ValidationError, e:
                assert_in('Checksum failure', e.message)
            else:
                raise Exception('Test failed for case: {}'.format(case))


class TestNormaliseAbn(object):

    def test_basic_normalisation(self):
        assert_equal(normalise_abn(' 51824 753556   '), '51 824 753 556')

    def test_good_abn_formats(self):
        golden = '28 799 046 203'
        cases = [
            '28 799 046 203',
            '28-799-046-203',
            '28799046203',
            '28799 046 203',
            '  28 799 046203',
            '28 799046203           ',
            '28-799046-203',
            '2 8 7 9 9 0 4 6 2 0 3 ',
        ]
        for case in cases:
            assert_equal(normalise_abn(case), golden)

    def test_bad_abn_formats(self):
        cases = [
            'no',
            'foo@example.com',
            '',
            '1234',
            '1234567890',
            '1?',
            'one two three',
            '08 799 046 203'
        ]
        for case in cases:
            try:
                normalise_abn(case)
            except ValidationError, e:
                assert_in('Invalid ABN', e.message)
            else:
                raise Exception('Test failed for case: {}'.format(case))

    def test_bad_abn_checksums(self):
        cases = [
            '98799046203',
            '29799046203',
            '28999046203',
            '28709046203',
            '28790046203',
            '28799946203',
            '28799096203',
            '28799049203',
            '28799046903',
            '28799046293',
            '28799046209',
        ]
        for case in cases:
            try:
                normalise_abn(case)
            except ValidationError, e:
                assert_in('Checksum failure', e.message)
            else:
                raise Exception('Test failed for case: {}'.format(case))
