from odoo import api, fields, models


class MovieArtist(models.Model):
    _name = 'movie.artist'
    _description = 'Movie Artist'
    _order = 'name'

    name = fields.Char(required=True)
    birth_date = fields.Date()
    role = fields.Selection([
        ('actor', 'Actor'),
        ('director', 'Director'),
        ('writer', 'Writer'),
    ], default='actor', required=True)
    movie_ids = fields.Many2many(
        'movie.movie', 'movie_movie_artist_rel', 'artist_id', 'movie_id',
        string='Movies',
    )
    movie_count = fields.Integer(compute='_compute_movie_count', string='Movie Count')

    @api.depends('movie_ids')
    def _compute_movie_count(self):
        for rec in self:
            rec.movie_count = len(rec.movie_ids)

    def action_view_movies(self):
        """Action smart button untuk melihat film yang diperankan / disutradarai artis ini."""
        self.ensure_one()
        return {
            'name': f'Movies with {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.movie',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', self.movie_ids.ids)],
            'context': {'default_artist_ids': [(4, self.id)]},
        }
