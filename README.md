# TUM Market

A local Flask marketplace app with a static frontend and JSON-backed data store.

## Quick setup

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run locally:

```bash
python app.py
```

3. Open `http://127.0.0.1:5000` in your browser.

## Git setup

If you want to share the app with friends and colleagues, push it to GitHub:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
# create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Deployment options

### Option 1: Railway

1. Create an account at https://railway.app
2. Create a new project and connect your GitHub repository.
3. Set the deploy command to:

```bash
gunicorn app:app
```

4. Railway will give you a public URL.

### Option 2: Render

1. Create an account at https://render.com
2. Create a new Web Service from GitHub.
3. Set the build command to:

```bash
pip install -r requirements.txt
```

4. Set the start command to:

```bash
gunicorn app:app
```

5. Render will provide a live URL.

## Notes

- This app uses SQLAlchemy with SQLite for local development and is PostgreSQL-ready for production.
- Images are stored externally on Cloudinary to preserve server capacity.
