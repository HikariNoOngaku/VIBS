# 🎯 VIBS CRM Assistant

Intelligent contact enrichment using Claude AI. Automatically deduce and populate `role_inferred_l1` field for HubSpot contacts.

## What It Does

1. **Fetches** 5 recent contacts from your HubSpot account
2. **Analyzes** their job title, company, email, and other data
3. **Deduces** their role using Claude AI with confidence scoring
4. **Auto-saves** high-confidence deductions (>95%)
5. **Shows** low-confidence items for manual review

## Quick Setup (2 Minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. API Keys Already Set
- HubSpot API key: ✅ In `.env`
- Claude API key: ✅ In `.env`

### 3. Run the App
```bash
python app.py
```

### 4. Open in Browser
Visit: `http://localhost:5000`

Click **"Start Enrichment (5 Contacts)"** to test!

## How It Works

### Confidence Tiers

- **>95% Confidence**: Auto-saves to HubSpot ✅
- **75-95% Confidence**: Shows for review ⚠️
- **<75% Confidence**: Requires manual review 🚩

## Deploying to Production

### Deploy to Render
1. Go to [render.com](https://render.com)
2. Create new Web Service
3. Connect your GitHub repo (VIBS)
4. Set Build Command: `pip install -r requirements.txt`
5. Set Start Command: `gunicorn app:app`
6. Add Environment Variables:
   - `HUBSPOT_API_KEY`
   - `CLAUDE_API_KEY`
7. Deploy!

## For Your Successor

- **No code knowledge needed!**
- Just open the URL
- Click "Start Enrichment"
- Review and approve suggestions

---

**Live Dashboard**: Get your URL after Render deployment
