from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import login, logout, update_session_auth_hash
from .models import Movie, UserProfile
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .models import Rating, Movie
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from .recommendations import get_recommendations
from django.db.models import Q
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import datetime
import json
from django.utils import timezone
from django.db.models import Count
from django.core.mail import send_mail
from django.conf import settings
import random
import string
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDay, TruncMonth
from django.db import connection
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.middleware.csrf import get_token
from django.http import JsonResponse


@require_GET
def admin_archived_movies_api(request):
    """Return JSON list of archived movies for admin UI population.

    This is a fallback used by the admin UI when the server-rendered
    archive table appears empty (helps handle cases where client-side
    rendering or caching hides archived rows).
    """
    # Require admin/staff access
    if not request.user or not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'forbidden'}, status=403)

    movies = Movie.objects.filter(archived_at__isnull=False).order_by('-archived_at').values(
        'id', 'title', 'genre', 'release_year', 'description', 'poster', 'archived_at'
    )
    result = []
    for m in movies:
        poster_url = ''
        try:
            if m.get('poster'):
                poster_url = f"/media/{m.get('poster')}"
        except Exception:
            poster_url = ''
        result.append({
            'id': m.get('id'),
            'title': m.get('title'),
            'genre': m.get('genre'),
            'release_year': m.get('release_year'),
            'description': m.get('description'),
            'poster': poster_url,
            'archived_at': m.get('archived_at').isoformat() if m.get('archived_at') else None,
        })
    return JsonResponse(result, safe=False)


@require_GET
def whoami_view(request):
    """Debug endpoint: returns the server's view of the current user and session.

    Use this from the browser (GET /whoami/) to confirm which username and
    session key the server associates with your request. This helps determine
    whether the unexpected switch to the 'dada' account is coming from the
    server-side session cookie or a client-side UI overwrite.
    """
    session_key = request.session.session_key
    username = None
    try:
        if request.user and request.user.is_authenticated:
            username = request.user.username
    except Exception:
        username = None
    return JsonResponse({
        'is_authenticated': bool(request.user and request.user.is_authenticated),
        'username': username,
        'session_key': session_key,
    })


@ensure_csrf_cookie
@csrf_protect
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Save optional email if provided on the custom form
            email = request.POST.get('email')
            if email:
                user.email = email
                user.save()
            login(request, user)
            return redirect('dashboard')
        else:
            # Provide a readable error message to the template
            errors = []
            for field, field_errors in form.errors.items():
                errors.append(f"{field}: {'; '.join(field_errors)}")
            error_msg = ' '.join(errors) if errors else 'Registration failed. Please check the form.'
            return render(request, 'pages/register.html', {'form': form, 'error': error_msg})
    else:
        form = UserCreationForm()
    return render(request, 'pages/register.html', {'form': form})

