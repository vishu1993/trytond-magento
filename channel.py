# -*- coding: utf-8 -*-
"""
    channel

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: see LICENSE for more details.
"""
import magento

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.model import ModelView, fields
from .api import OrderConfig, Core

__metaclass__ = PoolMeta
__all__ = ['Channel']


class Channel:
    """
    Sale Channel model
    """
    __name__ = 'sale.channel'

    # Instance
    magento_url = fields.Char("Magento Site URL", required=True)
    magento_api_user = fields.Char("API User", required=True)
    magento_api_key = fields.Char("API Key", required=True)
    magento_websites = fields.One2Many(
        "magento.instance.website", "instance", "Website", readonly=True
    )
    magento_order_states = fields.One2Many(
        "magento.order_state", "instance", "Order States"
    )
    magento_carriers = fields.One2Many(
        "magento.instance.carrier", "instance", "Carriers / Shipping Methods"
    )
    magento_order_prefix = fields.Char(
        'Sale Order Prefix',
        help="This helps to distinguish between orders from different "
            "instances"
    )

    magento_default_account_expense = fields.Property(fields.Many2One(
        'account.account', 'Account Expense', domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company')),
        ], depends=['company'], required=True
    ))

    #: Used to set revenue account while creating products.
    magento_default_account_revenue = fields.Property(fields.Many2One(
        'account.account', 'Account Revenue', domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company')),
        ], depends=['company'], required=True
    ))

    @classmethod
    def get_source(cls):
        """
        Get the source
        """
        res = super(Channel, cls).get_source()
        res.append(('magento', 'Magento'))
        return res

    @staticmethod
    def default_magento_order_prefix():
        """
        Sets default value for magento order prefix
        """
        return 'mag_'

    @classmethod
    @ModelView.button_action('magento.wizard_import_order_states')
    def import_order_states(cls, channels):
        """
        Import order states for magento channel

        :param channels: List of active records of instances
        """
        OrderState = Pool().get('magento.order_state')

        for channel in channels:

            Transaction().context.update({
                'magento_instance': channel.id
            })

            # Import order states
            with OrderConfig(
                channel.url, channel.api_user, channel.api_key
            ) as order_config_api:
                OrderState.create_all_using_magento_data(
                    order_config_api.get_states()
                )

    @classmethod
    @ModelView.button_action('magento.wizard_test_connection')
    def test_connection(cls, channels):
        """
        Test magento connection and display appropriate message to user

        :param instances: Active record list of magento instance
        """
        try:
            instance, = channels
        except ValueError:
            cls.raise_user_error('multiple_instances')

        try:
            with magento.API(
                instance.url, instance.api_user, instance.api_key
            ):
                return
        except (
            xmlrpclib.Fault, IOError, xmlrpclib.ProtocolError, socket.timeout
        ):
            cls.raise_user_error("connection_error")

    @classmethod
    @ModelView.button_action('magento.wizard_import_websites')
    def import_websites(cls, instances):
        """
        Import the websites and their stores/view from magento

        :param instances: Active record list of magento instance
        """
        Website = Pool().get('magento.instance.website')
        Store = Pool().get('magento.website.store')
        StoreView = Pool().get('magento.store.store_view')
        MagentoOrderState = Pool().get('magento.order_state')

        try:
            instance, = instances
        except ValueError:
            cls.raise_user_error('multiple_instances')

        with Transaction().set_context(magento_instance=instance.id):

            # Import order states
            with OrderConfig(
                instance.url, instance.api_user, instance.api_key
            ) as order_config_api:
                MagentoOrderState.create_all_using_magento_data(
                    order_config_api.get_states()
                )

            # Import websites
            with Core(
                instance.url, instance.api_user, instance.api_key
            ) as core_api:
                websites = []
                stores = []

                mag_websites = core_api.websites()

                # Create websites
                for mag_website in mag_websites:
                    websites.append(Website.find_or_create(
                        instance, mag_website
                    ))

                for website in websites:
                    mag_stores = core_api.stores(
                        {'website_id': {'=': website.magento_id}}
                    )

                    # Create stores
                    for mag_store in mag_stores:
                        stores.append(Store.find_or_create(website, mag_store))

                for store in stores:
                    mag_store_views = core_api.store_views(
                        {'group_id': {'=': store.magento_id}}
                    )

                    # Create store views
                    for mag_store_view in mag_store_views:
                            store_view = StoreView.find_or_create(
                                store, mag_store_view
                            )
                            # AR refactoring
                            store_view.save()

    @classmethod
    @ModelView.button_action('magento.wizard_import_carriers')
    def import_carriers(cls, instances):
        """
        Import carriers/shipping methods from magento for instances

        :param instances: Active record list of magento instances
        """
        InstanceCarrier = Pool().get('magento.instance.carrier')

        for instance in instances:

            with Transaction().set_context({
                'magento_instance': instance.id
            }):
                with OrderConfig(
                    instance.url, instance.api_user, instance.api_key
                ) as order_config_api:
                    mag_carriers = order_config_api.get_shipping_methods()

                InstanceCarrier.create_all_using_magento_data(mag_carriers)
