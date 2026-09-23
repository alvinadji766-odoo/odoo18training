import base64
import json
import logging
import re
import time
import requests

from odoo import api, fields, models, Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MovieFetchApiWizard(models.TransientModel):
    _name = 'movie.fetch.api.wizard'
    _description = 'Fetch Movie from External REST API Wizard'

    state = fields.Selection([
        ('draft', '1. Setup & Inspect Request'),
        ('fetched', '2. Inspect Response & Create Record'),
    ], string='Status', default='draft', required=True)

    search_query = fields.Char(
        string='Movie / TV Show Title',
        required=True,
        default='Batman',
        help='Masukkan judul film untuk dicari via REST API (contoh: Batman, Spider-Man, Inception, Breaking Bad)'
    )
    
    source_type = fields.Selection([
        ('live', '🌐 Live Public REST API (TVMaze API)'),
        ('mock', '💾 Mock / Offline Simulation (Belajar Struktur JSON)'),
    ], string='API Source', default='live', required=True)

    # =========================================================================
    # HTTP REQUEST INSPECTOR FIELDS
    # =========================================================================
    http_method = fields.Char(string='HTTP Method', default='GET', readonly=True)
    api_endpoint = fields.Char(string='Endpoint URL', compute='_compute_request_details', readonly=True)
    request_headers = fields.Text(string='Request Headers', compute='_compute_request_details', readonly=True)
    request_params = fields.Text(string='Query Parameters', compute='_compute_request_details', readonly=True)

    # =========================================================================
    # HTTP RESPONSE INSPECTOR FIELDS
    # =========================================================================
    response_status_code = fields.Integer(string='HTTP Status Code', readonly=True)
    response_status_text = fields.Char(string='HTTP Status', readonly=True)
    response_time_ms = fields.Float(string='Response Time (ms)', readonly=True)
    response_headers = fields.Text(string='Response Headers', readonly=True)
    response_body_raw = fields.Text(string='Response Payload (Formatted JSON)', readonly=True)

    # =========================================================================
    # PARSED DATA PREVIEW (MAPPING TO ODOO)
    # =========================================================================
    parsed_title = fields.Char(string='Movie Title', readonly=True)
    parsed_premiered = fields.Char(string='Premiered Date', readonly=True)
    parsed_runtime = fields.Integer(string='Runtime (minutes)', readonly=True)
    parsed_rating = fields.Char(string='Rating Score', readonly=True)
    parsed_rating_star = fields.Char(string='Rating Star (0-5)', readonly=True)
    parsed_genres = fields.Char(string='Detected Genres', readonly=True)
    parsed_cast = fields.Char(string='Detected Cast & Crew', readonly=True)
    parsed_image_url = fields.Char(string='Poster Image URL', readonly=True)
    parsed_summary = fields.Text(string='Cleaned Synopsis', readonly=True)

    @api.depends('search_query', 'source_type')
    def _compute_request_details(self):
        for rec in self:
            query = rec.search_query or ''
            if rec.source_type == 'live':
                rec.api_endpoint = f"https://api.tvmaze.com/singlesearch/shows?q={query}&embed=cast"
                rec.request_params = json.dumps({'q': query, 'embed': 'cast'}, indent=2)
                rec.request_headers = json.dumps({
                    'User-Agent': 'OdooMovieTraining/18.0 (REST API Demo)',
                    'Accept': 'application/json'
                }, indent=2)
            else:
                rec.api_endpoint = f"mock://internal-simulation/shows?q={query}"
                rec.request_params = json.dumps({'q': query, 'mode': 'mock_offline'}, indent=2)
                rec.request_headers = json.dumps({
                    'User-Agent': 'OdooMovieTraining/18.0 (Mock Engine)',
                    'Accept': 'application/json'
                }, indent=2)

    # =========================================================================
    # STEP 1: SEND HTTP REQUEST & INSPECT RESPONSE
    # =========================================================================
    def action_send_request(self):
        """
        Kirim HTTP Request ke API eksternal (atau simulasi mock),
        catat response status, timing, headers, dan payload JSON
        lalu buka step inspeksi sebelum record dibuat di Odoo.
        """
        self.ensure_one()
        t_start = time.time()

        if self.source_type == 'live':
            #manggul API nya
            resp_data, status_code, status_text, resp_headers = self._fetch_from_live_api(self.search_query)
        else:
            resp_data, status_code, status_text, resp_headers = self._get_mock_api_response(self.search_query)

        duration_ms = round((time.time() - t_start) * 1000, 2)

        # Parsing preview fields
        movie_title = resp_data.get('name') or self.search_query.title()
        premiered_date = str(resp_data.get('premiered') or '-')
        runtime = resp_data.get('runtime') or resp_data.get('averageRuntime') or 90
        raw_summary = resp_data.get('summary') or ''
        clean_summary = re.sub(r'<[^>]+>', '', raw_summary).strip()

        avg_score = (resp_data.get('rating') or {}).get('average') or 0.0
        if avg_score >= 8.5:
            rating_star = '5 ⭐⭐⭐⭐⭐'
        elif avg_score >= 7.0:
            rating_star = '4 ⭐⭐⭐⭐'
        elif avg_score >= 5.5:
            rating_star = '3 ⭐⭐⭐'
        elif avg_score >= 4.0:
            rating_star = '2 ⭐⭐'
        elif avg_score > 0:
            rating_star = '1 ⭐'
        else:
            rating_star = '0 ⚪'

        image_info = resp_data.get('image') or {}
        image_url = image_info.get('original') or image_info.get('medium') or '-'

        genres_list = resp_data.get('genres') or []
        genres_str = ", ".join(genres_list) if genres_list else "None"

        raw_cast = resp_data.get('cast') or (resp_data.get('_embedded') or {}).get('cast') or []
        cast_names = []
        for c in raw_cast[:5]:
            p = c.get('person') if isinstance(c.get('person'), dict) else c
            name = p.get('name')
            if name:
                cast_names.append(name)
        cast_str = ", ".join(cast_names) if cast_names else "None"

        self.write({
            'state': 'fetched',
            'response_status_code': status_code,
            'response_status_text': status_text,
            'response_time_ms': duration_ms,
            'response_headers': json.dumps(resp_headers, indent=2),
            'response_body_raw': json.dumps(resp_data, indent=2),
            'parsed_title': movie_title,
            'parsed_premiered': premiered_date,
            'parsed_runtime': int(runtime),
            'parsed_rating': f"{avg_score} / 10",
            'parsed_rating_star': rating_star,
            'parsed_genres': genres_str,
            'parsed_cast': cast_str,
            'parsed_image_url': image_url,
            'parsed_summary': clean_summary,
        })

        return {
            'name': 'Inspect REST API Request & Response',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.fetch.api.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # =========================================================================
    # STEP 2: CREATE RECORD IN DATABASE & OPEN IT
    # =========================================================================
    def action_create_movie_record(self):
        """
        Mengonversi JSON Response yang telah diinspeksi menjadi Record Odoo
        lengkap dengan poster gambar Base64, relational tags, dan chatter log.
        """
        self.ensure_one()
        if not self.response_body_raw:
            self.action_send_request()

        try:
            data = json.loads(self.response_body_raw)
        except Exception:
            raise UserError("Gagal membaca payload JSON response.")

        # 1. Parsing Nilai Scalar
        movie_title = data.get('name') or self.search_query.title()
        premiered_date = data.get('premiered')  # format "YYYY-MM-DD"
        runtime = data.get('runtime') or data.get('averageRuntime') or 90
        raw_summary = data.get('summary') or ''
        clean_summary = re.sub(r'<[^>]+>', '', raw_summary).strip()

        # Mapping Rating 0-10 ke skala pilihan '0'-'5'
        avg_score = (data.get('rating') or {}).get('average') or 0.0
        if avg_score >= 8.5:
            rating_val = '5'
        elif avg_score >= 7.0:
            rating_val = '4'
        elif avg_score >= 5.5:
            rating_val = '3'
        elif avg_score >= 4.0:
            rating_val = '2'
        elif avg_score > 0:
            rating_val = '1'
        else:
            rating_val = '0'

        # 2. Unduh Gambar Poster (Binary Base64)
        poster_base64 = False
        image_info = data.get('image') or {}
        image_url = image_info.get('original') or image_info.get('medium')
        if image_url and image_url.startswith('http'):
            try:
                img_res = requests.get(image_url, timeout=10)
                if img_res.status_code == 200:
                    poster_base64 = base64.b64encode(img_res.content)
            except Exception as img_err:
                _logger.warning("Gagal mengunduh poster gambar dari %s: %s", image_url, img_err)

        # 3. Auto-Create / Link Relasi Many2many (Genres)
        genre_ids = []
        for g_name in (data.get('genres') or []):
            genre = self.env['movie.genre'].search([('name', '=ilike', g_name.strip())], limit=1)
            if not genre:
                genre = self.env['movie.genre'].create({
                    'name': g_name.strip(),
                    'color': (len(g_name) % 10) + 1,
                })
            genre_ids.append(genre.id)

        # 4. Auto-Create / Link Relasi Many2many (Cast & Crew)
        cast_ids = []
        raw_cast = data.get('cast') or (data.get('_embedded') or {}).get('cast') or []
        for cast_entry in raw_cast[:5]:
            person = cast_entry.get('person') if isinstance(cast_entry.get('person'), dict) else cast_entry
            actor_name = person.get('name')
            if actor_name:
                artist = self.env['movie.artist'].search([('name', '=ilike', actor_name.strip())], limit=1)
                if not artist:
                    artist = self.env['movie.artist'].create({
                        'name': actor_name.strip(),
                        'birth_date': person.get('birthday') or False,
                        'role': 'actor',
                    })
                cast_ids.append(artist.id)

        # 5. Simpan Record Film Baru di Odoo
        vals = {
            'name': movie_title,
            'release_date': premiered_date or False,
            'duration': int(runtime),
            'synopsis': clean_summary,
            'rating': rating_val,
            'state': 'released' if premiered_date else 'draft',
            'poster_image': poster_base64,
            'genre_ids': [Command.set(genre_ids)] if genre_ids else False,
            'artist_ids': [Command.set(cast_ids)] if cast_ids else False,
        }

        new_movie = self.env['movie.movie'].create(vals)

        # Log chatter catatan integrasi REST API
        new_movie.message_post(
            body=(
                f"📡 <b>Data berhasil di-import dari REST API!</b><br/>"
                f"• Sumber: {'🌐 TVMaze Public API' if self.source_type == 'live' else '💾 Mock API Simulation'}<br/>"
                f"• Query: <i>{self.search_query}</i><br/>"
                f"• Response Time: {self.response_time_ms} ms<br/>"
                f"• Score API: {avg_score}/10 (Mapped ke Rating {rating_val} Bintang)"
            )
        )

        # 6. Buka Langsung Form View Film yang Baru Saja Dibuat
        return {
            'name': new_movie.name,
            'type': 'ir.actions.act_window',
            'res_model': 'movie.movie',
            'res_id': new_movie.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reset_draft(self):
        """Kembali ke form pencarian / setup request."""
        self.ensure_one()
        self.write({'state': 'draft'})
        return {
            'name': 'Fetch Movie from REST API',
            'type': 'ir.actions.act_window',
            'res_model': 'movie.fetch.api.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # =========================================================================
    # HELPER: CALL REAL LIVE REST API
    # =========================================================================
    def _fetch_from_live_api(self, query):
        """Memanggil API publik TVMaze secara realtime."""
        endpoint = "https://api.tvmaze.com/singlesearch/shows"
        params = {'q': query, 'embed': 'cast'}
        headers = {
            'User-Agent': 'OdooMovieTraining/18.0 (REST API Demo)',
            'Accept': 'application/json'
        }

        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=12)
            status_code = response.status_code
            status_text = f"{status_code} {response.reason}"
            resp_headers = dict(response.headers)

            if response.status_code == 404:
                raise UserError(f"Film dengan judul '{query}' tidak ditemukan di TVMaze API (HTTP 404). Coba kata kunci lain (misal: Batman, Matrix, Avatar).")
            if response.status_code != 200:
                raise UserError(f"API Error (HTTP {response.status_code}): {response.text}")
            
            return response.json(), status_code, status_text, resp_headers
        except requests.exceptions.ConnectionError:
            raise UserError(
                "Gagal terhubung ke internet / DNS Error! Pastikan server memiliki koneksi internet, "
                "atau pilih opsi '💾 Mock / Offline Simulation' untuk mencoba secara offline."
            )
        except requests.exceptions.Timeout:
            raise UserError("Koneksi API Timeout! Server API membutuhkan waktu terlalu lama untuk merespons.")

    # =========================================================================
    # HELPER: MOCK OFFLINE SIMULATION
    # =========================================================================
    def _get_mock_api_response(self, query):
        """Simulasi payload JSON jika dijalankan secara offline."""
        q_lower = (query or '').lower()
        if 'spider' in q_lower:
            data = {
                'name': 'Spider-Man: The Animated Series',
                'premiered': '1994-11-19',
                'runtime': 22,
                'summary': '<p>After being bitten by a radioactive spider, young Peter Parker gains extraordinary superpowers and vows to protect New York City.</p>',
                'rating': {'average': 8.6},
                'genres': ['Action', 'Sci-Fi', 'Animation'],
                'image': {
                    'medium': 'https://static.tvmaze.com/uploads/images/medium_portrait/10/26732.jpg',
                    'original': 'https://static.tvmaze.com/uploads/images/original_untouched/10/26732.jpg'
                },
                'cast': [
                    {'name': 'Christopher Daniel Barnes', 'birthday': '1972-11-07'},
                    {'name': 'Sara Ballantine', 'birthday': '1961-04-12'},
                    {'name': 'Edward Asner', 'birthday': '1929-11-15'},
                ]
            }
        else:
            data = {
                'name': f"{query.title()} (REST API Demo)",
                'premiered': '2024-05-10',
                'runtime': 135,
                'summary': f'<p>An epic cinematic adventure following the journey of <b>{query.title()}</b> across uncharted dimensions.</p>',
                'rating': {'average': 8.8},
                'genres': ['Action', 'Sci-Fi', 'Thriller'],
                'image': {
                    'medium': '',
                    'original': ''
                },
                'cast': [
                    {'name': 'Tom Hardy', 'birthday': '1977-09-15'},
                    {'name': 'Emily Blunt', 'birthday': '1983-02-23'},
                    {'name': 'Michael Caine', 'birthday': '1933-03-14'},
                ]
            }
        
        status_code = 200
        status_text = "200 OK (Mock Simulation)"
        resp_headers = {
            'content-type': 'application/json; charset=utf-8',
            'server': 'Odoo-Mock-Engine/18.0',
            'x-simulation-mode': 'offline-educational'
        }
        return data, status_code, status_text, resp_headers
