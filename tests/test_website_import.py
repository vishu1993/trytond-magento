# -*- coding: utf-8 -*-
"""
    test_website_import

    Tests import of Magento Websites, Stores and StoreViews

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import sys
import os

import unittest
import trytond.tests.test_tryton
from trytond.transaction import Transaction
from test_base import TestBase, load_json
from trytond.tests.test_tryton import USER, DB_NAME, CONTEXT

DIR = os.path.abspath(os.path.normpath(
    os.path.join(
        __file__,
        '..', '..', '..', '..', '..', 'trytond'
    )
))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))


class TestWebsiteImport(TestBase):
    '''
    Tests import of Magento Websites, Stores and StoreViews
    '''

    def test_0010_import_websites(self):
        """
        Test the import of websites
        """
        with Transaction().start(DB_NAME, USER, CONTEXT) as txn:
            self.setup_defaults()
            with txn.set_context({'company': self.company.id}):
                channel, = self.Channel.create([{
                    'name': 'Test Instance',
                    'price_list': self.price_list,
                    'invoice_method': 'order',
                    'shipment_method': 'order',
                    'source': 'manual',
                    'create_users': [('add', [USER])],
                    'warehouse': self.warehouse,
                    'payment_term': self.payment_term,
                    'company': self.company.id,
                    'magento_url': 'some test url 1',
                    'magento_api_user': 'admin',
                    'magento_api_key': 'testkey',
                    'magento_default_account_expense':
                        self.get_account_by_kind('expense'),
                    'magento_default_account_revenue':
                        self.get_account_by_kind('revenue'),
                }])
                websites_before_import = self.Website.search([])
                self.Website.find_or_create(
                    channel, load_json('core', 'website')
                )
                websites_after_import = self.Website.search([])

                self.assertTrue(
                    websites_after_import > websites_before_import
                )

    def test_0020_import_stores(self):
        """
        Tests the import of stores
        """
        with Transaction().start(DB_NAME, USER, CONTEXT) as txn:
            self.setup_defaults()
            with txn.set_context({'company': self.company.id}):
                channel, = self.Channel.create([{
                    'name': 'Test Instance',
                    'price_list': self.price_list,
                    'invoice_method': 'order',
                    'shipment_method': 'order',
                    'source': 'manual',
                    'create_users': [('add', [USER])],
                    'warehouse': self.warehouse,
                    'payment_term': self.payment_term,
                    'company': self.company.id,
                    'magento_url': 'some test url 1',
                    'magento_api_user': 'admin',
                    'magento_api_key': 'testkey',
                    'magento_default_account_expense':
                        self.get_account_by_kind('expense'),
                    'magento_default_account_revenue':
                        self.get_account_by_kind('revenue'),
                }])
                website = self.Website.find_or_create(
                    channel, load_json('core', 'website')
                )

                stores_before_import = self.Store.search([])
                self.Store.find_or_create(website, load_json('core', 'store'))
                stores_after_import = self.Store.search([])

                self.assertTrue(
                    stores_after_import > stores_before_import
                )

    def test_0030_import_store_views(self):
        """
        Tests import of store view
        """
        with Transaction().start(DB_NAME, USER, CONTEXT) as txn:
            self.setup_defaults()
            with txn.set_context({'company': self.company.id}):
                channel, = self.Channel.create([{
                    'name': 'Test Instance',
                    'price_list': self.price_list,
                    'invoice_method': 'order',
                    'shipment_method': 'order',
                    'source': 'manual',
                    'create_users': [('add', [USER])],
                    'warehouse': self.warehouse,
                    'payment_term': self.payment_term,
                    'company': self.company.id,
                    'magento_url': 'some test url 1',
                    'magento_api_user': 'admin',
                    'magento_api_key': 'testkey',
                    'magento_default_account_expense':
                        self.get_account_by_kind('expense'),
                    'magento_default_account_revenue':
                        self.get_account_by_kind('revenue'),
                }])
                website = self.Website.find_or_create(
                    channel, load_json('core', 'website')
                )
                store = self.Store.find_or_create(
                    website, load_json('core', 'store')
                )

                store_views_before_import = self.StoreView.search([])
                store_view = self.StoreView.find_or_create(
                    store, load_json('core', 'store_view')
                )
                store_view.save()
                store_views_after_import = self.StoreView.search([])

                self.assertTrue(
                    store_views_after_import > store_views_before_import
                )


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestWebsiteImport)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
