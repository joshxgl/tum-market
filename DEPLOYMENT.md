# Deployment Guide

## Option 1: Render

1. Go to https://render.com
2. Sign up/login with GitHub
3. Click "New +" → "Web Service"
4. Select your `tum-market` repository
5. Fill in:
   - **Name**: `tum-market`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free (or Starter for better uptime)
6. Click "Create Web Service"
7. Render will generate a public URL like: `https://tum-market-xxxx.onrender.com`

**Notes:**
- Free tier may spin down after 15 min of inactivity
- Data is not persisted across restarts (use a database for production)

---

## Option 2: Railway

1. Go to https://railway.app
2. Sign up/login with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your `tum-market` repository
5. Railway auto-detects Python and reads `Procfile`
6. Click "Deploy"
7. Once deployed, Railway shows your URL like: `https://tum-market-production.up.railway.app`

**Notes:**
- Free tier includes $5 USD/month credit
- Data persists but is local JSON (upgrade to PostgreSQL for production)

---

## Option 3: Vercel (Frontend only)

If you prefer a simpler frontend-only setup on Vercel:

1. Go to https://vercel.com
2. Import your GitHub repository
3. Vercel auto-deploys the `docs/` folder
4. Use a separate backend API (Render/Railway)
5. Update `script.js` API URLs to point to your backend

---

## After Deployment

### Update API URLs
In `static/script.js` and `static/profile.html`, replace:
```javascript
fetch('/api/login', ...)  →  fetch('https://your-render-url.com/api/login', ...)
```

Or set an environment variable:
```javascript
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';
```

### Database Upgrade (Production)
Replace `listings.json` with PostgreSQL:
1. Add `psycopg2-binary` to `requirements.txt`
2. Update `app.py` to use SQLAlchemy ORM
3. Connect to a managed database (Railway, Render, or AWS RDS)

### Custom Domain
After deploying, add a custom domain in Render/Railway settings:
- Point your domain's DNS to the platform's nameservers
- Enable SSL/TLS (usually automatic)

---

## Next Steps

1. Choose Render or Railway
2. Connect your GitHub account
3. Deploy the repository
4. Test the live API endpoints
5. Share the deployed URL with your team
