# VIBS CRM Assistant - Project Files

## Project Overview
VIBS CRM Assistant is an AI-powered contact enrichment application for HubSpot, built with Flask and JavaScript.

**Location:** `D:\CLAUDE CODE\hubspot-role-enricher`

---

## Core Application Files

### Backend
- **`app.py`** - Flask backend application
  - HubSpot API integration
  - Claude AI enrichment engine
  - Credit system and contact filtering
  - Property management and taxonomy support

### Frontend
- **`templates/index.html`** - Main enrichment dashboard
  - Custom property dropdown organized by HubSpot taxonomy layers
  - Enrichment source selection (Internal Data, LinkedIn, Social Media, Websites)
  - Batch size slider with credit cost display
  - Testing/Action mode switching with audio feedback
  - Contact enrichment results display
  - Premium styling and animations

- **`templates/landing.html`** - Marketing landing page
  - Hero section with value proposition
  - Feature cards and benefits
  - Stats display (99% Accuracy, 10K+ Contacts/Month, 30s per Contact)
  - CTA buttons for Free Trial
  - Professional footer

- **`templates/login.html`** - User login screen
  - Email and password input
  - "Remember me" checkbox
  - Sign-in with Google option
  - Link to sign-up page

- **`templates/signup.html`** - User registration screen
  - Name, email, password, company fields
  - Terms agreement checkbox
  - Account creation button
  - Link to login page

---

## Configuration & Documentation

### Reference Files
- **`CRM_TAXONOMY_CANON_V1.csv`** - HubSpot CRM Taxonomy reference document (imported from Downloads)
  - Section 1: Customer Intelligence Taxonomy (L1 & L2 layers)
  - Section 2: Legacy CRM contact properties
  - Section 3: First Segmentation Round (February 2026)
  - Property definitions, field types, options, and descriptions

### Environment
- **`.env`** - Environment variables (NOT in repo)
  - `HUBSPOT_API_KEY` - HubSpot API access token
  - `CLAUDE_API_KEY` - Anthropic Claude API key

---

## Features Implemented

### 1. Property Management
- ✅ Custom dropdown organized by HubSpot taxonomy layers
- ✅ 421 TAXONOMY properties loaded and grouped
- ✅ Real-time search filtering
- ✅ Layer organization: STANDARD PROPERTIES → HUBSPOT FIELDS → OTHER

### 2. Enrichment Sources
- ✅ Internal Data (Claude AI analysis) - default
- ☐ LinkedIn (Professional profiles) - future
- ☐ Social Media (Twitter, Facebook, Instagram) - future
- ☐ Websites (Company & personal sites) - future

### 3. Credit System
- ✅ 500 credit starting balance
- ✅ 1 credit = 1 contact enriched
- ✅ Batch size slider (1-100 contacts)
- ✅ Dynamic credit cost display
- ✅ Credit validation before enrichment
- ✅ Deduction only in Action mode (Test mode is free)

### 4. Contact Filtering
- ✅ Skip contacts with property already populated
- ✅ Filter out pre-filled contacts to avoid duplicate enrichment
- ✅ Fetch more contacts to reach batch size if needed

### 5. Audio Feedback
- ✅ Testing mode: Softer chime (F4, C5, F5)
- ✅ Action mode: Bright bell (C5, G5, C6)
- ✅ Volume reduced to 0.08 gain for professional level

### 6. UI/UX Enhancements
- ✅ Mode switching with color palette change (Blue Testing ↔ Orange Action)
- ✅ Premium custom dropdown (no ugly datalist)
- ✅ Enrichment sources section with refined hover effects
- ✅ Batch size slider with credit cost sync
- ✅ Responsive design (mobile-friendly)

### 7. Enrichment Tracking
- ✅ Enrichment history tracking per contact/property
- ✅ Prevent duplicate enrichment
- ✅ Changes log for session management
- ✅ Revert functionality

---

## Technology Stack

### Backend
- **Flask** - Python web framework
- **HubSpot SDK** - CRM integration
- **Anthropic Claude API** - AI enrichment
- **Requests** - HTTP library with timeout handling

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Custom properties (variables), Grid, Flexbox
- **JavaScript (Vanilla)** - No jQuery/frameworks
  - Web Audio API for sound effects
  - Fetch API for backend communication
  - Event delegation for dynamic elements

### Deployment
- **Python 3.x**
- **Flask development server** (port 5000)
- **Browser compatibility**: Chrome, Firefox, Safari, Edge

---

## File Structure
```
D:\CLAUDE CODE\hubspot-role-enricher/
├── app.py                          # Flask backend
├── .env                            # Credentials (local only)
├── requirements.txt                # Python dependencies
├── CRM_TAXONOMY_CANON_V1.csv      # Taxonomy reference
├── PROJECT_FILES.md               # This file
└── templates/
    ├── index.html                 # Main dashboard
    ├── landing.html               # Marketing landing page
    ├── login.html                 # Login screen
    └── signup.html                # Sign-up screen
```

---

## Development Notes

### Recent Changes
- Implemented custom property dropdown with taxonomy layer organization
- Added enrichment source checkboxes for future integration
- Reduced audio volume to professional level
- Implemented contact filtering to skip pre-populated properties
- Premium UI styling throughout

### Next Steps
- Integrate LinkedIn API for professional profile enrichment
- Add social media data source connectors
- Implement web scraping for company research
- Build multi-source confidence scoring algorithm
- Add user authentication and persistence
- Deploy to production environment

---

## API Endpoints

### Core Enrichment
- `POST /api/enrich` - Start enrichment process
  - Parameters: action, property_name, mode, batch_size, enrichment_sources
  - Returns: auto_approved, review_queue, credits info

### Property Management
- `GET /api/properties` - Get available properties organized by TAXONOMY
- `GET /api/changes` - Get changes log for current session
- `GET /api/credits` - Get user credit balance

### Session Management
- `POST /api/revert` - Revert all changes in session
- `GET /api/health` - Health check

---

## Support & Maintenance

**Deployed on:** Flask development server
**Database:** In-memory session storage (Python dicts)
**Logging:** Console output with [DEBUG], [ERROR] prefixes

For production deployment, consider:
- PostgreSQL for persistent storage
- Redis for session management
- Gunicorn/uWSGI for production server
- Nginx for reverse proxy
- SSL/TLS encryption

---

*Document created: 2026-03-25*
*Last updated: 2026-03-25*
