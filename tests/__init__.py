# -*- coding: utf-8 -*-
"""
    __init__

    Test Suite

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import unittest
import trytond.tests.test_tryton

from tests.test_views import TestViewDepend
from tests.test_models import TestModels
from tests.test_country import TestCountry


def suite():
    """
    Define suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestViewDepend),
        unittest.TestLoader().loadTestsFromTestCase(TestModels),
        unittest.TestLoader().loadTestsFromTestCase(TestCountry),
    ])
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())