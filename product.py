# -*- coding: UTF-8 -*-
'''
    product

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
'''
import magento
from trytond.model import ModelSQL, ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder
from trytond.pool import PoolMeta, Pool
from decimal import Decimal


__all__ = [
    'Category', 'MagentoInstanceCategory', 'Product',
    'ProductSaleChannelListing',
    'ProductPriceTier', 'UpdateCatalogStart',
    'UpdateCatalog', 'ImportCatalogStart', 'ImportCatalog',
    'ExportCatalogStart', 'ExportCatalog'
]
__metaclass__ = PoolMeta


class Category:
    "Product Category"
    __name__ = "product.category"

    magento_ids = fields.One2Many(
        'magento.instance.product_category', 'category',
        'Magento IDs', readonly=True,
    )

    @classmethod
    def create_tree_using_magento_data(cls, category_tree):
        """
        Create the categories from the category tree

        :param category_tree: Category Tree from Magento
        """
        # Create the root
        root_category = cls.find_or_create_using_magento_data(
            category_tree
        )
        for child in category_tree['children']:
            cls.find_or_create_using_magento_data(
                child, parent=root_category
            )
            if child['children']:
                cls.create_tree_using_magento_data(child)

    @classmethod
    def find_or_create_using_magento_data(
        cls, category_data, parent=None
    ):
        """
        Find or Create category using Magento Database

        :param category_data: Category Data from Magento
        :param parent: Browse record of Parent if present, else None
        :returns: Active record of category found/created
        """
        category = cls.find_using_magento_data(
            category_data
        )

        if not category:
            category = cls.create_using_magento_data(
                category_data, parent
            )
        return category

    @classmethod
    def find_or_create_using_magento_id(
        cls, magento_id, parent=None
    ):
        """
        Find or Create Category Using Magento ID of Category

        :param category_data: Category Data from Magento
        :param parent: Browse record of Parent if present, else None
        :returns: Active record of category found/created
        """
        Channel = Pool().get('sale.channel')

        category = cls.find_using_magento_id(magento_id)
        if not category:
            channel = Channel(
                Transaction().context.get('magento_channel')
            )

            with magento.Category(
                channel.magento_url, channel.magento_api_user,
                channel.magento_api_key
            ) as category_api:
                category_data = category_api.info(magento_id)

            category = cls.create_using_magento_data(
                category_data, parent
            )

        return category

    @classmethod
    def find_using_magento_data(cls, category_data):
        """
        Find category using Magento Data

        :param category_data: Category Data from Magento
        :returns: Active record of category found or None
        """
        MagentoCategory = Pool().get('magento.instance.product_category')

        records = MagentoCategory.search([
            ('magento_id', '=', int(category_data['category_id'])),
            ('channel', '=', Transaction().context.get('magento_channel'))
        ])
        return records and records[0].category or None

    @classmethod
    def find_using_magento_id(cls, magento_id):
        """
        Find category using Magento ID or Category

        :param magento_id: Category ID from Magento
        :type magento_id: Integer
        :returns: Active record of Category Found or None
        """
        MagentoCategory = Pool().get('magento.instance.product_category')

        records = MagentoCategory.search([
            ('magento_id', '=', magento_id),
            ('channel', '=', Transaction().context.get('magento_channel'))
        ])

        return records and records[0].category or None

    @classmethod
    def create_using_magento_data(cls, category_data, parent=None):
        """
        Create category using magento data

        :param category_data: Category Data from magento
        :param parent: Browse record of Parent if present, else None
        :returns: Active record of category created
        """
        category, = cls.create([{
            'name': category_data['name'],
            'parent': parent,
            'magento_ids': [('create', [{
                'magento_id': int(category_data['category_id']),
                'channel': Transaction().context.get('magento_channel'),
            }])],
        }])

        return category


