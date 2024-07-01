from odoo.tests import HttpCase, tagged

@tagged('-at_install', 'post_install')
class TestSalesOrderController(HttpCase):

    def setUp(self):
        super(TestSalesOrderController, self).setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com'
        })
        self.product_1 = self.env['product.product'].create({
            'name': 'Test Product 1',
            'list_price': 100.0
        })
        self.product_2 = self.env['product.product'].create({
            'name': 'Test Product 2',
            'list_price': 200.0
        })

    def test_01_create_sales_order(self):
        order_lines = [
            {"product_id": self.product_1.id, "product_uom_qty": 1, "price_unit": 100.0},
            {"product_id": self.product_2.id, "product_uom_qty": 2, "price_unit": 200.0}
        ]
        data = {
            'partner_id': self.partner.id,
            'order_lines': order_lines
        }
        
        response = self.url_open('/api/sales_order/create', json=data)
        result = response.json()

        self.assertTrue(result.get('success'))
        order_id = result.get('order_id')
        self.assertTrue(order_id)

        order = self.env['sale.order'].browse(order_id)
        self.assertEqual(order.partner_id.id, self.partner.id)
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(order.order_line[0].product_id.id, self.product_1.id)
        self.assertEqual(order.order_line[1].product_id.id, self.product_2.id)
        self.assertEqual(order.order_line[0].product_uom_qty, 1)
        self.assertEqual(order.order_line[1].product_uom_qty, 2)
        self.assertEqual(order.order_line[0].price_unit, 100.0)
        self.assertEqual(order.order_line[1].price_unit, 200.0)

    def test_02_get_sales_order(self):
        # First, create a sales order to retrieve
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_1.id,
                    'product_uom_qty': 1,
                    'price_unit': 100.0
                }),
                (0, 0, {
                    'product_id': self.product_2.id,
                    'product_uom_qty': 2,
                    'price_unit': 200.0
                })
            ]
        })

        response = self.url_open(f'/api/sales_order/{order.id}')
        result = response.json()

        self.assertEqual(result['id'], order.id)
        self.assertEqual(result['partner_id'], self.partner.id)
        self.assertEqual(len(result['order_line']), 2)
        self.assertEqual(result['order_line'][0]['product_id'], self.product_1.id)
        self.assertEqual(result['order_line'][1]['product_id'], self.product_2.id)
        self.assertEqual(result['order_line'][0]['product_uom_qty'], 1)
        self.assertEqual(result['order_line'][1]['product_uom_qty'], 2)
        self.assertEqual(result['order_line'][0]['price_unit'], 100.0)
        self.assertEqual(result['order_line'][1]['price_unit'], 200.0)
