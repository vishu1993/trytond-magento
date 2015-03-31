# -*- coding: utf-8 -*-
"""
    magento_

    Magento

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import xmlrpclib
import socket
from datetime import datetime

import magento
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, Eval
from trytond.wizard import Wizard, StateView, Button, StateAction
from .api import OrderConfig, Core
from .sale import SaleLine


__all__ = [
    'InstanceWebsite', 'WebsiteStore', 'WebsiteStoreView',
    'TestConnectionStart', 'TestConnection', 'ImportWebsitesStart',
    'ImportWebsites', 'ExportInventoryStart', 'ExportInventory',
    'StorePriceTier', 'ExportTierPricesStart', 'ExportTierPrices',
    'ExportTierPricesStatus', 'ExportShipmentStatusStart',
    'ExportShipmentStatus', 'ImportOrderStatesStart', 'MagentoException',
    'ImportOrderStates', 'ImportCarriersStart', 'ImportCarriers'
]
__metaclass__ = PoolMeta


class InstanceWebsite(ModelSQL, ModelView):
    """
    Magento Channel Website

    A magento channel can have multiple websites.
    They act as  parents of stores. A website consists of one or more stores
    """
    __name__ = 'magento.instance.website'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, readonly=True)
    magento_id = fields.Integer('Magento ID', readonly=True, required=True)
    channel = fields.Many2One(
        'sale.channel', 'Channel', required=True, readonly=True,
    )
    company = fields.Function(
        fields.Many2One('company.company', 'Company'),
        'get_company'
    )
    stores = fields.One2Many(
        'magento.website.store', 'website', 'Stores',
        readonly=True,
    )
    default_uom = fields.Many2One('product.uom', 'Default Product UOM')
    magento_root_category_id = fields.Integer(
        'Magento Root Category ID', required=True
    )
    magento_product_templates = fields.One2Many(
        'magento.website.template', 'website', 'Magento Product Templates',
        readonly=True
    )

    def get_company(self, name):
        """
        Returns company related to channel

        :param name: Field name
        """
        return self.channel.company.id

    @staticmethod
    def default_magento_root_category_id():
        """
        Sets default root category id. Is set to 1, because the default
        root category is 1
        """
        return 1

    @staticmethod
    def default_default_uom():
        """
        Sets default product uom for website
        """
        ProductUom = Pool().get('product.uom')

        return ProductUom.search([('name', '=', 'Unit')])[0].id

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(InstanceWebsite, cls).__setup__()
        cls._sql_constraints += [
            (
                'magento_id_channel_unique', 'UNIQUE(magento_id, channel)',
                'A website must be unique in an channel'
            )
        ]

    @classmethod
    def find_or_create(cls, channel, values):
        """
        Looks for the website whose `values` are sent by magento against
        the channel with `channel` in tryton.
        If a record exists for this, return that else create a new one and
        return

        :param channel: Active record of channel
        :param values: Dictionary of values for a website sent by magento
        :return: Active record of record created/found
        """
        websites = cls.search([
            ('channel', '=', channel.id),
            ('magento_id', '=', int(values['website_id']))
        ])

        if websites:
            return websites[0]

        return cls.create([{
            'name': values['name'],
            'code': values['code'],
            'channel': channel.id,
            'magento_id': int(values['website_id']),
        }])[0]

    def export_inventory(self, websites):
        """
        Exports inventory stock information to magento

        :param websites: List of active records of website
        """
        for website in websites:
            website.export_inventory_to_magento()

    def export_inventory_to_magento(self):
        """
        Exports stock data of products from tryton to magento for this
        website

        :return: List of product templates
        """
        Location = Pool().get('stock.location')

        product_templates = []
        channel = self.channel

        locations = Location.search([('type', '=', 'storage')])

        for magento_product_template in self.magento_product_templates:
            product_template = magento_product_template.template
            product_templates.append(product_template)

            with Transaction().set_context({'locations': map(int, locations)}):
                product_data = {
                    'qty': product_template.quantity,
                    'is_in_stock': '1' if product_template.quantity > 0
                        else '0',
                }

                # Update stock information to magento
                with magento.Inventory(
                    channel.magento_url, channel.magento_api_user,
                    channel.magento_api_key
                ) as inventory_api:
                    inventory_api.update(
                        magento_product_template.magento_id, product_data
                    )

        return product_templates


class WebsiteStore(ModelSQL, ModelView):
    """
    Magento Website Store or Store view groups

    Stores are children of websites. The visibility of products and
    categories is managed on magento at store level by specifying the
    root category on a store.
    """
    __name__ = 'magento.website.store'

    name = fields.Char('Name', required=True)
    magento_id = fields.Integer('Magento ID', readonly=True, required=True)
    website = fields.Many2One(
        'magento.instance.website', 'Website', required=True,
        readonly=True,
    )
    channel = fields.Function(
        fields.Many2One('sale.channel', 'Sale Channel'),
        'get_channel'
    )
    company = fields.Function(
        fields.Many2One('company.company', 'Company'),
        'get_company'
    )
    store_views = fields.One2Many(
        'magento.store.store_view', 'store', 'Store Views', readonly=True
    )
    price_list = fields.Many2One(
        'product.price_list', 'Price List',
        domain=[('company', '=', Eval('company'))], depends=['company']
    )
    price_tiers = fields.One2Many(
        'magento.store.price_tier', 'store', 'Default Price Tiers'
    )

    def get_company(self, name):
        """
        Returns company related to website

        :param name: Field name
        """
        return self.website.company.id

    def get_channel(self, name):
        """
        Returns channel related to website

        :param name: Field name
        """
        return self.website.channel.id

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(WebsiteStore, cls).__setup__()
        cls._sql_constraints += [
            (
                'magento_id_website_unique', 'UNIQUE(magento_id, website)',
                'A store must be unique in a website'
            )
        ]

    @classmethod
    def find_or_create(cls, website, values):
        """
        Looks for the store whose `values` are sent by magento against the
        website with `website` in tryton.
        If a record exists for this, return that else create a new one and
        return

        :param website: Active record of website
        :param values: Dictionary of values for a store sent by magento
        :return: Active record of record created/found
        """
        stores = cls.search([
            ('website', '=', website.id),
            ('magento_id', '=', int(values['group_id']))
        ])

        if stores:
            return stores[0]

        return cls.create([{
            'name': values['name'],
            'magento_id': int(values['group_id']),
            'website': website.id,
        }])[0]

    def export_tier_prices_to_magento(self):
        """
        Exports tier prices of products from tryton to magento for this store

        :return: List of products
        """
        channel = self.website.channel

        for mag_product_template in self.website.magento_product_templates:
            product_template = mag_product_template.template
            product = product_template.products[0]

            # Get the price tiers from the product if the product has a price
            # tier table else get the default price tiers from current store
            price_tiers = product_template.price_tiers or self.price_tiers

            price_data = []
            for tier in price_tiers:
                if hasattr(tier, 'product'):
                    # The price tier comes from a product, then it has a
                    # function field for price, we use it directly
                    price = tier.price
                else:
                    # The price tier comes from the default tiers on store,
                    # we dont have a product on tier, so we use the current
                    # product in loop for computing the price for this tier
                    price = self.price_list.compute(
                        None, product, product.list_price, tier.quantity,
                        self.website.default_uom
                    )

                price_data.append({
                    'qty': tier.quantity,
                    'price': float(price),
                })

            # Update stock information to magento
            with magento.ProductTierPrice(
                channel.magento_url, channel.magento_api_user,
                channel.magento_api_key
            ) as tier_price_api:
                tier_price_api.update(
                    mag_product_template.magento_id, price_data
                )

        return len(self.website.magento_product_templates)


class WebsiteStoreView(ModelSQL, ModelView):
    """
    Magento Website Store View

    A store needs one or more store views to be browse-able in the front-end.
    It allows for multiple presentations of a store. Most implementations
    use store views for different languages
    """
    __name__ = 'magento.store.store_view'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, readonly=True)
    magento_id = fields.Integer('Magento ID', readonly=True, required=True)
    store = fields.Many2One(
        'magento.website.store', 'Store', required=True, readonly=True,
    )
    channel = fields.Function(
        fields.Many2One('sale.channel', 'Channel'),
        'get_channel'
    )
    website = fields.Function(
        fields.Many2One('magento.instance.website', 'Website'),
        'get_website'
    )
    company = fields.Function(
        fields.Many2One('company.company', 'Company'),
        'get_company'
    )
    last_order_import_time = fields.DateTime('Last Order Import Time')
    last_order_export_time = fields.DateTime("Last Order Export Time")

    #: Last time at which the shipment status was exported to magento
    last_shipment_export_time = fields.DateTime('Last shipment export time')

    #: Checking this will make sure that only the done shipments which have a
    #: carrier and tracking reference are exported.
    export_tracking_information = fields.Boolean(
        'Export tracking information', help='Checking this will make sure'
        ' that only the done shipments which have a carrier and tracking '
        'reference are exported. This will update carrier and tracking '
        'reference on magento for the exported shipments as well.'
    )

    taxes = fields.One2Many(
        "magento.store.store_view.tax", "store_view", "Taxes"
    )

    def get_taxes(self, rate):
        "Return list of tax records with the given rate"
        for store_view_tax in self.taxes:
            if store_view_tax.tax_percent == rate:
                return list(store_view_tax.taxes)
        return []

    def get_channel(self, name):
        """
        Returns channel related to store

        :param name: Field name
        """
        return self.store.channel.id

    def get_website(self, name):
        """
        Returns website related to store

        :param name: Field name
        """
        return self.store.website.id

    def get_company(self, name):
        """
        Returns company related to store

        :param name: Field name
        """
        return self.store.company.id

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(WebsiteStoreView, cls).__setup__()
        cls._sql_constraints += [
            (
                'magento_id_store_unique', 'UNIQUE(magento_id, store)',
                'A store view must be unique in a store'
            )
        ]
        cls._error_messages.update({
            "states_not_found": 'No order states found for importing orders! '
                'Please configure the order states on magento channel',
        })
        cls._buttons.update({
            'import_orders_button': {},
            'export_order_status_button': {}
        })

    @classmethod
    def find_or_create(cls, store, values):
        """
        Looks for the store view whose `values` are sent by magento against
        the store with `store` in tryton.
        If a record exists for this, return that else create a new one and
        return

        :param store: Active record of store
        :param values: Dictionary of values for store view sent by magento
        :return: Actice record of record created/found
        """
        store_views = cls.search([
            ('store', '=', store.id),
            ('magento_id', '=', int(values['store_id']))
        ])

        if store_views:
            return store_views[0]

        return cls(**{
            'name': values['name'],
            'code': values['code'],
            'store': store.id,
            'magento_id': int(values['store_id']),
        })

    @classmethod
    @ModelView.button_action('magento.wizard_import_orders')
    def import_orders_button(cls, store_views):
        """
        Calls wizard to import orders for store view

        :param store_views: List of active records of store views
        """
        pass

    @classmethod
    @ModelView.button_action('magento.wizard_export_order_status')
    def export_order_status_button(cls, store_views):
        """
        Calls wizard to export order status for store view

        :param store_views: List of active records of store views
        """
        pass

    def import_order_from_store_view(self):
        """
        Imports sale from store view

        :return: List of active record of sale imported
        """
        Sale = Pool().get('sale.sale')
        MagentoOrderState = Pool().get('magento.order_state')

        new_sales = []
        channel = self.channel
        with Transaction().set_context({
            'magento_channel': channel.id,
            'magento_website': self.website.id,
            'magento_store_view': self.id,
        }):

            order_states = MagentoOrderState.search([
                ('channel', '=', channel.id),
                ('use_for_import', '=', True)
            ])
            order_states_to_import_in = map(
                lambda state: state.code, order_states
            )

            if not order_states_to_import_in:
                self.raise_user_error("states_not_found")

            with magento.Order(
                channel.magento_url, channel.magento_api_user,
                channel.magento_api_key
            ) as order_api:
                # Filter orders with date and store_id using list()
                # then get info of each order using info()
                # and call find_or_create_using_magento_data on sale
                filter = {
                    'store_id': {'=': self.magento_id},
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

    def export_order_status(self, store_views=None):
        """
        Export sales orders status to magento.

        :param store_views: List of active record of store view
        """
        if store_views is None:
            store_views = self.search([])

        for store_view in store_views:
            store_view.export_order_status_for_store_view()

    def export_order_status_for_store_view(self):
        """
        Export sale orders to magento for the current store view.
        If last export time is defined, export only those orders which are
        updated after last export time.

        :return: List of active records of sales exported
        """
        Sale = Pool().get('sale.sale')

        exported_sales = []
        domain = [('magento_store_view', '=', self.id)]

        if self.last_order_export_time:
            domain = [('write_date', '>=', self.last_order_export_time)]

        sales = Sale.search(domain)

        self.last_order_export_time = datetime.utcnow()
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

        channel = self.channel

        sale_domain = [
            ('magento_store_view', '=', self.id),
            ('shipment_state', '=', 'sent'),
            ('magento_id', '!=', None),
            ('shipments', '!=', None),
        ]

        if self.last_shipment_export_time:
            sale_domain.append(
                ('write_date', '>=', self.last_shipment_export_time)
            )

        sales = Sale.search(sale_domain)

        self.last_shipment_export_time = datetime.utcnow()
        self.save()

        for sale in sales:
            # Get the increment id from the sale reference
            increment_id = sale.reference[
                len(channel.magento_order_prefix): len(sale.reference)
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
                        channel.magento_url, channel.magento_api_user,
                        channel.magento_api_key
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

                        if self.export_tracking_information and (
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

    @classmethod
    def get_current_store_view(cls):
        """Helper method to get the current store view.
        """
        return cls(Transaction().context.get('magento_store_view'))


class StorePriceTier(ModelSQL, ModelView):
    """Price Tiers for store

    This model stores the default price tiers to be used while sending
    tier prices for a product from Tryton to Magento.
    The product also has a similar table like this. If there are no entries in
    the table on product, then these tiers are used.
    """
    __name__ = 'magento.store.price_tier'

    store = fields.Many2One(
        'magento.website.store', 'Magento Store', required=True, readonly=True,
    )
    quantity = fields.Float('Quantity', required=True)

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(StorePriceTier, cls).__setup__()
        cls._sql_constraints += [
            (
                'store_quantity_unique', 'UNIQUE(store, quantity)',
                'Quantity in price tiers must be unique for a store'
            )
        ]


class TestConnectionStart(ModelView):
    "Test Connection"
    __name__ = 'magento.wizard_test_connection.start'


class TestConnection(Wizard):
    """
    Test Connection Wizard

    Test the connection to magento channel(s)
    """
    __name__ = 'magento.wizard_test_connection'

    start = StateView(
        'magento.wizard_test_connection.start',
        'magento.wizard_test_connection_view_form',
        [
            Button('Ok', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """Test the connection and show the user appropriate message

        :param data: Wizard data
        """
        return {}


class ImportWebsitesStart(ModelView):
    "Import Websites Start View"
    __name__ = 'magento.wizard_import_websites.start'

    message = fields.Text("Message", readonly=True)


class ImportWebsites(Wizard):
    """
    Import Websites Wizard

    Import the websites and their stores/view from magento
    """
    __name__ = 'magento.wizard_import_websites'

    start = StateView(
        'magento.wizard_import_websites.start',
        'magento.wizard_import_websites_view_form',
        [
            Button('Ok', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """
        Import the websites, store and store views and show user a
        confirmation message

        :param data: Wizard data
        """
        return {
            'message': "This wizard has imported all the websites for this " +
                "magento channel. It has also imported all the stores and " +
                "store views related to the websites imported. If any of " +
                "the records existed already, it wont be imported."
        }


class ImportOrderStatesStart(ModelView):
    "Import Order States Start"
    __name__ = 'magento.wizard_import_order_states.start'


class ImportOrderStates(Wizard):
    """
    Wizard to import order states for channel
    """
    __name__ = 'magento.wizard_import_order_states'

    start = StateView(
        'magento.wizard_import_order_states.start',
        'magento.wizard_import_order_states_start_view_form',
        [
            Button('Ok', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """
        Import order states and show the user appropriate message

        :param data: Wizard data
        """
        return {}


class ImportCarriersStart(ModelView):
    "Import Carriers Start"
    __name__ = 'magento.wizard_import_carriers.start'

    message = fields.Text("Message", readonly=True)


class ImportCarriers(Wizard):
    """
    Wizard to import carriers / shipping methods for channel
    """
    __name__ = 'magento.wizard_import_carriers'

    start = StateView(
        'magento.wizard_import_carriers.start',
        'magento.wizard_import_carriers_start_view_form',
        [
            Button('Ok', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """
        Import carriers and show the user appropriate message

        :param data: Wizard data
        """
        return {
            'message': "This wizard has imported all the carriers / " +
                "shipping methods for this magento channel. You should now " +
                "configure the imported carriers / shipping methods to " +
                "match the shipment carriers in Tryton to allow seamless " +
                "synchronisation of tracking information."
        }


class ExportInventoryStart(ModelView):
    "Export Inventory Start View"
    __name__ = 'magento.wizard_export_inventory.start'


class ExportInventory(Wizard):
    """
    Export Inventory Wizard

    Export product stock information to magento for the current website
    """
    __name__ = 'magento.wizard_export_inventory'

    start = StateView(
        'magento.wizard_export_inventory.start',
        'magento.wizard_export_inventory_view_start_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'export_', 'tryton-ok', default=True),
        ]
    )

    export_ = StateAction('product.act_template_form')

    def do_export_(self, action):
        """Handles the transition"""

        Website = Pool().get('magento.instance.website')

        website = Website(Transaction().context.get('active_id'))

        product_templates = website.export_inventory_to_magento()

        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', map(int, product_templates))])
        return action, {}

    def transition_export_(self):
        return 'end'


class ExportTierPricesStart(ModelView):
    "Export Tier Prices Start View"
    __name__ = 'magento.wizard_export_tier_prices.start'


class ExportTierPricesStatus(ModelView):
    "Export Tier Prices Status View"
    __name__ = 'magento.wizard_export_tier_prices.status'

    products_count = fields.Integer('Products Count', readonly=True)


class ExportTierPrices(Wizard):
    """
    Export Tier Prices Wizard

    Export product tier prices to magento for the current store
    """
    __name__ = 'magento.wizard_export_tier_prices'

    start = StateView(
        'magento.wizard_export_tier_prices.start',
        'magento.wizard_export_tier_prices_view_start_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'export_', 'tryton-ok', default=True),
        ]
    )

    export_ = StateView(
        'magento.wizard_export_tier_prices.status',
        'magento.wizard_export_tier_prices_view_status_form',
        [
            Button('OK', 'end', 'tryton-cancel'),
        ]
    )

    def default_export_(self, fields):
        """Export price tiers and return count of products"""
        Store = Pool().get('magento.website.store')

        store = Store(Transaction().context.get('active_id'))

        return {
            'products_count': store.export_tier_prices_to_magento()
        }


class ExportShipmentStatusStart(ModelView):
    "Export Shipment Status View"
    __name__ = 'magento.wizard_export_shipment_status.start'

    message = fields.Text("Message", readonly=True)


class ExportShipmentStatus(Wizard):
    """
    Export Shipment Status Wizard

    Exports shipment status for sale orders related to current store view
    """
    __name__ = 'magento.wizard_export_shipment_status'

    start = StateView(
        'magento.wizard_export_shipment_status.start',
        'magento.wizard_export_shipment_status_view_start_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'export_', 'tryton-ok', default=True),
        ]
    )

    export_ = StateAction('sale.act_sale_form')

    def default_start(self, data):
        """
        Sets default data for wizard

        :param data: Wizard data
        """
        return {
            'message': "This wizard will export shipment status for all the " +
                "shipments related to this store view. To export tracking " +
                "information also for these shipments please check the " +
                "checkbox for Export Tracking Information on Store View."
        }

    def do_export_(self, action):
        """Handles the transition"""

        StoreView = Pool().get('magento.store.store_view')

        storeview = StoreView(Transaction().context.get('active_id'))

        sales = storeview.export_shipment_status_to_magento()

        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', map(int, sales))]
        )
        return action, {}

    def transition_export_(self):
        return 'end'


class MagentoException(ModelSQL, ModelView):
    """
    Magento Exception model
    """
    __name__ = 'magento.exception'

    origin = fields.Reference(
        "Origin", selection='models_get', select=True,
    )
    log = fields.Text('Exception Log')

    @classmethod
    def models_get(cls):
        '''
        Return valid models allowed for origin
        '''
        return [
            ('sale.sale', 'Sale'),
            ('sale.line', 'Sale Line'),
        ]