class MagentoInstanceCategory(ModelSQL, ModelView):
    """
    Magento Instance - Product Category Store

    This model keeps a record of a category's association with an Instance
    and the ID of the category on that channel
    """
    __name__ = "magento.instance.product_category"

    magento_id = fields.Integer(
        'Magento ID', readonly=True, required=True, select=True
    )
    channel = fields.Many2One(
        'sale.channel', 'Magento Instance', readonly=True,
        required=True, select=True
    )
    category = fields.Many2One(
        'product.category', 'Product Category', readonly=True,
        required=True, select=True
    )

    @classmethod
    def __setup__(cls):
        '''
        Setup the class and define constraints
        '''
        super(MagentoInstanceCategory, cls).__setup__()
        cls._sql_constraints += [
            (
                'magento_id_instance_unique',
                'UNIQUE(magento_id, channel)',
                'Each category in an channel must be unique!'
            )
        ]


class ProductSaleChannelListing:
    "Product Sale Channel"
    __name__ = 'product.product.channel_listing'

    price_tiers = fields.One2Many(
        'product.price_tier', 'template', 'Price Tiers'
    )
    magento_product_type = fields.Selection([
        (None, ''),
        ('simple', 'Simple'),
        ('configurable', 'Configurable'),
        ('grouped', 'Grouped'),
        ('bundle', 'Bundle'),
        ('virtual', 'Virtual'),
        ('downloadable', 'Downloadable'),
    ], 'Magento Product Type', readonly=True)


