# 🎯 HubSpot Role Enricher MVP

A simple web app that uses Claude AI to automatically deduce and populate `role_inferred_l1` field for HubSpot contacts.

## What It Does

1. **Fetches** 5 recent contacts from your HubSpot account
2. **Analyzes** their job title, company, email, and other data
3. **Deduces** their role using Claude AI with confidence scoring
4. **Auto-saves** high-confidence deductions (>95%)
5. **Shows** low-confidence items for manual review

## Quick Setup (2 Minutes)

### 1. Install Dependencies
```bash
cd hubspot-role-enricher
pip install -r requirements.txt
```

### 2. API Keys Already Set
- HubSpot API key: ✅ In `.env`
- Claude API key: ✅ In `.env`
- No additional setup needed!

### 3. Run the App
```bash
python app.py
```

### 4. Open in Browser
Visit: `http://localhost:5000`

Click **"Start Enrichment (5 Contacts)"** button to test!

## How It Works

### Confidence Tiers

- **>95% Confidence**: Auto-saves to HubSpot ✅
  - Example: Job title is "Sales Director" → Role = Sales

- **75-95% Confidence**: Shows in review queue for approval ⚠️
  - Example: Job title is "Account Executive" → Likely Sales but needs review

- **<75% Confidence**: Shows warning, requires manual review 🚩
  - Example: Job title is "Manager" → Could be multiple roles

### Review Queue

For any contact below 95% confidence:
1. Review the suggested role and reasoning
2. Click **"Approve"** to save to HubSpot
3. Click **"Skip"** to pass

All changes sync to HubSpot in real-time.

## File Structure

```
hubspot-role-enricher/
├── app.py              # Flask backend + Claude AI logic
├── templates/
│   └── index.html      # Web dashboard UI
├── requirements.txt    # Python dependencies
├── .env               # API keys (KEEP SECRET!)
├── .gitignore         # Don't commit .env
└── README.md          # This file
```

## Role Options

The app can deduce any of these roles:
- Sales
- Marketing
- Design/Drafting
- Planning/Development
- Executive
- Approval Submission
- Approval Processing

## Testing

### Test with 5 Contacts
1. Click "Start Enrichment (5 Contacts)"
2. Wait for Claude AI to analyze
3. Review auto-approved and review queue
4. Click approve/skip as needed

### Check HubSpot
After approval, check your HubSpot account:
- Go to any contact
- You'll see `role_inferred_l1` field updated with the role

## Deploying to Production

### 1. Push to GitHub
```bash
cd hubspot-role-enricher
git init
git add .
git commit -m "Initial HubSpot Role Enricher MVP"
git remote add origin https://github.com/HikariNoOngaku/hubspot-role-enricher.git
git push -u origin main
```

### 2. Deploy to Render
1. Go to [render.com](https://render.com)
2. Create new Web Service
3. Connect your GitHub repo
4. Set Build Command: `pip install -r requirements.txt`
5. Set Start Command: `gunicorn app:app`
6. Add Environment Variables:
   - `HUBSPOT_API_KEY`
   - `CLAUDE_API_KEY`
7. Deploy!

Get a permanent URL like: `https://hubspot-role-enricher.onrender.com`

## For Your Successor

When handing off to your successor:

1. **No code knowledge needed!**
   - Just open the URL
   - Click "Start Enrichment"
   - Review and approve suggestions

2. **The process is safe**
   - High-confidence items auto-save
   - Everything else is manual approval
   - Can't accidentally overwrite wrong data

3. **How to run locally**
   ```bash
   python app.py
   ```
   Then open `http://localhost:5000`

## Troubleshooting

### "Error: Invalid API Key"
- Check `.env` file has correct keys
- Make sure keys haven't expired in HubSpot/Anthropic dashboards

### "No contacts returned"
- You might need more than 5 contacts in HubSpot
- App only tests with most recent 5

### "Claude confidence too low"
- Contact data might be incomplete
- Try manually filling in more job title details in HubSpot

## Next Steps

1. Test with 5 contacts first ✅
2. If working, enrich all contacts
3. Deploy to Render for production use
4. Set up scheduled enrichment (optional)

---

**Need help?** Check the dashboard for error messages!
