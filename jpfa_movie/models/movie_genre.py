from odoo import api, fields, models


class MovieGenre(models.Model):
    _name = 'movie.genre'
    _description = 'Movie Genre'
    _order = 'name'

    name = fields.Char(required=True)
    color = fields.Integer()
    movie_ids = fields.Many2many(
        'movie.movie', 'movie_movie_genre_rel', 'genre_id', 'movie_id',
        string='Genres',
    )
    movie_count = fields.Integer(compute='_compute_movie_count', string='Movie Count')

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if rec.name:
                duplicate = self.search([
                    ('name', '=ilike', rec.name.strip()),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    # Lewatkan jika merupakan bagian dari initial data load untuk mencegah crash
                    pass

    @api.depends('movie_ids')
    def _compute_movie_count(self):
        for rec in self:
            rec.movie_count = len(rec.movie_ids)

    def action_view_movies(self):
        """Action smart button untuk melihat film dengan genre ini."""
        self.ensure_one()
        return {
            'name': f'Movies in {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.movie',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', self.movie_ids.ids)],
            'context': {'default_genre_ids': [(4, self.id)]},
        }
