# -*- coding: utf-8 -*-
"""
    test_models

    Tests Magento Channel, Website, Store and StoreView

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import sys
import os

import unittest
import trytond.tests.test_tryton
from trytond.transaction import Transaction
from trytond.tests.test_tryton import USER, DB_NAME, CONTEXT
from tests.test_base import TestBase

DIR = os.path.abspath(os.path.normpath(
    os.path.join(
        __file__,
        '..', '..', '..', '..', '..', 'trytond'
    )
))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))


class TestModels(TestBase):
    '''
    Tests instance, website, store and store view
    '''

    def test0010create_channel(self):
        '''
        Tests if instance is created
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as txn:
            self.setup_defaults()

            with txn.set_context({'company': self.company.id}):
                values = {
                    'name': 'Test channel',
                    'price_list': self.price_list,
                    'invoice_method': 'order',
                    'shipment_method': 'order',
                    'source': 'manual',
                    'create_users': [('add', [USER])],
                    'warehouse': self.warehouse,
                    'payment_term': self.payment_term,
                    'company': self.company.id,

                    'magento_url': 'some test url 2',
                    'magento_api_user': 'admin',
                    'magento_api_key': 'testkey',
                    'magento_default_account_expense':
                        self.get_account_by_kind('expense'),
                    'magento_default_account_revenue':
                        self.get_account_by_kind('revenue'),
                    'magento_website_name': 'A test website 1',
                    'magento_website_id': 1,
                    'magento_website_code': 'test_code',
                    'magento_store_name': 'Store1',
                    'magento_store_id': 1,
                }

                channel, = self.Channel.create([values])

                self.assert_(channel)


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestModels)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