class Product:
    "Product"

    __name__ = "product.product"

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Product, cls).__setup__()
        cls._error_messages.update({
            "invalid_category": 'Category "%s" must have a magento category '
                'associated',
            "invalid_product": 'Product "%s" already has a magento product '
                'associated',
            "missing_product_code": 'Product "%s" has a missing code.',
        })

    @classmethod
    def find_or_create_using_magento_id(cls, magento_id):
        """
        Find or create a product using magento ID. This method looks
        for an existing product using the magento ID provided. If found, it
        returns the template found, else creates a new one and returns that

        :param magento_id: Product ID from Magento
        :returns: Active record of Product Created
        """
        Channel = Pool().get('sale.channel')

        # TODO: handle case when same product (SKU matched)
        # from different store, then add channel to product listing
        product_template = cls.find_using_magento_id(magento_id)

        if not product_template:
            # if product is not found get the info from magento and
            # delegate to create_using_magento_data
            channel = Channel(Transaction().context.get('magento_channel'))

            with magento.Product(
                channel.magento_url, channel.magento_api_user,
                channel.magento_api_key
            ) as product_api:
                product_data = product_api.info(magento_id)

            product = cls.create_using_magento_data(product_data)

        return product

    @classmethod
    def find_using_magento_id(cls, magento_id):
        """
        Find a product template corresponding to the magento ID provided. If
        found return that else None

        :param magento_id: Product ID from Magento
        :returns: Product created for the Record
        """
        SaleChannelListing = Pool().get('product.product.channel_listing')

        records = SaleChannelListing.search([
            ('channel', '=', Transaction().context.get('magento_channel')),
            ('product_identifier', '=', magento_id),
        ])

        return records and records[0].product or None

    @classmethod
    def find_or_create_using_magento_data(cls, product_data):
        """
        Find or create a product template using magento data provided.
        This method looks for an existing template using the magento ID From
        data provided. If found, it returns the template found, else creates
        a new one and returns that

        :param product_data: Product Data From Magento
        :returns: Browse record of product found/created
        """
        product_template = cls.find_using_magento_data(product_data)

        if not product_template:
            product_template = cls.create_using_magento_data(product_data)

        return product_template

    @classmethod
    def find_using_magento_data(cls, product_data):
        """
        Find a product template corresponding to the magento data provided.
        If found return that else None

        :param product_data: Category Data from Magento
        :returns: Active record of product found or None
        """
        return cls.find_using_magento_id(product_data['product_id'])

    @classmethod
    def extract_product_values_from_data(cls, product_data):
        """
        Extract product values from the magento data, used for both
        creation/updation of product. This method can be overwritten by
        custom modules to store extra info to a product

        :param: product_data
        :returns: Dictionary of values
        """
        Channel = Pool().get('sale.channel')

        channel = Channel(Transaction().context.get('magento_channel'))
        return {
            'name': product_data.get('name') or
                ('SKU: ' + product_data.get('sku')),
            'list_price': Decimal(
                product_data.get('special_price') or
                product_data.get('price') or
                0.00
            ),
            'cost_price': Decimal(product_data.get('cost') or 0.00),
            'default_uom': channel.magento_default_uom.id,
            'salable': True,
            'sale_uom': channel.magento_default_uom.id,
            'account_expense':
                channel.magento_default_account_expense.id,
            'account_revenue':
                channel.magento_default_account_revenue.id,
        }

    @classmethod
    def create_using_magento_data(cls, product_data):
        """
        Create a new product with the `product_data` from magento.This method
        also looks for the category of the product. If found, it uses that
        category to assign the product to. If no category is found, it assigns
        the product to `Unclassified Magento Product` category

        :param product_data: Product Data from Magento
        :returns: Browse record of product created
        """
        Template = Pool().get('product.template')
        Category = Pool().get('product.category')

        # Get only the first category from the list of categories
        # If no category is found, put product under unclassified category
        # which is created by default data
        if product_data.get('categories'):
            category = Category.find_or_create_using_magento_id(
                int(product_data['categories'][0])
            )
        else:
            categories = Category.search([
                ('name', '=', 'Unclassified Magento Products')
            ])
            category = categories[0]

        product_template_values = cls.extract_product_values_from_data(
            product_data
        )
        product_template_values.update({
            'products': [('create', [{
                'description': product_data['description'],
                'code': product_data['sku'],
                'channel_listings': [('create', [{
                    'product_identifier': product_data['product_id'],
                    'channel': Transaction().context.get('magento_channel'),
                    'magento_product_type': product_data['type'],
                }])],
            }])],
            'category': category.id,
        })
        product_template, = Template.create([product_template_values])

        return product_template.products[0]

    def update_from_magento(self):
        """
        Update product using magento ID for that product

        :returns: Active record of product updated
        """
        Channel = Pool().get('sale.channel')
        SaleChannelListing = Pool().get('product.product.channel_listing')

        channel = Channel(Transaction().context.get('magento_channel'))

        with magento.Product(
            channel.magento_url, channel.magento_api_user,
            channel.magento_api_key
        ) as product_api:
            channel_listing, = SaleChannelListing.search([
                ('product', '=', self.id),
                ('channel', '=', channel.id),
            ])
            product_data = product_api.info(
                channel_listing.product_identifier
            )

        return self.update_from_magento_using_data(product_data)

    def update_from_magento_using_data(self, product_data):
        """
        Update product using magento data

        :param product_data: Product Data from magento
        :returns: Active record of product updated
        """
        Template = Pool().get('product.template')

        product_template_values = self.extract_product_values_from_data(
            product_data
        )
        product_template_values.update({
            'products': [('write', map(int, self.products), {
                'description': product_data['description'],
                'code': product_data['sku'],
            })]
        })
        Template.write([self], product_template_values)

        return self

    def get_product_values_for_export_to_magento(self, categories, channels):
        """Creates a dictionary of values which have to exported to magento for
        creating a product

        :param categories: List of Browse record of categories
        :param channels: List of Browse record of channels
        """
        return {
            'categories': map(
                lambda mag_categ: mag_categ.magento_id,
                categories[0].magento_ids
            ),
            'websites': map(lambda c: c.magento_website_id, channels),
            'name': self.name,
            'description': self.description or self.name,
            'short_description': self.description or self.name,
            'status': '1',
            'visibility': '4',
            'price': float(str(self.list_price)),
            'tax_class_id': '1',    # FIXME
        }

    def export_to_magento(self, category):
        """Export the current product to the magento category corresponding to
        the given `category` under the current website in context

        :param category: Active record of category to which the product has
                         to be exported
        :return: Active record of product
        """
        Channel = Pool().get('sale.channel')
        SaleChannelListing = Pool().get('product.product.channel_listing')

        channel = Channel(Transaction().context['magento_channel'])

        if not category.magento_ids:
            self.raise_user_error(
                'invalid_category', (category.complete_name,)
            )

        listing = SaleChannelListing.search([
            ('channel', '=', channel.id),
            ('product', '=', self.id),
        ])

        if listing:
            self.raise_user_error(
                'invalid_product', (self.name,)
            )

        if not self.products[0].code:
            self.raise_user_error(
                'missing_product_code', (self.name,)
            )

        with magento.Product(
            channel.magento_url, channel.magento_api_user,
            channel.magento_api_key
        ) as product_api:
            # We create only simple products on magento with the default
            # attribute set
            # TODO: We have to call the method from core API extension
            # because the method for catalog create from core API does not seem
            # to work. This should ideally be from core API rather than
            # extension
            magento_id = product_api.call(
                'ol_catalog_product.create', [
                    'simple',
                    int(Transaction().context['magento_attribute_set']),
                    self.products[0].code,
                    self.get_product_values_for_export_to_magento(
                        [category], [channel]
                    )
                ]
            )
            SaleChannelListing.create([{
                'product_identifier': str(magento_id),
                'channel': channel.id,
                'product': self.id,
                'magento_product_type': 'simple',
            }])
        return self


