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
                }

                channel, = self.Channel.create([values])

                self.assert_(channel)

    def test0020create_website(self):
        '''
        Tests if website is created under instance
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            values = {
                'name': 'A test website',
                'magento_id': 3,
                'code': 'test_code',
                'channel': self.channel1.id,
            }

            website, = self.Website.create([values])
            self.assert_(website)

            self.assertEqual(website.company, self.channel1.company)

    def test0030create_store(self):
        '''
        Tests if store is created under website
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            values = {
                'name': 'A test store',
                'magento_id': 2,
                'website': self.website1.id,
            }

            store, = self.Store.create([values])
            self.assert_(store)

            self.assertEqual(store.company, self.website1.company)
            self.assertEqual(store.channel, self.website1.channel)

    def test0040create_store_view(self):
        '''
        Tests if store view is created for store
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            values = {
                'name': 'A test store view',
                'code': 'test_code',
                'magento_id': 2,
                'store': self.store.id,
            }

            store_view, = self.StoreView.create([values])
            self.assert_(store_view)

            self.assertEqual(store_view.channel, self.store.channel)
            self.assertEqual(store_view.company, self.store.company)
            self.assertEqual(store_view.website, self.store.website)


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
