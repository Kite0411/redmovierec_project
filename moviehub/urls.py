from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.home_redirect, name='home'),
    path('rate/<int:movie_id>/', views.rate_movie_view, name='rate_movie'),
    path('csrf-token/', views.csrf_token_view, name='csrf_token'),
    path('whoami/', views.whoami_view, name='whoami'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('reset-password-otp/', views.reset_password_with_otp, name='reset_password_with_otp'),
    
    # Admin URLs
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    # Support legacy/default auth redirect path
    path('accounts/login/', views.login_view),
    path('admin-panel/movie/add/', views.add_movie, name='add_movie'),
    path('admin-panel/movie/edit/<int:movie_id>/', views.edit_movie, name='edit_movie'),
    path('admin-panel/movie/delete/<int:movie_id>/', views.delete_movie, name='delete_movie'),
    path('admin-panel/movie/archive/<int:movie_id>/', views.archive_movie, name='archive_movie'),
    path('admin-panel/movie/restore/<int:movie_id>/', views.restore_movie, name='restore_movie'),
    path('admin-panel/movie/permanently-delete/<int:movie_id>/', views.permanently_delete_movie, name='permanently_delete_movie'),
    
    # API endpoints
    path('api/movies/updates/', views.movies_updates_api, name='movies_updates'),
    path('api/admin/archived_movies/', views.admin_archived_movies_api, name='admin_archived_movies'),
    path('api/admin/movie/<int:movie_id>/', views.admin_movie_api, name='admin_movie_api'),
    path('api/admin/users/', views.admin_users_api, name='admin_users_api'),
    path('api/admin/ratings/', views.admin_ratings_api, name='admin_ratings_api'),
    path('api/movies/is_recommended/', views.movie_recommendation_status, name='movie_recommendation_status'),
    path('api/top-picks/', views.get_top_picks_api, name='get_top_picks_api'),
]