class ProductPriceTier(ModelSQL, ModelView):
    """Price Tiers for product

    This model stores the price tiers to be used while sending
    tier prices for a product from Tryton to Magento.
    """
    __name__ = 'product.price_tier'
    _rec_name = 'quantity'

    template = fields.Many2One(
        'product.template', 'Product Template', required=True, readonly=True,
    )
    quantity = fields.Float(
        'Quantity', required=True
    )
    price = fields.Function(fields.Numeric('Price'), 'get_price')

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(ProductPriceTier, cls).__setup__()
        cls._sql_constraints += [
            (
                'template_quantity_unique', 'UNIQUE(template, quantity)',
                'Quantity in price tiers must be unique for a product'
            )
        ]

    def get_price(self, name):
        """Calculate the price of the product for quantity set in record

        :param name: Name of field
        """
        Channel = Pool().get('sale.channel')

        if not Transaction().context.get('magento_channel'):
            return 0

        channel = Channel(Transaction().context['magento_channel'])
        return channel.price_list.compute(
            None, self.template, self.template.list_price, self.quantity,
            channel.magento_default_uom
        )


class UpdateCatalogStart(ModelView):
    'Update Catalog View'
    __name__ = 'magento.instance.update_catalog.start'


class UpdateCatalog(Wizard):
    '''
    Update Catalog

    This is a wizard to update already imported products
    '''
    __name__ = 'magento.instance.update_catalog'

    start = StateView(
        'magento.instance.update_catalog.start',
        'magento.update_catalog_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'update_', 'tryton-ok', default=True),
        ]
    )
    update_ = StateAction('product.act_template_form')

    def do_update_(self, action):
        """Handles the transition"""

        Channel = Pool().get('sale.channel')

        channel = Channel(Transaction().context.get('active_id'))

        product_template_ids = self.update_products(channel)

        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', product_template_ids)])
        return action, {}

    def transition_import_(self):
        return 'end'

    def update_products(self, channel):
        """
        Updates products for current website

        :param website: Browse record of website
        :return: List of product templates IDs
        """
        products = []
        with Transaction().set_context({'magento_channel': channel.id}):
            for listing in channel.product_listings:
                products.append(
                    listing.product.update_from_magento()
                )

        return map(int, products)


class ImportCatalogStart(ModelView):
    'Import Catalog View'
    __name__ = 'magento.instance.import_catalog.start'


