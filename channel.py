# -*- coding: utf-8 -*-
"""
    channel

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: see LICENSE for more details.
"""
from datetime import datetime
import magento
import xmlrpclib
import socket

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
    magento_website_id = fields.Integer(
        'Website ID', readonly=True, required=True
    )
    magento_website_name = fields.Char(
        'Website Name', readonly=True, required=True
    )
    magento_website_code = fields.Char(
        'Website Code', required=True, readonly=True
    )
    magento_default_uom = fields.Many2One('product.uom', 'Default Product UOM')
    magento_root_category_id = fields.Integer(
        'Root Category ID', required=True
    )
    magento_store_name = fields.Char('Store Name', required=True)
    magento_store_id = fields.Integer(
        'Store ID', readonly=True, required=True
    )
    magentod_last_order_import_time = fields.DateTime('Last Order Import Time')
    magentod_last_order_export_time = fields.DateTime("Last Order Export Time")

    #: Last time at which the shipment status was exported to magento
    magento_last_shipment_export_time = fields.DateTime(
        'Last shipment export time'
    )

    #: Checking this will make sure that only the done shipments which have a
    #: carrier and tracking reference are exported.
    magento_export_tracking_information = fields.Boolean(
        'Export tracking information', help='Checking this will make sure'
        ' that only the done shipments which have a carrier and tracking '
        'reference are exported. This will update carrier and tracking '
        'reference on magento for the exported shipments as well.'
    )
    magento_taxes = fields.One2Many(
        "sale.channel.magento.tax", "channel", "Taxes"
    )
    magento_price_tiers = fields.One2Many(
        'sale.channel.magento.price_tier', 'channel', 'Default Price Tiers'
    )
    product_listings = fields.One2Many(
        'product.product.channel_listing', 'channel', 'Product Listings',
    )

    @classmethod
    def get_source(cls):
        """
        Get the source
        """
        res = super(Channel, cls).get_source()
        res.append(('magento', 'Magento'))
        return res

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Channel, cls).__setup__()
        cls._error_messages.update({
            "missing_magento_channel": 'Magento channel is not in context',
        })

    @staticmethod
    def default_magento_order_prefix():
        """
        Sets default value for magento order prefix
        """
        return 'mag_'

    @staticmethod
    def default_default_uom():
        """
        Sets default product uom for website
        """
        ProductUom = Pool().get('product.uom')

        return ProductUom.search([('name', '=', 'Unit')])[0].id

    @staticmethod
    def default_magento_root_category_id():
        """
        Sets default root category id. Is set to 1, because the default
        root category is 1
        """
        return 1

    def get_taxes(self, rate):
        "Return list of tax records with the given rate"
        for mag_tax in self.magento_taxes:
            if mag_tax.tax_percent == rate:
                return list(mag_tax.taxes)
        return []

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

    @classmethod
    def get_current_magento_channel(cls):
        """Helper method to get the current magento_channel.
        """
        channel_id = Transaction().context.get('magento_channel')
        if not channel_id:
            cls.raise_user_error('missing_magento_channel')
        return cls(Transaction().context.get('magento_channel'))

    def import_magento_products(self):
        "Import products for this magento channel"
        Product = Pool().get('product.template')

        Transaction().set_context({
            'magento_channel': self.id,
        })
        with magento.Product(
            self.magento_url, self.magento_api_user, self.magento_api_key
        ) as product_api:
            # TODO: Implement pagination and import each product as async task
            magento_products = product_api.list()

            products = []
            for magento_product in magento_products:
                products.append(
                    Product.find_or_create_using_magento_data(magento_product)
                )

        return map(int, products)

    def import_order_from_magento(self):
        """
        Imports sale from magento

        :return: List of active record of sale imported
        """
        Sale = Pool().get('sale.sale')
        MagentoOrderState = Pool().get('magento.order_state')

        new_sales = []
        with Transaction().set_context({
            'magento_channel': self.id,
        }):

            order_states = MagentoOrderState.search([
                ('channel', '=', self.id),
                ('use_for_import', '=', True)
            ])
            order_states_to_import_in = map(
                lambda state: state.code, order_states
            )

            if not order_states_to_import_in:
                self.raise_user_error("states_not_found")

            with magento.Order(
                self.magento_url, self.magento_api_user, self.magento_api_key
            ) as order_api:
                # Filter orders with date and store_id using list()
                # then get info of each order using info()
                # and call find_or_create_using_magento_data on sale
                filter = {
                    'store_id': {'=': self.magento_store_id},
                    'state': {'in': order_states_to_import_in},
                }
                if self.last_order_import_time:
                    last_order_import_time = \
                        self.last_order_import_time.replace(microsecond=0)
                    filter.update({
                        'updated_at': {
                            'gteq': last_order_import_time.isoformat(' ')
                        },
                    })
                self.write([self], {
                    'last_order_import_time': datetime.utcnow()
                })
                orders = order_api.list(filter)
                for order in orders:
                    new_sales.append(
                        Sale.find_or_create_using_magento_data(
                            order_api.info(order['increment_id'])
                        )
                    )

        return new_sales

    def export_order_status(self, channels=None):
        """
        Export sales orders status to magento.

        :param store_views: List of active record of store view
        """
        if channels is None:
            channels = self.search([])

        for channel in channels:
            channel.export_order_status_for_store_view()

    def export_order_status_for_store_view(self):
        """
        Export sale orders to magento for the current store view.
        If last export time is defined, export only those orders which are
        updated after last export time.

        :return: List of active records of sales exported
        """
        Sale = Pool().get('sale.sale')

        exported_sales = []
        domain = [('channel', '=', self.id)]

        if self.magentod_last_order_export_time:
            domain = [
                ('write_date', '>=', self.magentod_last_order_export_time)
            ]

        sales = Sale.search(domain)

        self.magentod_last_order_export_time = datetime.utcnow()
        self.save()

        for sale in sales:
            exported_sales.append(sale.export_order_status_to_magento())

        return exported_sales

    @classmethod
    def import_orders(cls, store_views=None):
        """
        Import orders from magento for store views

        :param store_views: Active record list of store views
        """
        if store_views is None:
            store_views = cls.search([])

        for store_view in store_views:
            store_view.import_order_from_store_view()

    @classmethod
    def export_shipment_status(cls, store_views=None):
        """
        Export Shipment status for shipments related to current store view.
        This method is called by cron.

        :param store_views: List of active records of store_view
        """
        if store_views is None:
            store_views = cls.search([])

        for store_view in store_views:
            # Set the channel in context
            with Transaction().set_context(
                magento_channel=store_view.channel.id
            ):
                store_view.export_shipment_status_to_magento()

    def export_shipment_status_to_magento(self):
        """
        Exports shipment status for shipments to magento, if they are shipped

        :return: List of active record of shipment
        """
        Shipment = Pool().get('stock.shipment.out')
        Sale = Pool().get('sale.sale')
        SaleLine = Pool().get('sale.line')

        sale_domain = [
            ('channel', '=', self.id),
            ('shipment_state', '=', 'sent'),
            ('magento_id', '!=', None),
            ('shipments', '!=', None),
        ]

        if self.magento_last_shipment_export_time:
            sale_domain.append(
                ('write_date', '>=', self.magento_last_shipment_export_time)
            )

        sales = Sale.search(sale_domain)

        self.magento_last_shipment_export_time = datetime.utcnow()
        self.save()

        for sale in sales:
            # Get the increment id from the sale reference
            increment_id = sale.reference[
                len(self.magento_order_prefix): len(sale.reference)
            ]

            for shipment in sale.shipments:
                try:
                    # Some checks to make sure that only valid shipments are
                    # being exported
                    if shipment.is_tracking_exported_to_magento or \
                            shipment.state not in ('packed', 'done') or \
                            shipment.magento_increment_id:
                        sales.pop(sale)
                        continue
                    with magento.Shipment(
                        self.magento_url, self.magento_api_user,
                        self.magento_api_key
                    ) as shipment_api:
                        item_qty_map = {}
                        for move in shipment.outgoing_moves:
                            if isinstance(move.origin, SaleLine) \
                                    and move.origin.magento_id:
                                # This is done because there can be multiple
                                # lines with the same product and they need
                                # to be send as a sum of quanitities
                                item_qty_map.setdefault(
                                    str(move.origin.magento_id), 0
                                )
                                item_qty_map[str(move.origin.magento_id)] += \
                                    move.quantity
                        shipment_increment_id = shipment_api.create(
                            order_increment_id=increment_id,
                            items_qty=item_qty_map
                        )
                        Shipment.write(list(sale.shipments), {
                            'magento_increment_id': shipment_increment_id,
                        })

                        if self.magento_export_tracking_information and (
                            shipment.tracking_number and shipment.carrier
                        ):
                            shipment.export_tracking_info_to_magento()
                except xmlrpclib.Fault, fault:
                    if fault.faultCode == 102:
                        # A shipment already exists for this order,
                        # we cannot do anything about it.
                        # Maybe it was already exported earlier or was created
                        # separately on magento
                        # Hence, just continue
                        continue

        return sales

    def export_inventory_to_magento(self):
        """
        Exports stock data of products from tryton to magento for this
        website
        :return: List of product templates
        """
        Location = Pool().get('stock.location')

        products = []
        locations = Location.search([('type', '=', 'storage')])

        for listing in self.product_listings:
            product = listing.product
            products.append(product)

            with Transaction().set_context({'locations': map(int, locations)}):
                product_data = {
                    'qty': product.quantity,
                    'is_in_stock': '1' if listing.product.quantity > 0
                        else '0',
                }

                # Update stock information to magento
                with magento.Inventory(
                    self.magento_url, self.magento_api_user,
                    self.magento_api_key
                ) as inventory_api:
                    inventory_api.update(
                        listing.product_identifier, product_data
                    )

        return products
