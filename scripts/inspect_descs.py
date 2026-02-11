import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'redmovierec_project.settings')
django.setup()

from moviehub.models import Movie

qs = Movie.objects.all()
print('COUNT', qs.count())
for m in qs[:200]:
    desc = m.description or ''
    print(m.id, repr(m.title), len(desc))
