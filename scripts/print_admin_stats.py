import os
import sys
import django
import datetime

# Ensure project root is on PYTHONPATH
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'redmovierec_project.settings')
django.setup()
from django.utils import timezone
from moviehub.models import Rating

now = timezone.now()

# Weekly (last 4 weeks)
print('--- Weekly (last 4 weeks) ---')
current_monday = (now.date() - datetime.timedelta(days=now.weekday()))
weekly_labels = []
weekly_counts = []
for i in range(3, -1, -1):
    week_start = current_monday - datetime.timedelta(weeks=i)
    week_end = week_start + datetime.timedelta(days=6)
    count = Rating.objects.filter(created_at__date__gte=week_start, created_at__date__lte=week_end).values('user').distinct().count()
    weekly_labels.append(f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")
    weekly_counts.append(count)
print('labels:', weekly_labels)
print('counts:', weekly_counts)

# Monthly (last 12 months)
print('\n--- Monthly (last 12 months) ---')
first_of_month = datetime.date(now.year, now.month, 1)

def month_shift(dt, shift):
    year = dt.year + ((dt.month - 1 + shift) // 12)
    month = (dt.month - 1 + shift) % 12 + 1
    return datetime.date(year, month, 1)

monthly_labels = []
monthly_counts = []
for i in range(11, -1, -1):
    m = month_shift(first_of_month, -i)
    c = Rating.objects.filter(created_at__year=m.year, created_at__month=m.month).values('user').distinct().count()
    monthly_labels.append(m.strftime('%b %Y'))
    monthly_counts.append(c)
print('labels:', monthly_labels)
print('counts:', monthly_counts)

# Yearly (last 3 years)
print('\n--- Yearly (last 3 years) ---')
yearly_labels = []
yearly_counts = []
for i in range(2, -1, -1):
    y = now.year - i
    c = Rating.objects.filter(created_at__year=y).values('user').distinct().count()
    yearly_labels.append(str(y))
    yearly_counts.append(c)
print('labels:', yearly_labels)
print('counts:', yearly_counts)

# Scales (0-5) for weekly example
print('\n--- Scaled (weekly) ---')
if weekly_counts and max(weekly_counts) > 0:
    scaled = [round((c / max(weekly_counts)) * 5, 2) for c in weekly_counts]
else:
    scaled = [0 for _ in weekly_counts]
print('scaled:', scaled)