class ImportCatalog(Wizard):
    '''
    Import Catalog

    This is a wizard to import Products from a Magento Website. It opens up
    the list of products after the import has been completed.
    '''
    __name__ = 'magento.instance.import_catalog'

    start = StateView(
        'magento.instance.import_catalog.start',
        'magento.instance_import_catalog_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'import_', 'tryton-ok', default=True),
        ]
    )
    import_ = StateAction('product.act_template_form')

    def do_import_(self, action):
        """Handles the transition"""

        Website = Pool().get('magento.instance.website')

        website = Website(Transaction().context.get('active_id'))

        self.import_category_tree(website)
        product_ids = self.import_products(website)
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', product_ids)])
        return action, {}

    def transition_import_(self):
        return 'end'

    def import_category_tree(self, website):
        """
        Imports the category tree and creates categories in a hierarchy same as
        that on Magento

        :param website: Active record of website
        """
        Category = Pool().get('product.category')

        channel = website.channel
        Transaction().set_context({'magento_channel': channel.id})

        with magento.Category(
            channel.magento_url, channel.magento_api_user,
            channel.magento_api_key
        ) as category_api:
            category_tree = category_api.tree(website.magento_root_category_id)
            Category.create_tree_using_magento_data(category_tree)

    def import_products(self, channel):
        """
        Imports products for the current channel

        :param website: Active record of website
        """
        Product = Pool().get('product.template')

        Transaction().set_context({
            'magento_channel': channel.id,
        })
        with magento.Product(
            channel.magento_url, channel.magento_api_user,
            channel.magento_api_key
        ) as product_api:
            magento_products = product_api.list()

            products = []
            for magento_product in magento_products:
                products.append(
                    Product.find_or_create_using_magento_data(
                        magento_product
                    )
                )

        return map(int, products)


class ExportCatalogStart(ModelView):
    'Export Catalog View'
    __name__ = 'magento.website.export_catalog.start'

    @classmethod
    def get_attribute_sets(cls):
        """Get the list of attribute sets from magento for the current website

        :return: Tuple of attribute sets where each tuple consists of (ID,Name)
        """
        Website = Pool().get('magento.instance.website')

        if not Transaction().context.get('active_id'):
            return []

        website = Website(Transaction().context['active_id'])
        channel = website.channel

        with magento.ProductAttributeSet(
            channel.magento_url, channel.magento_api_user,
            channel.magento_api_key
        ) as attribute_set_api:
            attribute_sets = attribute_set_api.list()

        return [(
            attribute_set['set_id'], attribute_set['name']
        ) for attribute_set in attribute_sets]

    category = fields.Many2One(
        'product.category', 'Magento Category', required=True,
        domain=[('magento_ids', 'not in', [])],
    )
    products = fields.Many2Many(
        'product.template', None, None, 'Products', required=True,
        domain=[('magento_ids', '=', None)],
    )
    attribute_set = fields.Selection(
        [], 'Attribute Set', required=True,
    )

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        """This method is overridden to populate the selection field for
        attribute_set with the attribute sets from the current website's
        counterpart on magento.
        This overridding has to be done because `active_id` is not available
        if the meth:get_attribute_sets is called directly from the field.
        """
        rv = super(ExportCatalogStart, cls).fields_view_get(view_id, view_type)
        rv['fields']['attribute_set']['selection'] = cls.get_attribute_sets()
        return rv


class ExportCatalog(Wizard):
    '''Export catalog

    Export the products selected to the selected category for this website
    '''
    __name__ = 'magento.website.export_catalog'

    start = StateView(
        'magento.website.export_catalog.start',
        'magento.website_export_catalog_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'export_', 'tryton-ok', default=True),
        ]
    )
    export_ = StateAction('product.act_template_form')

    def do_export_(self, action):
        """
        Export the products selected to the selected category for this website
        """
        Website = Pool().get('magento.instance.website')

        website = Website(Transaction().context['active_id'])

        with Transaction().set_context({
            'magento_website': website.id,
            'magento_attribute_set': self.start.attribute_set,
        }):
            for product in self.start.products:
                product.export_to_magento(self.start.category)

        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', map(int, self.start.products))])

        return action, {}

    def transition_export_(self):
        return 'end'
