from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError


class MovieMovie(models.Model):
    _name = 'movie.movie'
    _description = 'Movie'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'release_date desc, name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    release_date = fields.Date(tracking=True)
    duration = fields.Integer(string='Duration (min)', default=90)
    synopsis = fields.Text()
    color = fields.Integer()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('released', 'Released'),
    ], default='draft', required=True, tracking=True)

    # ---------- Field Binary & Image ----------
    # 1. Image / Poster (Disimpan sebagai binary, ditampilkan dengan widget="image")
    poster_image = fields.Image(
        string='Poster Image',
        max_width=1024,
        max_height=1024,
        help='Movie poster image (Widget Image)'
    )
    # 2. Raw Binary File (Contoh: Dokumen script/naskah film + filename)
    attachment_file = fields.Binary(
        string='Script / Document File',
        attachment=True,
        help='Binary file upload demo'
    )
    attachment_filename = fields.Char(string='Attachment Filename')

    # ---------- Field Rating / Priority ----------
    # Rating/Priority (Widget "priority" untuk bintang interaktif 0-5)
    rating = fields.Selection([
        ('0', 'No Rating'),
        ('1', '1 Star (Poor)'),
        ('2', '2 Stars (Fair)'),
        ('3', '3 Stars (Good)'),
        ('4', '4 Stars (Very Good)'),
        ('5', '5 Stars (Masterpiece)'),
    ], string='Rating', default='0', tracking=True, help='Manual star rating using widget="priority"')

    studio_id = fields.Many2one('movie.studio', tracking=True)
    genre_ids = fields.Many2many(
        'movie.genre', 'movie_movie_genre_rel', 'movie_id', 'genre_id',
        string='Genres',
    )
    artist_ids = fields.Many2many(
        'movie.artist', 'movie_movie_artist_rel', 'movie_id', 'artist_id',
        string='Cast & Crew',
    )
    review_ids = fields.One2many('movie.review', 'movie_id', string='Reviews')

    avg_rating = fields.Float(compute='_compute_rating', store=True, digits=(3, 1), string='Avg Review Score')
    review_count = fields.Integer(compute='_compute_rating', store=True, string='Review Count')
    artist_count = fields.Integer(compute='_compute_artist_count', string='Artist Count')

    # ---------- compute ----------
    @api.depends('review_ids.score')
    def _compute_rating(self):
        for rec in self:
            scores = rec.review_ids.mapped('score')
            rec.review_count = len(scores)
            rec.avg_rating = sum(scores) / len(scores) if scores else 0.0

    @api.depends('artist_ids')
    def _compute_artist_count(self):
        for rec in self:
            rec.artist_count = len(rec.artist_ids)

    # ---------- constraint / exception ----------
    @api.constrains('duration')
    def _check_duration(self):
        for rec in self:
            if rec.duration <= 0:
                raise ValidationError("Duration must be greater than 0.")

    # =========================================================================
    # INHERIT ORM CRUD METHODS (create, write, unlink, copy) - UNTUK PEMBELAJARAN
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        return records

    def write(self, vals):
        res = super().write(vals)
        return res

    def unlink(self):
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        return super().copy(default)

    # ---------- smart button actions ----------
    def action_view_reviews(self):
        """Membuka view list review yang spesifik hanya untuk film ini."""
        self.ensure_one()
        return {
            'name': f'Reviews for {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.review',
            'view_mode': 'list,form',
            'domain': [('movie_id', '=', self.id)],
            'context': {'default_movie_id': self.id},
        }

    def action_view_artists(self):
        """Membuka view list Cast & Crew yang terlibat di film ini."""
        self.ensure_one()
        return {
            'name': f'Cast & Crew of {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.artist',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.artist_ids.ids)],
            'context': {'default_movie_ids': [(4, self.id)]},
        }

    # ---------- actions ----------
    def action_release(self):
        for rec in self:
            if not rec.genre_ids or not rec.artist_ids:
                raise UserError(
                    "Movie '%s' needs at least one genre and one cast/crew member before release."
                    % rec.name
                )
            rec.state = 'released'
            rec.message_post(body="Movie released.")

    def action_back_draft(self):
        self.write({'state': 'draft'})

