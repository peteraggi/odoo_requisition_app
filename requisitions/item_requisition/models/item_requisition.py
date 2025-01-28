from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    requisition_id = fields.Many2one('item.requisition', string='Requisition')

class StockPicking(models.Model):
    _inherit = "stock.picking"

    requisition_id = fields.Many2one('item.requisition', string='Requisition')


class ItemRequisition(models.Model):
    _name = "item.requisition"
    _inherit = ['mail.thread']

    name = fields.Char('PO Requisition', default='/')
    requested_by = fields.Many2one('res.users', string="Requested By",tracking=True)
    user = fields.Many2one('res.users', string='Approved By',tracking=True)
    user_complete = fields.Many2one('res.users', string='Completed By',tracking=True)
    department_id = fields.Many2one('hr.department', string="Department")
    partner_id = fields.Many2one('res.partner', string='Customer',tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True, default=1)
    source = fields.Many2one('stock.location', string="Source", domain="[('usage', 'in', ('internal','production'))]",tracking=True)
    destination = fields.Many2one('stock.location', string="Destination", domain="[('usage', 'in', ('internal','production'))]",tracking=True)
   
    delivery_date = fields.Datetime(string='Expected Delivery Date', index=True,tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('rejected', 'Rejected'),
    ], string='Status', readonly=True, index=True, copy=False, default='draft',tracking=True)
   
    order_line = fields.One2many('item.requisition.order.line', 'order_id', string='Order Lines', copy=True,tracking=True)

    picking_id = fields.Many2one('stock.picking', string="picking")

    # def get_default_out_picking_type(self):
    #     return self.env['stock.picking.type'].search([
    #         ('code', '=', 'internal'),
    #         ('warehouse_id.company_id', 'in', [self.env.context.get('company_id', self.env.user.company_id.id), False])],
    #         limit=1).id
    def get_default_out_picking_type(self):
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', 'in', [self.env.context.get('company_id', self.env.user.company_id.id), False])
        ], limit=1)
        if not picking_type:
            raise ValidationError(_("No valid Operation Type found for the company. Please configure an internal Operation Type."))
        return picking_type.id

    def get_default_out_location_src_id(self):
        location = False
        if self.picking_type_in_id:
            location = self.env['stock.picking.type'].browse(self.picking_type_in_id.id).default_location_src_id.id
        else:
            picking_type_in_id = self.env['stock.picking.type'].search([('code', '=', 'internal'),
                ('warehouse_id.company_id', 'in', [self.env.context.get('company_id', self.env.user.company_id.id), False])],
                limit=1).id
            location = self.env['stock.picking.type'].browse(picking_type_in_id).default_location_src_id.id
    
        return location


    def get_default_out_location_dest_id(self):
        location = False
        
        site_location_record = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        location = site_location_record.id
    
        return location
    
    picking_type_in_id = fields.Many2one('stock.picking.type', string='Operation Type ',default=get_default_out_picking_type)
    location_src_in_id = fields.Many2one('stock.location', string='Source Location', default=get_default_out_location_src_id,readonly=True)
    location_dest_in_id = fields.Many2one('stock.location', string='Destination Location', default=get_default_out_location_dest_id,readonly=True)

    def submit_for_approval(self):
        for rec in self:
            if len(rec.order_line) < 1:
                raise models.ValidationError(_("Stop! You are attempting to make an empty request!"))

            for line_item in self.order_line:
                if line_item.product_qty <= 0:
                    raise UserError(_('Please the quantity for '+str(line_item.product_id.name)))

           
            # template_id = self.env.ref('requisitions.item_requisition_approval_email').id
            # self.env['mail.template'].browse(template_id).send_mail(self.id,force_send=True)
            rec.write({
                'state': 'submitted',
                'requested_by': self.env.user.id,
                'department_id': self.env.user.employee_id.department_id.id if self.env.user.employee_id.department_id else False,
            })

    def approve(self):
        self.write({
            'state': 'approved',
            'user': self.env.uid,
        })

    def action_approve_item_requisition(self):
        if self.order_line:
            for data in self:

                if not data.destination:
                    raise models.ValidationError(_("Please provide the destination for the items requested!"))
                
                move_obj = self.env['stock.move']
                pick_obj = self.env["stock.picking"]
                for data in self:

                    move_vals = []
                    for rec in data.order_line:
                        move_vals.append([0,0, {
                            'name': '('+str(rec.product_id.name)+') requested from '+str(data.name),
                            'product_id': rec.product_id.id,
                            'product_uom_qty': rec.product_qty,
                            'quantity': rec.product_qty,
                            # 'quantity_done': rec.quantity,
                            'product_uom': rec.product_uom.id,
                            'location_dest_id': data.destination.id,
                            'location_id': data.source.id,
                            'requisition_id': data.id,
                        
                        }])

                    pick_values = {
                        'note': 'Items requested by '+str(self.env.user.name),
                        # 'company_id': 1,
                        'location_dest_id': data.destination.id,
                        'location_id': data.source.id,
                        'move_ids_without_package': move_vals,
                        'move_type': 'direct',
                        'picking_type_id': data.get_default_out_picking_type(), #check correct picking type ID
                        'origin': data.name,
                        'requisition_id': data.id,

                    }
                    pick_id = pick_obj.create(pick_values)
                    # for rec in data.order_line:
                    #     move_vals = {
                    #         'name': '('+str(rec.product_id.name)+') requested from '+str(data.name),
                    #         'picking_id':pick_id.id,
                    #         'product_id': rec.product_id.id,
                    #         'product_uom_qty': rec.product_qty,
                    #         # 'quantity_done': rec.quantity,
                    #         'product_uom': rec.product_uom.id,
                    #         'location_dest_id': data.destination.id,
                    #         'location_id': data.get_default_out_location_src_id(),
                    #         'requisition_id': data.id,
                            
                    #     }
                    #     move_obj.create(move_vals)
                    pick_id.action_confirm()
                    # pick_id.action_assign()
                    pick_id.button_validate()

                    self.write({'picking_id': pick_id.id})
                # template_id = self.env.ref('requisitions.item_requisition_approval_email').id
                # self.env['mail.template'].browse(template_id).send_mail(self.id,force_send=True)
                data.write({
                    'state':'done',
                    # 'user':self.env.uid,
                    'user_complete' : self.env.uid,
                })

            return True
       
        else:
            raise models.ValidationError(_('You must provide atleast one product to complete this request'))

        return True

    def cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def reject(self):
        for rec in self:
            rec.state = 'rejected'

    # def ops_approval(self):
    #     for rec in self:
    #         template_id = self.env.ref('requisitions.item_requisition_approval_email').id
    #         self.env['mail.template'].browse(template_id).send_mail(self.id,force_send=True)
    #         rec.state = 'ops_approve'        


    # @api.model
    def unlink(self):
        for rec in self:
            if rec.state in ('approve','cancel'):
                raise UserError(_("You can only delete records in Draft State!"),_("Something is wrong!"),_("error"))               
        return super(ItemRequisition, self).unlink()

    @api.model
    def create(self, values):
        
        record = super(ItemRequisition, self).create(values)
        record.name = "ITEM-REQ-"+str(record.id)

        return record



class ItemRequisitionOrderLine(models.Model):
    _name = 'item.requisition.order.line'
    _description = 'Requisition Order Line'
    # _inherit = ['mail.thread',]

    order_id = fields.Many2one('item.requisition', string='Order Reference')
    name = fields.Text(string='Description')
    product_id = fields.Many2one('product.product', string='Product', domain=[
                                 ('detailed_type', 'in', ['product','consu'])], change_default=True, required=True)
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True)

    product_uom = fields.Many2one('uom.uom', string='Product Unit of Measure', store=True)

    @api.onchange('product_uom')
    def _change_uom2(self):
        for rec in self:
            if rec.product_uom.category_id.id != rec.product_id.uom_id.category_id.id:
                raise ValidationError("The Unit of Measure Selected does not belong to the same Category \
                     as the Product's purchase Unit of Measure")
                
    @api.onchange('product_id')
    def _change_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_uom = rec.product_id.uom_id.id
                rec.name = rec.product_id.name


    @api.model
    def create(self, vals):
        sequence = self.env['ir.sequence'].next_by_code('item.requisition.order.line')
        vals['name'] = sequence
        res = super(ItemRequisitionOrderLine,self).create(vals)

        return res


