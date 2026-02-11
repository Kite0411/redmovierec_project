from django.contrib import admin
from .models import Movie, Rating


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'genre', 'release_year', 'average_rating_display')
    list_filter = ('genre', 'release_year')
    search_fields = ('title', 'genre', 'description')
    readonly_fields = ('average_rating_display',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'genre', 'release_year')
        }),
        ('Details', {
            'fields': ('description', 'poster')
        }),
        ('Statistics', {
            'fields': ('average_rating_display',),
            'classes': ('collapse',)
        }),
    )

    def average_rating_display(self, obj):
        rating = obj.average_rating()
        if rating > 0:
            return f"⭐ {rating}/5 ({obj.ratings.count()} ratings)"
        return "No ratings yet"
    
    average_rating_display.short_description = "Average Rating"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'value', 'formatted_rating')
    list_filter = ('value', 'movie__genre')
    search_fields = ('user__username', 'movie__title')
    readonly_fields = ('user', 'movie', 'value')

    def formatted_rating(self, obj):
        return f"{obj.value}/5"
    
    formatted_rating.short_description = "Rating Stars"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser