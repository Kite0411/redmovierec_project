from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from moviehub.models import Movie


class Command(BaseCommand):
    help = 'Automatically delete archived movies that are older than 30 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        # Calculate the cutoff date (30 days ago)
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Find archived movies older than 30 days
        old_archived_movies = Movie.objects.filter(
            archived_at__isnull=False,
            archived_at__lt=cutoff_date
        )
        
        count = old_archived_movies.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No archived movies to delete.'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would delete {count} archived movie(s):'))
            for movie in old_archived_movies:
                self.stdout.write(f"  - {movie.title} (archived: {movie.archived_at})")
        else:
            movies_to_delete = list(old_archived_movies.values_list('title', flat=True))
            old_archived_movies.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {count} archived movie(s):')
            )
            for title in movies_to_delete:
                self.stdout.write(f"  - {title}")