@ensure_csrf_cookie
@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Show welcome notification once after successful login
            try:
                request.session['show_welcome'] = True
            except Exception:
                pass
            # Redirect admins to admin panel, others to dashboard
            if user.is_superuser or user.is_staff:
                return redirect('admin_dashboard')
            return redirect('dashboard')
        else:
            # Authentication failed — show a generic error message
            error_msg = 'Invalid username or password.'
            return render(request, 'pages/login.html', {'form': form, 'error': error_msg})
    else:
        form = AuthenticationForm()
    return render(request, 'pages/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def dashboard_view(request):
    query = (request.GET.get('q') or '').strip()
    selected_genre = (request.GET.get('genre') or '').strip()
    if query:
        # Split query into tokens so multi-word searches match titles in any order
        tokens = [t for t in query.split() if t]
        if tokens:
            q_objects = Q()
            # Require each token to appear in title OR genre (AND across tokens)
            for token in tokens:
                token_q = Q(title__icontains=token) | Q(genre__icontains=token)
                q_objects &= token_q
            movies = Movie.objects.filter(q_objects, archived_at__isnull=True).distinct()
        else:
            movies = Movie.objects.all()
    else:
        movies = Movie.objects.filter(archived_at__isnull=True)

    # Apply genre filter if provided. Movies may have multiple genres stored
    # in the `genre` CharField (comma-separated). We do a case-insensitive
    # contains match so that partial/combined genre strings still match.
    if selected_genre:
        movies = movies.filter(genre__icontains=selected_genre)

    # Compute top picks safely: avoid querying Rating model if DB migrations
    # haven't added the new `created_at` column yet. When created_at is
    # missing, skip rating-based computations to prevent OperationalError.
    def _table_has_column(model, column_name):
        try:
            table_name = model._meta.db_table
            with connection.cursor() as cursor:
                cols = [c.name for c in connection.introspection.get_table_description(cursor, table_name)]
            return column_name in cols
        except Exception:
            return False

    rating_table_ok = _table_has_column(Rating, 'created_at')

    if rating_table_ok:
        top_rated = sorted(movies, key=lambda m: m.average_rating(), reverse=True)[:5]
    else:
        # Fallback: just take first 5 movies when ratings can't be queried
        top_rated = list(movies[:5])

    user_ratings = {}
    recommended_movies = []
    if request.user.is_authenticated and rating_table_ok:
        try:
            ratings = Rating.objects.filter(user=request.user)
            user_ratings = {r.movie.id: r.value for r in ratings}
            recommended_movies = get_recommendations(request.user)
        except Exception:
            user_ratings = {}
            recommended_movies = []

    # If a search query is active, filter recommended movies to only those matching the search
    if query and recommended_movies:
        tokens = [t for t in query.split() if t]
        filtered_recs = []
        for m in recommended_movies:
            # Check if all tokens appear in title or genre
            matches = all(token.lower() in (m.title or '').lower() or token.lower() in (m.genre or '').lower() for token in tokens)
            if matches:
                filtered_recs.append(m)
        recommended_movies = filtered_recs

    # If a genre is selected, also filter recommended movies list
    if selected_genre and recommended_movies:
        recommended_movies = [m for m in recommended_movies if selected_genre.lower() in (m.genre or '').lower()]

    # Show the one-time welcome notification if set in session (set during login)
    show_welcome = False
    try:
        show_welcome = bool(request.session.pop('show_welcome', False))
    except Exception:
        show_welcome = False

    # Build a list of available genres (split by comma) from all movies so
    # the template can render a filter dropdown. Normalize and dedupe.
    all_genres = set()
    for m in Movie.objects.filter(archived_at__isnull=True):
        if m.genre:
            parts = [p.strip().replace('-', '') for p in m.genre.split(',') if p.strip()]
            for p in parts:
                all_genres.add(p)

    genres = sorted(all_genres)

    # Ensure recommended movies appear in the 'movies' list so "Top Picks"
    # are also visible in "All Movies". This keeps the UI consistent when
    # filters or queries would otherwise hide recommended items.
    # However, when searching, only include recommended movies that match the search.
    try:
        # Convert queryset to list for safe mutation
        movies_list = list(movies) if not isinstance(movies, list) else movies
        existing_ids = {m.id for m in movies_list if getattr(m, 'id', None) is not None}
        if recommended_movies:
            for rm in recommended_movies:
                if getattr(rm, 'id', None) and rm.id not in existing_ids:
                    # When searching or filtering by genre, only add recommended movies
                    # that are already in the search/filter results
                    if query or selected_genre:
                        # Skip: only add if already in movies_list (which was filtered by search)
                        continue
                    # No search/genre filter: insert all recommended items near the top
                    movies_list.insert(0, rm)
                    existing_ids.add(rm.id)
        movies = movies_list
    except Exception:
        # Fail safely: keep original `movies` queryset if anything goes wrong
        pass

    return render(request, 'pages/dashboard.html', {
        'movies': movies,
        'top_rated': top_rated,
        'user_ratings': user_ratings,
        'recommended_movies': recommended_movies,
        'show_welcome': show_welcome,
        'genres': genres,
        'selected_genre': selected_genre,
    })

def home_redirect(request):
    return redirect('dashboard')

@login_required
def rate_movie_view(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == "POST":
        value = int(request.POST.get(f'rating_{movie.id}', 0))
        try:
            rating, created = Rating.objects.get_or_create(user=request.user, movie=movie)
            rating.value = value
            rating.save()
            # If this was an AJAX/fetch request, return JSON so client can handle it
            if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                # Return both the user's rating and the new average rating
                return JsonResponse({
                    'status': 'ok',
                    'value': rating.value,
                    'average_rating': movie.average_rating()
                })
        except Exception:
            # If DB schema isn't migrated yet, avoid crashing; show a message instead
            messages.error(request, 'Unable to save rating right now. Please try again after applying migrations.')
    # For non-AJAX posts, redirect back to the page that submitted the rating
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('dashboard')


# Admin Views
def is_admin(user):
    return user.is_superuser or user.is_staff


@ensure_csrf_cookie
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_dashboard(request):
    # Only admin/staff users can access the admin dashboard
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
        return redirect('dashboard')
    
    # Admin filters (by genre and release year)
    admin_genre = (request.GET.get('admin_genre') or '').strip()
    admin_year = (request.GET.get('admin_year') or '').strip()

    # Show only non-archived movies
    movies = Movie.objects.filter(archived_at__isnull=True).order_by('-id')
    if admin_genre:
        movies = movies.filter(genre__icontains=admin_genre)
    if admin_year:
        try:
            movies = movies.filter(release_year=int(admin_year))
        except ValueError:
            pass
    
    # Get archived movies for archive section
    archived_movies = Movie.objects.filter(archived_at__isnull=False).order_by('-archived_at')
    
    users = User.objects.filter(is_superuser=False, is_staff=False)  # Only show regular users
    # Safely fetch ratings: if the DB lacks the `created_at` column (migrations
    # not applied), avoid querying Rating to prevent OperationalError.
    def _table_has_column(model, column_name):
        try:
            table_name = model._meta.db_table
            with connection.cursor() as cursor:
                cols = [c.name for c in connection.introspection.get_table_description(cursor, table_name)]
            return column_name in cols
        except Exception:
            return False

    ratings = []
    if _table_has_column(Rating, 'created_at'):
        try:
            ratings = list(Rating.objects.all())
        except Exception:
            ratings = []
    
    # Calculate average rating (handle ratings as queryset or list)
    try:
        if hasattr(ratings, 'exists'):
            if ratings.exists():
                avg_rating = round(sum(r.value for r in ratings) / ratings.count(), 1)
            else:
                avg_rating = 0
        else:
            # ratings is a list
            if ratings:
                avg_rating = round(sum(r.value for r in ratings) / len(ratings), 1)
            else:
                avg_rating = 0
    except Exception:
        avg_rating = 0
    
    # Provide admin's profile (if any) to prefill admin profile form
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Prepare available genres and years for admin filters (from all movies)
    all_genres = set()
    for m in Movie.objects.all():
        if m.genre:
            parts = [p.strip().replace('-', '') for p in m.genre.split(',') if p.strip()]
            for p in parts:
                all_genres.add(p)
    available_genres = sorted(all_genres)

    available_years = sorted({m.release_year for m in Movie.objects.filter(archived_at__isnull=True) if m.release_year}, reverse=True)

    # STATISTICS: rating activity chart data
    stats_range = request.GET.get('stats_range', 'weekly')  # weekly, monthly, yearly
    # We default to counting active users (unique users who rated in the period).
    stats_metric = request.GET.get('stats_metric', 'active_users')  # kept for compatibility but default is active_users
    now = timezone.now()
    stats_labels = []
    stats_data = []

    try:
        # Only run aggregation if the DB table has the 'created_at' column (migrations applied)
        table_name = Rating._meta.db_table
        with connection.cursor() as cursor:
            cols = [c.name for c in connection.introspection.get_table_description(cursor, table_name)]

        if 'created_at' in cols:
            # Build counts per requested range. We will compute raw counts (distinct active users)
            # and a presence flag (1 if count>0 else 0). Monthly now shows last 3 months; yearly last 3 years.
            if stats_range == 'weekly':
                # Last 4 weeks (week = Mon-Sun). Show 4 bars, oldest -> newest.
                current_monday = (now.date() - datetime.timedelta(days=now.weekday()))
                for i in range(3, -1, -1):
                    week_start = current_monday - datetime.timedelta(weeks=i)
                    week_end = week_start + datetime.timedelta(days=6)
                    # Count distinct active users who rated in this week
                    count = Rating.objects.filter(created_at__date__gte=week_start, created_at__date__lte=week_end).values('user').distinct().count()
                    # Format label with dates (e.g., "Nov 10 - Nov 16, 2025")
                    if week_start.year == week_end.year:
                        label = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
                    else:
                        label = f"{week_start.strftime('%b %d, %Y')} - {week_end.strftime('%b %d, %Y')}"
                    stats_labels.append(label)
                    stats_data.append(count)

            elif stats_range == 'monthly':
                # Last 3 months (calendar months). Show 3 bars, oldest -> newest.
                first_of_month = datetime.date(now.year, now.month, 1)

                def month_shift(dt, shift):
                    year = dt.year + ((dt.month - 1 + shift) // 12)
                    month = (dt.month - 1 + shift) % 12 + 1
                    return datetime.date(year, month, 1)

                for i in range(2, -1, -1):
                    m = month_shift(first_of_month, -i)
                    # Count distinct active users who rated in this month
                    c = Rating.objects.filter(created_at__year=m.year, created_at__month=m.month).values('user').distinct().count()
                    # Format label (e.g., "November 2025")
                    label = m.strftime('%B %Y')
                    stats_labels.append(label)
                    stats_data.append(c)

            else:  # yearly
                # Last 3 years (calendar years). Show 3 bars, oldest -> newest.
                for i in range(2, -1, -1):
                    y = now.year - i
                    c = Rating.objects.filter(created_at__year=y).values('user').distinct().count()
                    stats_labels.append(str(y))
                    stats_data.append(c)
        else:
            # migrations not applied yet or column missing; leave empty
            stats_labels = []
            stats_data = []
    except Exception:
        # If anything goes wrong (DB locked, sqlite missing column, etc.) keep the page working
        stats_labels = []
        stats_data = []

    # JSON-encode for safe inclusion in template
    try:
        stats_labels_json = json.dumps(stats_labels)
        # stats_data currently holds raw distinct-user counts per period
        stats_counts_json = json.dumps(stats_data)

        # Convert raw counts into a 0-5 activity score for visualisation.
        # If there's any activity, scale relative to the maximum observed
        # count across the selected periods so the chart fits a 0-5 scale.
        max_count = max(stats_data) if stats_data else 0
        if max_count and max_count > 0:
            stats_scores = [int(round((int(c) / float(max_count)) * 5)) if c is not None else 0 for c in stats_data]
            # clamp to [0,5]
            stats_scores = [max(0, min(5, s)) for s in stats_scores]
        else:
            # No activity recorded: keep zeros
            stats_scores = [0 for _ in stats_data]

        stats_data_json = json.dumps(stats_scores)
    except Exception:
        stats_labels_json = '[]'
        stats_counts_json = '[]'
        stats_data_json = '[]'

    return render(request, 'pages/admin_dashboard.html', {
        'movies': list(movies),
        'archived_movies': list(archived_movies),
        'ratings': ratings,
        'users': users,
        'avg_rating': avg_rating,
        'profile': profile,
        'stats_labels': stats_labels_json,
        'stats_data': stats_data_json,
        'stats_counts': stats_counts_json,
        'stats_range': stats_range,
        'stats_metric': stats_metric,
        'admin_genre': admin_genre,
        'admin_year': admin_year,
        'available_genres': available_genres,
        'available_years': available_years,
    })


@require_GET
@ensure_csrf_cookie
def csrf_token_view(request):
    # Ensure the CSRF cookie is set and return the token for client-side usage
    token = get_token(request)
    return JsonResponse({'csrfToken': token})


@require_GET
def movie_recommendation_status(request):
    """Return whether the given movie_id is recommended for the current user.

    Useful for client-side logic to decide whether a restored movie should
    appear in the Top Picks section for this user.
    """
    movie_id = request.GET.get('movie_id')
    try:
        movie_id = int(movie_id)
    except Exception:
        return JsonResponse({'recommended': False})

    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'recommended': False})

    try:
        recommended = get_recommendations(request.user)
    except Exception:
        recommended = []

    for m in recommended:
        try:
            if m.id == movie_id and getattr(m, 'archived_at', None) is None:
                poster_url = ''
                try:
                    if m.poster:
                        poster_url = m.poster.url
                except Exception:
                    poster_url = ''
                return JsonResponse({
                    'recommended': True,
                    'id': m.id,
                    'title': m.title,
                    'genre': m.genre,
                    'release_year': m.release_year,
                    'description': m.description,
                    'poster': poster_url,
                })
        except Exception:
            continue

    return JsonResponse({'recommended': False})


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def add_movie(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        genre = request.POST.get('genre')
        release_year = request.POST.get('release_year')
        description = request.POST.get('description')
        poster = request.FILES.get('poster')

        movie = Movie.objects.create(
            title=title,
            genre=genre,
            release_year=release_year,
            description=description,
            poster=poster
        )
        # If this is an AJAX/fetch request, return JSON so client can update the UI immediately.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            poster_url = ''
            try:
                if movie.poster:
                    poster_url = movie.poster.url
            except Exception:
                poster_url = ''
            return JsonResponse({'status': 'ok', 'action': 'added', 'id': movie.id, 'title': movie.title, 'poster': poster_url})

        messages.success(request, f"Movie '{movie.title}' added successfully.")
        return redirect('admin_dashboard')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def edit_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    
    if request.method == 'POST':
        movie.title = request.POST.get('title')
        movie.genre = request.POST.get('genre')
        movie.release_year = request.POST.get('release_year')
        movie.description = request.POST.get('description')
        if request.FILES.get('poster'):
            movie.poster = request.FILES.get('poster')
        movie.save()
        
        # If this is an AJAX request, return JSON so client can update the UI immediately
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            poster_url = ''
            try:
                if movie.poster:
                    poster_url = movie.poster.url
            except Exception:
                poster_url = ''
            return JsonResponse({
                'status': 'ok',
                'action': 'edited',
                'id': movie.id,
                'title': movie.title,
                'genre': movie.genre,
                'release_year': movie.release_year,
                'description': movie.description,
                'poster': poster_url,
            })
        
        messages.success(request, f"Movie '{movie.title}' updated successfully.")
        return redirect('admin_dashboard')
    
    # Prepare the same context as admin_dashboard so the template can render correctly
    movies = Movie.objects.all()
    ratings = Rating.objects.all()
    users = User.objects.filter(is_superuser=False, is_staff=False)
    if ratings.exists():
        avg_rating = round(sum(r.value for r in ratings) / ratings.count(), 1)
    else:
        avg_rating = 0

    return render(request, 'pages/admin_dashboard.html', {
        'movies': movies,
        'ratings': ratings,
        'users': users,
        'avg_rating': avg_rating,
        'movie': movie,
    })


@require_http_methods(['POST'])
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def archive_movie(request, movie_id):
    """Archive a movie instead of deleting it."""
    movie = get_object_or_404(Movie, id=movie_id)
    movie.archived_at = timezone.now()
    movie.save()
    # If this is an AJAX request, return JSON to allow immediate UI updates
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'action': 'archived',
            'id': movie.id,
            'title': movie.title,
            'archived_at': movie.archived_at.isoformat() if movie.archived_at else None,
        })
    messages.success(request, f"Movie '{movie.title}' has been archived.")
    return redirect('admin_dashboard')
@require_http_methods(['POST'])
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def restore_movie(request, movie_id):
    """Restore an archived movie."""
    movie = get_object_or_404(Movie, id=movie_id)
    movie.archived_at = None
    movie.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        poster_url = ''
        try:
            if movie.poster:
                poster_url = movie.poster.url
        except Exception:
            poster_url = ''
        return JsonResponse({
            'status': 'ok',
            'action': 'restored',
            'id': movie.id,
            'title': movie.title,
            'genre': movie.genre,
            'release_year': movie.release_year,
            'description': movie.description,
            'poster': poster_url,
        })
    messages.success(request, f"Movie '{movie.title}' has been restored.")
    return redirect('admin_dashboard')


@require_GET
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_movie_api(request, movie_id):
    """Return JSON details for a single movie (admin use)."""
    movie = get_object_or_404(Movie, id=movie_id)
    poster_url = ''
    try:
        if movie.poster:
            poster_url = movie.poster.url
    except Exception:
        poster_url = ''
    return JsonResponse({
        'id': movie.id,
        'title': movie.title,
        'genre': movie.genre,
        'release_year': movie.release_year,
        'description': movie.description,
        'poster': poster_url,
        'average_rating': movie.average_rating(),
        'rating_count': movie.ratings.count(),
    })


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def permanently_delete_movie(request, movie_id):
    """Permanently delete an archived movie."""
    movie = get_object_or_404(Movie, id=movie_id)
    title = movie.title
    movie.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({
            'status': 'ok',
            'action': 'deleted',
            'id': movie_id,
            'title': title,
        })
    messages.success(request, f"Movie '{title}' has been permanently deleted.")
    return redirect('admin_dashboard')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def delete_movie(request, movie_id):
    """Legacy endpoint - now archives instead of deleting."""
    movie = get_object_or_404(Movie, id=movie_id)
    movie.archived_at = timezone.now()
    movie.save()
    return redirect('admin_dashboard')


