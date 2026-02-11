# Hosting on Render (Django + SQLite)

This project is configured to be hosted as a **Web Service** on [Render](https://render.com).

## ⚠️ Important Note on SQLite Persistence
By default, Render's filesystem is **ephemeral**. This means any data saved to `db.sqlite3` will be **wiped** every time the service restarts (which happens during redeploys or at least once a day on the free tier).

**Recommendations:**
- **For Development/Demo**: SQLite is fine, but data will reset periodically.
- **For Production**:
  - **Option A (Persistent SQLite)**: Upgrade to a paid Render instance and attach a **Render Disk**. Update `settings.py` to point the database to the disk path (e.g., `/var/data/db.sqlite3`).
  - **Option B (PostgreSQL)**: Use Render's managed PostgreSQL service. The `requirements.txt` already includes `psycopg2-binary` for this purpose.

---

## Deployment Steps

### 1. Prepare your Repository
Make sure all changes are committed and pushed to your GitHub/GitLab repository.

### 2. Create a Web Service on Render
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** and select **Web Service**.
3. Connect your repository.
4. Render will automatically detect the `render.yaml` file (if you use the "Blueprints" feature) **OR** you can configure it manually:
   - **Name**: `filmoracle` (or your preferred name)
   - **Environment**: `Python`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn redmovierec_project.wsgi:application`

### 3. Configure Environment Variables
In the Render dashboard, go to the **Environment** tab and add the following:

| Key | Value | Description |
|-----|-------|-------------|
| `SECRET_KEY` | *(A long random string)* | Django's secret key. Render can generate this. |
| `DEBUG` | `False` | Set to `False` for production. |
| `ALLOWED_HOSTS` | `your-app-name.onrender.com` | Your Render domain. |
| `CLOUDINARY_URL` | `cloudinary://...` | (Optional) For persistent image uploads. |

### 4. Database Migrations
The `build.sh` script automatically runs `python manage.py migrate` during the build process, so your SQLite database will be initialized automatically.

### 5. Static Files
The project uses `WhiteNoise` to serve static files efficiently. No additional configuration is needed for static files.

---

## Technical Details
- **Framework**: Django 4.2.x
- **Server**: Gunicorn (WSGI HTTP Server)
- **Static Assets**: WhiteNoise
- **Database**: SQLite (default)
