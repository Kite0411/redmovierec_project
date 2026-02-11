from django.db import models
from django.contrib.auth.models import User

# User Profile model
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

# Movie model
class Movie(models.Model):
    title = models.CharField(max_length=200)
    genre = models.CharField(max_length=100)
    release_year = models.IntegerField()
    description = models.TextField()
    poster = models.ImageField(upload_to='posters/', blank=True, null=True)
    archived_at = models.DateTimeField(null=True, blank=True, help_text="When the movie was archived. Null if not archived.")

    def average_rating(self):
        try:
            ratings = self.ratings.all()
            if ratings.exists():
                return round(sum(r.value for r in ratings) / ratings.count(), 1)
            return 0
        except Exception:
            # If the ratings table/columns aren't available (migrations not applied),
            # avoid crashing the site — return 0 as a safe fallback.
            return 0

    def __str__(self):
        return self.title

# Rating model
class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, related_name='ratings', on_delete=models.CASCADE)
    value = models.IntegerField(default=0)  # 1-5
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        unique_together = ('user', 'movie')

    def __str__(self):
        return f"{self.user.username} -> {self.movie.title}: {self.value}"