@login_required
def edit_profile(request):
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        
        if action == 'profile':
            # Update profile info
            email = request.POST.get('email', '').strip()
            bio = request.POST.get('bio', '').strip()
            
            # Validate email
            if not email:
                return render(request, 'pages/edit_profile.html', {
                    'error': 'Email is required.',
                    'profile': profile
                })
            
            # Update user email
            request.user.email = email
            request.user.save()
            
            # Update profile bio
            profile.bio = bio
            profile.save()
            
            return render(request, 'pages/edit_profile.html', {
                'success': 'Profile updated successfully!',
                'profile': profile
            })
        
        elif action == 'password':
            # Change password
            old_password = request.POST.get('old_password', '')
            new_password1 = request.POST.get('new_password1', '')
            new_password2 = request.POST.get('new_password2', '')
            
            # Validate old password
            if not request.user.check_password(old_password):
                return render(request, 'pages/edit_profile.html', {
                    'error': 'Current password is incorrect.',
                    'profile': profile,
                    'show_password_form': True
                })
            
            # Validate new passwords match
            if new_password1 != new_password2:
                return render(request, 'pages/edit_profile.html', {
                    'error': 'New passwords do not match.',
                    'profile': profile,
                    'show_password_form': True
                })
            
            # Validate password length
            if len(new_password1) < 8:
                return render(request, 'pages/edit_profile.html', {
                    'error': 'Password must be at least 8 characters long.',
                    'profile': profile,
                    'show_password_form': True
                })
            
            # Change password
            request.user.set_password(new_password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            
            return render(request, 'pages/edit_profile.html', {
                'success': 'Password changed successfully!',
                'profile': profile
            })
    
    return render(request, 'pages/edit_profile.html', {'profile': profile})


@require_GET
def movies_updates_api(request):
    """API endpoint for polling new movies.
    
    Query params:
    - since_id: return movies with id > since_id (for pagination/polling)
    
    Returns JSON array of movies with id, title, genre, release_year, description, poster.
    Only returns non-archived movies.
    """
    since_id = request.GET.get('since_id', '0')
    try:
        since_id = int(since_id)
    except (ValueError, TypeError):
        since_id = 0
    
    # Fetch non-archived movies with id > since_id, ordered by id ascending
    movies = Movie.objects.filter(archived_at__isnull=True, id__gt=since_id).order_by('id').values(
        'id', 'title', 'genre', 'release_year', 'description', 'poster'
    )
    
    result = []
    for movie in movies:
        movie_data = {
            'id': movie['id'],
            'title': movie['title'],
            'genre': movie['genre'],
            'release_year': movie['release_year'],
            'description': movie['description'],
        }
        # Safely include poster URL if file exists
        if movie['poster']:
            try:
                # Construct the poster URL
                poster_url = f"/media/{movie['poster']}"
                movie_data['poster'] = poster_url
            except Exception:
                movie_data['poster'] = ''
        else:
            movie_data['poster'] = ''
        result.append(movie_data)
    
    return JsonResponse(result, safe=False)


# Store OTPs temporarily (in production, use cache or database)
_otp_storage = {}

@require_POST
def send_otp(request):
    """Send OTP to user's email for password reset"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        
        if not email:
            return JsonResponse({'status': 'error', 'message': 'Email is required'}, status=400)
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'No account found with this email'}, status=404)
        
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Store OTP with timestamp (expires in 10 minutes)
        _otp_storage[email] = {
            'otp': otp,
            'timestamp': timezone.now()
        }
        
        # Send email
        try:
            subject = 'FilmOracle - Password Reset OTP'
            message = f"""Hello {user.username},

You requested a password reset for your FilmOracle account.

Your OTP code is: {otp}

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
FilmOracle Team"""
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return JsonResponse({'status': 'success', 'message': 'OTP sent to your email'})
        except Exception as e:
            print(f"Error sending email: {e}")
            return JsonResponse({'status': 'error', 'message': 'Failed to send email. Please try again.'}, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    except Exception as e:
        print(f"Error in send_otp: {e}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)


@require_POST
def reset_password_with_otp(request):
    """Reset password using OTP verification"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        otp = data.get('otp', '').strip()
        new_password = data.get('new_password', '')
        
        if not all([email, otp, new_password]):
            return JsonResponse({'status': 'error', 'message': 'All fields are required'}, status=400)
        
        # Check if OTP exists and is valid
        if email not in _otp_storage:
            return JsonResponse({'status': 'error', 'message': 'OTP not found or expired'}, status=400)
        
        stored_otp_data = _otp_storage[email]
        stored_otp = stored_otp_data['otp']
        timestamp = stored_otp_data['timestamp']
        
        # Check if OTP has expired (10 minutes)
        if (timezone.now() - timestamp).total_seconds() > 600:
            del _otp_storage[email]
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please request a new one.'}, status=400)
        
        # Verify OTP
        if otp != stored_otp:
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP'}, status=400)
        
        # Get user and reset password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Remove OTP from storage
            del _otp_storage[email]
            
            return JsonResponse({'status': 'success', 'message': 'Password reset successfully'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    except Exception as e:
        print(f"Error in reset_password_with_otp: {e}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)


@login_required
@require_GET
def get_top_picks_api(request):
    """API endpoint to get recommended movies (top picks) for the current user.
    
    Returns a JSON list of recommended movies with their details.
    """
    try:
        recommended_movies = get_recommendations(request.user)
        
        result = []
        for movie in recommended_movies:
            poster_url = ''
            try:
                if movie.poster:
                    poster_url = f"/media/{movie.poster}"
            except Exception:
                poster_url = ''
            
            # Get average rating and rating count
            avg_rating = 0
            rating_count = 0
            try:
                ratings = Rating.objects.filter(movie=movie)
                if ratings.exists():
                    rating_count = ratings.count()
                    avg_rating = sum(r.rating for r in ratings) / rating_count
            except Exception:
                pass
            
            result.append({
                'id': movie.id,
                'title': movie.title,
                'genre': movie.genre or '',
                'release_year': movie.release_year or '',
                'description': movie.description or '',
                'poster': poster_url,
                'average_rating': round(avg_rating, 1) if avg_rating else 0,
                'rating_count': rating_count,
            })
        
        return JsonResponse(result, safe=False)
    
    except Exception as e:
        print(f"Error in get_top_picks_api: {e}")
        return JsonResponse({'error': 'Failed to fetch recommendations'}, status=500)


def admin_users_api(request):
    """API endpoint to fetch all users data for admin dashboard"""
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        # Fetch regular users only (not admins)
        users = User.objects.filter(is_superuser=False, is_staff=False).order_by('-date_joined')
        
        result = []
        for user in users:
            try:
                rating_count = user.rating_set.count()
            except Exception:
                rating_count = 0
            
            result.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'ratings_given': rating_count,
                'date_joined': user.date_joined.strftime('%b %d, %Y') if user.date_joined else 'Unknown',
                'date_joined_iso': user.date_joined.isoformat() if user.date_joined else '',
            })
        
        return JsonResponse(result, safe=False)
    
    except Exception as e:
        print(f"Error in admin_users_api: {e}")
        return JsonResponse({'error': 'Failed to fetch users'}, status=500)


def admin_ratings_api(request):
    """API endpoint to fetch all ratings data for admin dashboard"""
    if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        # Check if created_at column exists in Rating table
        def _table_has_column(model, column_name):
            try:
                table_name = model._meta.db_table
                with connection.cursor() as cursor:
                    cols = [c.name for c in connection.introspection.get_table_description(cursor, table_name)]
                return column_name in cols
            except Exception:
                return False
        
        ratings = []
        if _table_has_column(Rating, 'created_at'):
            try:
                ratings = Rating.objects.all().order_by('-created_at')
            except Exception:
                ratings = []
        
        result = []
        for rating in ratings:
            try:
                result.append({
                    'id': rating.id,
                    'user': rating.user.username if rating.user else 'Unknown',
                    'movie': rating.movie.title if rating.movie else 'Unknown',
                    'value': rating.value,
                    'created_at': rating.created_at.strftime('%b %d, %Y') if hasattr(rating, 'created_at') and rating.created_at else 'Recent',
                    'created_at_iso': rating.created_at.isoformat() if hasattr(rating, 'created_at') and rating.created_at else '',
                })
            except Exception:
                pass
        
        return JsonResponse(result, safe=False)
    
    except Exception as e:
        print(f"Error in admin_ratings_api: {e}")
        return JsonResponse({'error': 'Failed to fetch ratings'}, status=500)