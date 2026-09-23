from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MovieReview(models.Model):
    _name = 'movie.review'
    _description = 'Movie Review'
    _order = 'id desc'

    movie_id = fields.Many2one('movie.movie', required=True, ondelete='cascade')
    reviewer_id = fields.Many2one(
        'res.users', string='Reviewer', required=True,
        default=lambda self: self.env.user,
    )
    score = fields.Integer(default=5, required=True)
    comment = fields.Text()

    _sql_constraints = [
        ('reviewer_movie_uniq', 'unique(movie_id, reviewer_id)',
         'A user can only review a movie once.'),
    ]

    @api.constrains('score')
    def _check_score(self):
        for rec in self:
            if not 1 <= rec.score <= 10:
                raise ValidationError("Score must be between 1 and 10.")
