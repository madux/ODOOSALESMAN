from odoo import http
from odoo.http import request
import json
import logging
from odoo.addons.eha_auth.controllers.helpers import validate_token, validate_secret_key, invalid_response, valid_response
import werkzeug.wrappers
from odoo import fields
from odoo.exceptions import ValidationError


logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

class SalesManController(http.Controller):

    @http.route('/api/v1/invoice-validation', type='json', auth='user', methods=['POST'], csrf=False)
    def validate_invoice_api(self, **kwargs):
        
        '''url = "http://localhost:8069/api/v1/invoice-validation"
        User must provide either invoice_number or invoice_id
        payload = {
            "invoice_number": "INV/2024/00001",
            "invoice_id": 2, # 
            "is_register_payment": True or False, # 
            "journal_id": Null or Not Null, Not null if is_register_payment is True# 
        }'''
        data = json.loads(request.httprequest.data)
        invoice_number = data.get('invoice_number')
        invoice_id = data.get('invoice_id')
        journal_id = data.get('journal_id')
        is_register_payment = data.get('is_register_payment')
        if not invoice_number or not invoice_id:
            return invalid_response(
                "missing_parameter",
                "Missing required parameters"
                " [invoice_number, invoice_id]",
                200,
            )
        journalid = None
        if is_register_payment:
            if not journal_id:
                return invalid_response(
                    "missing_parameter",
                    "Please provide a journal id"
                    " [journal_id]",
                    200,
                )
            journal = request.env['account.journal'].search([('id', '=', int(journal_id))], limit=1)
            if not journal:
                return invalid_response(
                    "missing_parameter",
                    "Provide Journal id does not exist in the database"
                    " [journal_id]",
                    200,
                )
            journalid = journal.id
        inv = request.env['account.move'].sudo().search([
            '|', ('name', '=', invoice_number), 
            ('id', '=', invoice_id)])
        if inv:
            if inv.state == "draft":
                inv.action_post()
            if is_register_payment:
                journalid = request.env['account.journal'].sudo().browse([8])
                self.validate_invoice_and_post_journal(journalid, inv)
            return {
                'success': True, 
                'data': {'invoice_id': inv.id, 'invoice_number': inv.name}
                }
        else:
            return {
                    'success': False, 
                    'data': {},
                    'message': 'No invoice found'
                    }
            
    @http.route('/api/get-product', type='json', auth='user', methods=['GET'], csrf=False)
    def get_products(self, **kwargs):
        '''
        {
            'product_id': 1 or null
        }
        if product id, returns the specific product by id else returns all products
        '''
        try:
            data = json.loads(request.httprequest.data) # kwargs
            product_id = data.get('product_id')
            if product_id and type(product_id) != int:
                return invalid_response(
                    "Product id",
                    "Product ID provided must be an integer"
                    "[product_id]",
                    400,
                )
            domain = [('id', '=', product_id)] if product_id else []
            products = request.env['product.product'].search(domain)
            if products:
                data = []
                for prd in products:
                    data.append({
                        'id': prd.id, 'name': prd.name, 'sale_price': prd.list_price
                    })
                return {
                    'success': True, 
                    'data':data
                    }
            else:
                return {
                    'success': False, 
                    'message': 'No product found'}   
        
        except Exception as e:
            return {
                    'success': False, 
                    'message': str(e)}
            
    @http.route('/api/get-product-availability', type='json', auth='user', methods=['GET'], csrf=False)
    def get_product_availability(self, **kwargs):
        '''
        {
            'product_id': 1, compulsory,
            'requesting_qty': 2, # pass the requesting quantity
        }
        if product id, returns the specific product quantities based on the user company warehouse
        '''
        try:
            data = json.loads(request.httprequest.data) # kwargs
            product_id = data.get('product_id')
            qty = data.get('requesting_qty')
            if product_id and type(product_id) != int:
                return invalid_response(
                    "Product id",
                    "Product ID provided must be an integer"
                    "[product_id]",
                    400,
                )
            domain = [('active', '=', True),('id', '=', product_id)]
            product = request.env['product.product'].search(domain, limit=1)
            if product:
                warehouse_domain = [('company_id', '=', request.env.user.company_id.id)]
                warehouse_location_id = request.env['stock.warehouse'].search(warehouse_domain, limit=1)
                stock_location_id = warehouse_location_id.lot_stock_id
                # should_bypass_reservation : False
                if product.detailed_type in ['product']:
                    total_availability = request.env['stock.quant'].sudo()._get_available_quantity(product, stock_location_id, allow_negative=False) or 0.0
                    product_qty = float(qty) if qty else 0
                    if product_qty > total_availability:
                        return {
                            "success": False,
                            "data": {'total_quantity': total_availability},
                            "message": f"Selected product quantity ({product_qty}) is higher than the Available Quantity. Available quantity is {total_availability}", 
                            }
                    else:
                        return {
                            "status": True,
                            "message": "The requesting quantity of Product is available", 
						}
                else:
                    return {
						"status": False,
						"message": "Product selected for check must be a storable product and not service", 
						}
            else:
                return {
                    'success': False, 
                    'message': 'No product found'}   
        
        except Exception as e:
            return {
                    'success': False, 
                    'message': str(e)
                    }
            
    @http.route('/api/get-branch', type='json', auth='user', methods=['GET'], csrf=False)
    def get_branch(self, **kwargs):
        '''
        {
            'branch_id': 1 or null
        }
        if product id, returns the specific product by id else returns all products
        '''
        try:
            data = json.loads(request.httprequest.data) # kwargs
            branch_id = data.get('branch_id')
            if branch_id and type(branch_id) != int:
                return invalid_response(
                    "branch id",
                    "branch ID provided must be an integer"
                    "[branch_id]",
                    400,
                )
            domain = [('id', '=', branch_id)] if branch_id else []
            branch = request.env['multi.branch'].search(domain)
            if branch:
                data = []
                for prd in branch:
                    data.append({
                        'id': prd.id, 'name': prd.name
                    })
                return {
                    'success': True, 
                    'data':data
                    }
            else:
                return {
                    'success': False, 
                    'message': 'No branch found'}   
        
        except Exception as e:
            return {
                    'success': False, 
                    'message': str(e)}
            
    @http.route('/api/contact-operation', type='json', auth='user', methods=['GET', 'POST'], csrf=False)
    def get_contacts(self, **kwargs):
        '''
        {
            'contact_id': 1 or null,
            'contact_name': Moses Abraham or null,
            'id': cnt.id, 
            'to_create_contact': True, # (creates a new contact if contact id or name is not found), 
            'contact_name': 'peter Maduka Sopulu' or None, 
            'address1': 'No. 45 Maduka Sopulu Street'
            'address2': 'No. 46 Maduka Sopulu Street'
            'phone': '09092998888',
            'email': 'maduka@gmail.com',
        }
        if contact id, returns the specific contact by id else returns all contacts
        '''
        try:
            data = json.loads(request.httprequest.data) # kwargs
            contact_id = data.get('contact_id')
            address1 = data.get('address1')
            address2 = data.get('address2')
            phone = data.get('phone')
            email = data.get('email')
            contact_name = data.get('contact_name')
            to_create_contact = data.get('to_create_contact')
            if contact_id and type(contact_id) != int:
                return invalid_response(
                    "contact id",
                    "contact ID provided must be an integer"
                    "[contact_id]",
                    400,
                )
            domain = ['|', ('id', '=', contact_id), ('name', '=', contact_name)] if contact_id or contact_name else []
            contact = request.env['res.partner'].search(domain)
            address = address1 or address2
            if (not contact) and to_create_contact:
                if not contact_name or not address or not phone or not email:
                    return {
                    'success': False, 
                    'message': 'Please provide the following fields; contact name, address, phone and email'
                    }
                contact_vals = {
                    'name': contact_name, 
                    'street': address1, 
                    'street2': address2,
                    'phone': phone,
                    'email': email,
                }
                contact = request.env['res.partner'].create(contact_vals)
            if contact:
                data = []
                for cnt in contact:
                    data.append({
                        'id': cnt.id, 
                        'contact_name': cnt.name or None, 
                        'address1': cnt.street or None, 
                        'address2': cnt.street2 or None,
                        'phone': cnt.phone or None,
                        'email': cnt.email or None,
                    })
                return {
                    'success': True, 
                    'data':data
                    }
            else:
                return {
                    'success': False, 
                    'message': 'No contact found on the system'}   
        
        except Exception as e:
            return {
                    'success': False, 
                    'message': str(e)} 
            
    @http.route('/api/get-users', type='json', auth='user', methods=['GET'], csrf=False)
    def get_users(self, **kwargs):
        '''
        {
            'user_id': 1 or null
            'user_name': Moses Abraham or null
        }
        if user id or user name, returns the specific contact by id  or name else returns all contacts
        '''
        try:
            data = json.loads(request.httprequest.data) # kwargs
            user_id = data.get('user_id')
            user_name = data.get('user_name')
            if user_id and type(user_id) != int:
                return invalid_response(
                    "user id",
                    "user ID provided must be an integer"
                    "[user_id]",
                    400,
                )
            domain = ['|', ('id', '=', user_id), ('name', '=', user_name)] if user_id or user_name else []
            users = request.env['res.users'].sudo().search(domain)
            if users:
                data = []
                for usr in users:
                    data.append({
                        'id': usr.id, 
                        'user_name': usr.name or None,
                    })
                return {
                    'success': True, 
                    'data':data
                    }
            else:
                return {
                    'success': False, 
                    'message': 'No user found on the system'}   
        
        except Exception as e:
            return {
                    'success': False, 
                    'message': str(e)} 
        
    @http.route('/api/sales_order/operation', type='json', auth='user', methods=['POST'], csrf=False)
    def handle_sales_operations(self, **kwargs):
        ''''''
        try:
            _logger.info("Raw request data: ")

            data = json.loads(request.httprequest.data) # kwargs
            _logger.info(data)
            if data.get('operation') == 'create':
                return self._create_sales_order(data)
            elif data.get('operation') == 'update':
                return self._update_sales_order(data)
            elif data.get('operation') == 'get':
                return self._get_sales_order(data)
            else:
                return {'success': False, 'message': 'Ensure that the operation data contains create, update, or get'}   
        
        except Exception as e:
            return {'error': str(e)}
        
    def _create_sales_order(self, data):
        '''where data is equal to the sent payload'''
        partner_id = data.get('partner_id')
        order_lines = data.get('order_lines')
        company_id = data.get('company_id')
        _logger.info(f"Data is {data}")
        _logger.info(f".....Partner_id: {partner_id}, Order Lines: {order_lines} and Company ID: {company_id}.....")
        
        if not partner_id or not order_lines:
            return invalid_response(
                "missing_parameter",
                "Missing required parameters"
                " [partner_id, order_lines]",
                400,
            )
        order_vals = {
            'partner_id': partner_id,
            'company_id': company_id,
            'order_line': [(0, 0, line) for line in order_lines]
        }
        order = request.env['sale.order'].sudo().create(order_vals)
        order.action_confirm()
        inv = order.sudo()._create_invoices()[0]
        return {
            'success': True, 
            'data': {'so_id': order.id, 'so_id': order.name, 'invoice_id': inv.id}
            } 
            
    def validate_invoice_and_post_journal(
        self, journal_id, inv): 
        """To be used only when they request for automatic payment generation
        journal: set to the cash journal default bank journal is 7
        """
        inbound_payment_method = request.env['account.payment.method'].sudo().search(
            [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1)
        payment_method = 2
        if journal_id:
            payment_method = journal_id.inbound_payment_method_line_ids[0].id if \
                journal_id.inbound_payment_method_line_ids else inbound_payment_method.id \
                    if inbound_payment_method else payment_method
        payment_method_line_id = self.get_payment_method_line_id('inbound', journal_id)
        payment_vals = {
            'date': fields.Date.today(),
            'amount': inv.amount_total,
            'payment_type': 'inbound',
            # 'is_internal_transfer': True,
            'partner_type': 'customer',
            'ref': inv.name,
            # 'move_id': inv.id,
            # 'journal_id': 8, #inv.payment_journal_id.id,
            'currency_id': inv.currency_id.id,
            'partner_id': inv.partner_id.id,
            # 'destination_account_id': inv.line_ids[1].account_id.id,
            'payment_method_line_id': payment_method, #payment_method_line_id.id if payment_method_line_id else payment_method,
        }
        
        '''
        Add the skip context to avoid;  
        Journal Entry Draft Entry PBNK1/2023/00002 is not valid. 
        In order to proceed, the journal items must include one and only
        one outstanding payments/receipts account.
        '''
        skip_context = {
            'skip_invoice_sync':True,
            'skip_invoice_line_sync':True,
            'skip_account_move_synchronization':True,
            'check_move_validity':False,
        }
        payments = request.env['account.payment'].with_context(**skip_context).create(payment_vals)
        # payments = request.env['account.payment'].create(payment_vals)
        # payments._synchronize_from_moves(False)
        payments.action_post()
        
    def _update_sales_order(self, data):
        '''Update an existing sales order.'''
        data.pop('operation', None)
        order_id = data.pop('id')
        
        order = request.env['sale.order'].sudo().browse(order_id)
        if order:
            order_lines = data.pop('order_lines', None)
            if order_lines:
                updated_order_lines = []
                existing_product_ids = order.order_line.mapped('product_id.id')

                for line in order_lines:
                    product_id = line.get('product_id')
                    
                    if product_id in existing_product_ids:
                        existing_line = order.order_line.search([('order_id', '=', order.id),('product_id.id', '=', product_id)], limit=1)
                        updated_order_lines.append((1, existing_line.id, line))
                    else:
                        updated_order_lines.append((0, 0, line))

                data['order_line'] = updated_order_lines

            order.write(data)
            return {'success': True, 'order_id': order.id}
        else:
            return {'success': False, 'message': 'Sales order not found'}

    
    def _get_sales_order(self, data):
        '''where data is equal to the sent payload for get,
        e.g data = { 'id': 3, ...}
        '''
        order_id = data.get('id')
        so_number = data.get('so_number')

        if order_id or so_number:
            order = request.env['sale.order'].sudo().search([
                '|', ('id', '=', order_id), ('name', '=', so_number)
            ], limit=1)

            if not order:
                return {'success': False, 'message': 'Sales order not found'}
            
            order_data = {
                'id': order.id,
                'name': order.name,
                'partner_id': order.partner_id.id,
                'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                'order_line': [{
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'price_unit': line.price_unit
                } for line in order.order_line]
            }
            return {'success': True, 'result': order_data}

        return {'success': False, 'message': 'Missing order ID or SO number'}

    # @validate_token
    # @http.route(['/api/v1/create_payment'], type="http", auth="none", methods=["POST"], csrf=False)
    # def create_payment(self, **post):
    #     """Register payment for existing invoice

    #     Args:
    #         dict: post data

    #     Returns:
    #         json: Returns json doc containing status of payment registration
    #     Sample Request:
    #         url = "http://localhost:8069/api/v1/create_payment"
    #         payload = {
    #             "invoice_no": "INV/2024/00001",
    #             "user_id": 21,
    #             "payment_reference": "REF-0009999", #(ref from flutterwave)
                
    #         }

    #         headers =  {
    #             "token":"my_lovely_and_highly_secure_token"}
    #         req = requests.post(url, data=payload, headers=headers)
    #         req.json()
    #     """
    #     invoiceno = post.get('invoice_no', '').strip()
    #     # this is actually a user id not partner id
    #     user_id = post.get('user_id', '').strip()
    #     # payment_gateway = post.get('payment_gateway', '').strip()
    #     payment_reference = post.get('payment_reference', '').strip()
    #     company_id = request.env.user.company_id.id
    #     _logger.info(
    #         f"Registering payment for invoice {invoiceno} with user id {user_id}")

    #     _parameters = all(
    #         [invoiceno, payment_reference])
    #     if not _parameters:
    #         return invalid_response(
    #             "missing_parameter",
    #             "either of the following are missing"
    #             " [invoice_no, user_id, payment_date, payment_reference]",
    #             400,
    #         )

    #     # ensure the partner ID exists
    #     user = user = request.env['res.users'].sudo().search(
    #         [('id', '=', int(user_id))])
    #     if not user:
    #         return invalid_response(
    #             "user_not_found",
    #             f"User with ID {user_id} not found.",
    #             400
    #         )
    #     partner = user.partner_id
    #     # partner = request.env['res.partner'].sudo().browse(int(partner_id))
    #     if not partner:
    #         return invalid_response(
    #             "partner_not_found",
    #             f"User with ID {user_id} don't have a related partner",
    #             400,
    #         )

    #     invoice = (request.env['account.move'].sudo().search(
    #         [("name", "=", invoiceno), ]))
    #     if not invoice:
    #         return invalid_response(
    #             "invoice_not_found",
    #             f"Invoice with number {invoiceno} not found.",
    #             400,
    #         )

    #     if not invoice.state == "posted":
    #         return invalid_response(
    #             "invalid_invoice_state",
    #             f"You can only register payment for posted invoices.",
    #             400,
    #         )

    #     if invoice.payment_state == "paid":
    #         return valid_response(
    #             data={},
    #             status=200,
    #             message="Invoice is already paid"
    #         )
    #     default_journal = request.env['account.journal'].sudo().search(
    #         [
    #             ('type', '=', 'bank'),
    #             ('company_id', '=', company_id)
    #         ],
    #         limit=1
    #     )
    #     journal = default_journal
    #     # journal = acquirer.journal_id and acquirer.journal_id or default_journal

    #     payment_method = request.env['account.payment.method'].sudo().search(
    #         [
    #             ('code', '=', 'manual'),
    #             ('payment_type', '=', 'inbound')
    #         ],
    #         limit=1
    #     )
    #     vals = {
    #         'payment_date': fields.Date.today(),
    #         'move_id': invoice.id,
    #         # 'invoice_ids': [(4, invoice.id)],
    #         'amount': invoice.amount_residual_signed,
    #         'ref': payment_reference,
    #         'payment_type': 'inbound',
    #         'partner_type': 'customer',
    #         'journal_id': journal.id,
    #         'payment_method_id': payment_method and payment_method.id or 1,
    #         'partner_id': partner.id,
    #     }
    #     payment = request.env['account.payment'].sudo().create(vals)
    #     payment.post()

    #     return werkzeug.wrappers.Response(
    #         status=200,
    #         content_type="application/json; charset=utf-8",
    #         headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
    #         response=json.dumps(
    #             {
    #                 "status_code": 200,
    #                 "message": "successful"
    #             }
    #         )
    #     )
    
    # def get_payment_method_line_id(self, payment_type, journal_id):
    #     if journal_id:
    #         available_payment_method_lines = journal_id._get_available_payment_method_lines(payment_type)
    #     else:
    #         available_payment_method_lines = False
    #     # Select the first available one by default.
    #     if available_payment_method_lines:
    #         payment_method_line_id = available_payment_method_lines[0]._origin
    #     else:
    #         payment_method_line_id = False
    #     return payment_method_line_id
    
    # def validate_invoice_and_post_journalx(self, inv):
    #     payment_register = request.env['account.payment.register']
    #     payment_register.with_context(
    #         {'active_model': 'account.move',
    #         'active_ids': inv.ids}
    #     ).create({
    #         'journal_id': 8, 'amount': inv.amount_total, 'payment_type': 'inbound', 'line_ids': inv.invoice_line_ids.ids
    #         }).action_create_payments()
        
    # def register_payment(self, **kwargs):
    #     invoice_obj = request.env['account.move'].sudo()
    #     account_journal = request.env['account.journal'].sudo()
    #     account_payment_obj = request.env['account.payment'].sudo()
    #     sale_payment_method = request.env['account.payment.method'].sudo().search(
    #             [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1)

    #     journal_id = kwargs.get('journal_id') 
    #     inv = kwargs.get('invoiceObj')
    #     payment_reference = kwargs.get('payment_reference')
        
        
    #     # journal_payment_line_method = account_journal.browse([journal_id]).mapped('available_payment_method_ids').filtered(
    #     #     lambda s: s.code == 'manual' and s.payment_type == 'inbound')
    #     # payment_method = journal_payment_line_method.payment_method_id.id if journal_payment_line_method else sale_payment_method.id if sale_payment_method else 1
    #     # _logger.info(f"Payment methoddin {journal_payment_line_method.name}")
    #     acc_values = {
    #         'move_id': inv.id,
    #         # 'invoice_ids': [(6, 0, [inv.id])],
    #         'amount': inv.amount_residual_signed,
    #         'ref': f'[Payment REF: {payment_reference}',
    #         'payment_type': 'inbound',
    #         'partner_type': 'customer',
    #         'journal_id': 1, #inv.payment_journal_id.id or journal_id,
    #         # 'branch_id': branch_id,
    #         'payment_method_id': 1, # sale_payment_method.id, #payment_method,
    #         'payment_method_line_id': 3,# journal_payment_line_method.id or 3,
    #         # 'available_payment_method_line_ids': [(6, 0, [journal_payment_line_method.id])],
    #         'partner_id': inv.partner_id.id,  # or partner_id,
    #     }
    #     payment = account_payment_obj.create(acc_values)
    #     return payment