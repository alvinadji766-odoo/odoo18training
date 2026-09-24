import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

DEFAULT_API_KEY = "jpfa-movie-secret-key-2024"
DEFAULT_WEBHOOK_SECRET = "jpfa-webhook-token-secret"


class MovieApiController(http.Controller):

    # =========================================================================
    # AUTHENTICATION & RESPONSE HELPERS
    # =========================================================================
    def _json_response(self, data, status=200):
        """Helper untuk menghasilkan respon HTTP JSON berstandar REST API"""
        return Response(
            json.dumps(data, indent=2, default=str),
            status=status,
            mimetype='application/json'
        )

    def _authenticate_request(self):
        """
        Validasi autentikasi API Key dari Header Request.
        Mendukung dua format umum:
        1. Header 'X-Api-Key: <token>'
        2. Header 'Authorization: Bearer <token>'

        Token divalidasi terhadap System Parameter 'jpfa_movie.api_key'.
        Jika belum diatur di database, akan fallback ke DEFAULT_API_KEY.
        """
        headers = request.httprequest.headers
        token = headers.get('X-Api-Key')

        if not token:
            auth_header = headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()

        if not token:
            return False, "Header autentikasi 'X-Api-Key' atau 'Authorization: Bearer <token>' tidak ditemukan."

        # Cek kunci yang tersimpan di Odoo System Parameters
        system_key = request.env['ir.config_parameter'].sudo().get_param('jpfa_movie.api_key', DEFAULT_API_KEY)

        if token == system_key:
            return True, None

        # Opsi Lanjutan: Cek juga apakah token cocok dengan Odoo User API Key (res.users.apikeys)
        try:
            user = request.env['res.users.apikeys'].sudo()._check_credentials(scope='rpc', key=token)
            if user:
                return True, None
        except Exception:
            pass

        return False, "API Key tidak valid atau sudah kadaluarsa."

    # =========================================================================
    # 1. REST API ENDPOINTS (PROTECTED WITH AUTH)
    # =========================================================================

    @http.route('/api/v1/movies', type='http', auth='none', methods=['GET'], csrf=False)
    def get_movies_list(self, **kwargs):
        """
        GET /api/v1/movies
        Menampilkan daftar film dengan fitur search dan pagination.
        Memerlukan autentikasi API Key.
        """
        is_authenticated, err_msg = self._authenticate_request()
        if not is_authenticated:
            return self._json_response({'status': 'error', 'code': 401, 'message': err_msg}, status=401)

        domain = [('active', '=', True)]
        
        # Filter pencarian opsional
        search_query = kwargs.get('search')
        if search_query:
            domain.append(('name', 'ilike', search_query))

        state_filter = kwargs.get('state')
        if state_filter in ['draft', 'released']:
            domain.append(('state', '=', state_filter))

        limit = int(kwargs.get('limit', 20))
        offset = int(kwargs.get('offset', 0))

        movies = request.env['movie.movie'].sudo().search(domain, limit=limit, offset=offset, order='id asc')
        total_count = request.env['movie.movie'].sudo().search_count(domain)

        data = []
        for m in movies:
            data.append({
                'id': m.id,
                'name': m.name,
                'state': m.state,
                'release_date': m.release_date,
                'duration': m.duration,
                'rating_star': m.rating,
                'avg_rating': m.avg_rating,
                'review_count': m.review_count,
                'studio': m.studio_id.name if m.studio_id else None,
                'genres': m.genre_ids.mapped('name'),
            })

        return self._json_response({
            'status': 'success',
            'code': 200,
            'meta': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'returned': len(data),
            },
            'data': data
        })

    @http.route('/api/v1/movies/<int:movie_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_movie_detail(self, movie_id, **kwargs):
        """
        GET /api/v1/movies/<id>
        Mengambil informasi lengkap satu film beserta relasi review & artis.
        """
        is_authenticated, err_msg = self._authenticate_request()
        if not is_authenticated:
            return self._json_response({'status': 'error', 'code': 401, 'message': err_msg}, status=401)

        movie = request.env['movie.movie'].sudo().browse(movie_id)
        if not movie.exists():
            return self._json_response({
                'status': 'error',
                'code': 404,
                'message': f"Film dengan ID {movie_id} tidak ditemukan."
            }, status=404)

        reviews = []
        for rev in movie.review_ids:
            reviews.append({
                'id': rev.id,
                'author': rev.name,
                'score': rev.score,
                'comment': rev.comment,
            })

        artists = []
        for art in movie.artist_ids:
            artists.append({
                'id': art.id,
                'name': art.name,
                'role': getattr(art, 'role', 'artist'),
            })

        data = {
            'id': movie.id,
            'name': movie.name,
            'state': movie.state,
            'release_date': movie.release_date,
            'duration': movie.duration,
            'synopsis': movie.synopsis,
            'rating_star': movie.rating,
            'avg_rating': movie.avg_rating,
            'review_count': movie.review_count,
            'studio': {
                'id': movie.studio_id.id if movie.studio_id else None,
                'name': movie.studio_id.name if movie.studio_id else None,
            },
            'genres': movie.genre_ids.mapped('name'),
            'cast_and_crew': artists,
            'reviews': reviews,
        }

        return self._json_response({'status': 'success', 'code': 200, 'data': data})

    @http.route('/api/v1/movies', type='http', auth='none', methods=['POST'], csrf=False)
    def create_movie(self, **kwargs):
        """
        POST /api/v1/movies
        Membuat film baru melalui API eksternal.
        Menerima payload JSON raw body.
        """
        is_authenticated, err_msg = self._authenticate_request()
        if not is_authenticated:
            return self._json_response({'status': 'error', 'code': 401, 'message': err_msg}, status=401)

        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': 'Format payload tidak valid. Harap kirimkan format JSON valid.'
            }, status=400)

        name = payload.get('name')
        if not name:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': "Field 'name' wajib diisi."
            }, status=400)

        vals = {
            'name': name,
            'duration': payload.get('duration', 90),
            'release_date': payload.get('release_date') or False,
            'synopsis': payload.get('synopsis', ''),
            'rating': str(payload.get('rating', '0')),
            'state': 'draft',
        }

        try:
            new_movie = request.env['movie.movie'].sudo().create(vals)
            new_movie.message_post(body="🌐 <b>Film dibuat via External REST API</b> (Authorized Client).")
            return self._json_response({
                'status': 'success',
                'code': 201,
                'message': f"Film '{new_movie.name}' berhasil dibuat.",
                'data': {
                    'id': new_movie.id,
                    'name': new_movie.name,
                    'duration': new_movie.duration,
                    'state': new_movie.state,
                }
            }, status=201)
        except Exception as e:
            return self._json_response({
                'status': 'error',
                'code': 500,
                'message': f"Gagal membuat record film: {str(e)}"
            }, status=500)

    # =========================================================================
    # 2. INBOUND WEBHOOK ENDPOINT (RECEIVING WEBHOOK FROM OUTSIDE)
    # =========================================================================

    @http.route('/api/v1/webhook/movie', type='http', auth='none', methods=['POST'], csrf=False)
    def receive_movie_webhook(self, **kwargs):
        """
        POST /api/v1/webhook/movie
        Endpoint INBOUND WEBHOOK:
        Menerima notifikasi event otomatis dari sistem luar (misal: Sistem Review Publik,
        Aplikasi Tiket Bioskop, atau Payment Gateway).
        
        Verifikasi: Header 'X-Webhook-Secret'.
        """
        headers = request.httprequest.headers
        secret = headers.get('X-Webhook-Secret')
        
        expected_secret = request.env['ir.config_parameter'].sudo().get_param(
            'jpfa_movie.webhook_secret', DEFAULT_WEBHOOK_SECRET
        )

        if not secret or secret != expected_secret:
            _logger.warning("Inbound Webhook ditolak: Secret token tidak valid.")
            return self._json_response({
                'status': 'error',
                'code': 403,
                'message': "Akses Ditolak: Secret Webhook tidak cocok (X-Webhook-Secret)."
            }, status=403)

        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': "Payload webhook harus bertipe JSON valid."
            }, status=400)

        event = payload.get('event')
        _logger.info("Menerima Inbound Webhook event: %s", event)

        # Contoh Event 1: Sistem luar menambahkan review film secara otomatis
        if event == 'new_review':
            movie_id = payload.get('movie_id')
            movie = request.env['movie.movie'].sudo().browse(movie_id)
            if not movie.exists():
                return self._json_response({
                    'status': 'error',
                    'code': 404,
                    'message': f"Film ID {movie_id} tidak ditemukan untuk diberi review."
                }, status=404)

            reviewer = payload.get('reviewer_name', 'External Webhook Bot')
            score = float(payload.get('score', 8.0))
            comment = payload.get('comment', 'Auto review from external webhook.')

            review = request.env['movie.review'].sudo().create({
                'name': reviewer,
                'movie_id': movie.id,
                'score': score,
                'comment': comment,
            })

            movie.message_post(body=f"🔔 <b>Inbound Webhook:</b> Review baru diterima dari <i>{reviewer}</i> (Skor: {score}).")
            return self._json_response({
                'status': 'success',
                'code': 200,
                'message': 'Webhook new_review berhasil diproses.',
                'review_id': review.id
            })

        # Contoh Event 2: Ping / Health check dari third-party
        elif event == 'ping':
            return self._json_response({
                'status': 'success',
                'code': 200,
                'message': 'Webhook endpoint Odoo aktif dan siap menerima data (Pong!).'
            })

        # Contoh Event 3: Rilis status film
        elif event == 'release_movie':
            movie_id = payload.get('movie_id')
            movie = request.env['movie.movie'].sudo().browse(movie_id)
            if movie.exists():
                try:
                    movie.action_release()
                    return self._json_response({
                        'status': 'success',
                        'code': 200,
                        'message': f"Film '{movie.name}' berhasil di-release via webhook."
                    })
                except Exception as e:
                    return self._json_response({'status': 'error', 'code': 400, 'message': str(e)}, status=400)

        return self._json_response({
            'status': 'ignored',
            'code': 200,
            'message': f"Event '{event}' diterima tetapi tidak ada handler khusus."
        })
