from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commision_percent = fields.Float()
    commision_nominal = fields.Float(compute='compute_nominal')

    def calculate_nominal(self):
        self.commision_nominal = self.amount_total * self.commision_percent / 100
    
    @api.depends('commision_percent','amount_total')
    def compute_nominal(self):
        for rec in self:
            rec.commision_nominal = rec.amount_total * rec.commision_percent / 100
