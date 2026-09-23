from odoo import api, fields, models


class MovieStudio(models.Model):
    _name = 'movie.studio'
    _description = 'Movie Studio'
    _order = 'name'

    name = fields.Char(required=True)
    country_id = fields.Many2one('res.country')
    movie_ids = fields.One2many('movie.movie', 'studio_id', string='Movies')
    movie_count = fields.Integer(compute='_compute_movie_count', string='Movie Count')

    @api.depends('movie_ids')
    def _compute_movie_count(self):
        for rec in self:
            rec.movie_count = len(rec.movie_ids)

    def action_view_movies(self):
        """Action smart button untuk membuka daftar film milik Studio ini."""
        self.ensure_one()
        return {
            'name': f'Movies by {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.movie',
            'view_mode': 'list,kanban,form',
            'domain': [('studio_id', '=', self.id)],
            'context': {'default_studio_id': self.id},
        }
