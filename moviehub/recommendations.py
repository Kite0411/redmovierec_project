from collections import Counter
from .models import Rating

def get_recommendations(user):
    user_ratings = Rating.objects.filter(user=user, value__gte=4)
    movie_ids = [r.movie.id for r in user_ratings]

    similar_users = Rating.objects.filter(movie__id__in=movie_ids).exclude(user=user)
    similar_users_ids = [r.user.id for r in similar_users]

    recommended_movies = Rating.objects.filter(user__id__in=similar_users_ids, value__gte=4) \
                                        .exclude(movie__id__in=movie_ids)

    movie_counter = Counter([r.movie for r in recommended_movies if getattr(r.movie, 'archived_at', None) is None])
    top_movies = [movie for movie, _ in movie_counter.most_common(5)]
    return top_movies