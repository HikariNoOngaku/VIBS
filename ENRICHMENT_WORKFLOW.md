# VIBS Enrichment Workflow - Technical Specification

## 1. CONTACT ENROLLMENT STRUCTURE

### Single Property Enrichment Flow
```
User Action → Property Selection → Contact Fetching → Batch Processing → Approval → Update CRM
```

### Step-by-Step Enrollment Process

#### STEP 1: User Selects Property
- User chooses 1 property from 42 TAXONOMY options
- **Action**: Dropdown selection triggers `loadEnrichmentStats()`
- **Data**: Property name, property options (if dropdown), property type

#### STEP 2: Fetch Contacts from HubSpot
- **Endpoint**: `/api/enrich` with action=`fetch`
- **Filter Logic**:
  ```
  1. Get all contacts from HubSpot
  2. Filter: Remove contacts where property_name is already filled
  3. Filter: Remove contacts that were enriched for this property before
  4. Apply batch size limit (1-100 contacts)
  5. Return: Array of contacts needing enrichment
  ```
- **Data Retrieved**:
  - contact_id (unique identifier)
  - firstname, lastname
  - email
  - jobtitle
  - company
  - All other properties (for AI context)

#### STEP 3: AI Enrichment Analysis
- **Input**: Contact data + Property options (if applicable)
- **Claude Prompt**:
  ```
  "Based on this contact's information: [all contact data]
   Suggest a value for the property: [property_name]
   Available options: [property_options]
   Confidence: [0-100]
   Reasoning: [explain why]"
  ```
- **Output**:
  ```json
  {
    "value": "suggested_value",
    "confidence": 85,
    "reasoning": "Based on job title and company...",
    "source": "claude_ai"
  }
  ```

#### STEP 4: Present to User (Test/Action Mode)
- **Test Mode** (Preview):
  - Show enrichment suggestion
  - No credits deducted
  - User can preview before committing

- **Action Mode** (Commit):
  - Show enrichment suggestion
  - Request confirmation: "Approve enrichment for [Contact]?"
  - If approved: 1 credit deducted, contact updated in HubSpot
  - If skipped: Contact marked as reviewed, move to next

#### STEP 5: Update CRM
- **Endpoint**: `/api/update-contact` or `/api/enrich` with action=`approve`
- **HubSpot Update**:
  ```
  1. Set property value: property_name = enriched_value
  2. Set timestamp: enriched_{property_name}_date = now()
  3. Update contact record
  4. Log enrichment source
  ```

#### STEP 6: Track Progress
- **Progress Bar**: X of Y contacts enriched
- **Calculation**:
  ```
  Total contacts needing enrichment = count
  Enriched this session = approved_count
  Progress % = (approved_count / total_count) * 100
  ```

---

## 2. DATA EXTRACTION FROM CRM

### Real-Time Contact Fetching

#### Endpoint: `/api/enrich` (action=fetch)
```python
Parameters:
- property_name: str (e.g., "role_inferred_l1")
- batch_size: int (1-100)
- enrichment_sources: list (["internal", "linkedin", "social"])
- mode: str ("test" or "action")

Response:
{
  "contacts": [
    {
      "id": "123",
      "firstname": "Alex",
      "lastname": "Hardlion",
      "email": "alex@company.com",
      "jobtitle": "Sales Director",
      "company": "TechCorp",
      "all_properties": { ... }
    },
    ...
  ],
  "total_count": 150,
  "processed_count": 5,
  "remaining_count": 145,
  "errors": []
}
```

#### Data Quality Checks
1. **Email Validation**: Contact must have email
2. **Name Check**: At least first or last name
3. **No Null Values**: Handle missing data gracefully
4. **Deduplication**: Skip if enriched before (check timestamp)

---

## 3. ERROR HANDLING & NOTIFICATIONS

### Error Scenarios & User Notifications

#### A. HubSpot API Failures

**Scenario 1: API Key Invalid**
```
❌ Error: HubSpot authentication failed
→ Action: Show notification banner
→ Message: "HubSpot API key is invalid. Please check your configuration."
→ User Action: Stop enrichment, redirect to settings
```

**Scenario 2: Rate Limiting (429)**
```
⚠️ Warning: HubSpot rate limit reached
→ Action: Show toast notification
→ Message: "HubSpot is temporarily rate-limited. Waiting 30 seconds..."
→ User Action: Auto-retry after delay
```

**Scenario 3: Contact Not Found**
```
⚠️ Warning: Contact [ID] not found in HubSpot
→ Action: Skip contact, log error
→ Message: "1 contact could not be updated. Check HubSpot logs."
→ Continue with next contact
```

#### B. Claude AI Failures

**Scenario: AI API Timeout**
```
❌ Error: Claude AI analysis failed
→ Action: Show notification
→ Message: "Could not analyze this contact. Try again?"
→ Options: [Retry] [Skip] [Manual Input]
```

#### C. User Notifications System

**Notification Types:**
1. **Success** (Green): "✅ Updated 5 contacts successfully"
2. **Warning** (Yellow): "⚠️ 1 contact skipped due to error"
3. **Error** (Red): "❌ HubSpot API unavailable"
4. **Info** (Blue): "ℹ️ Processing 50 contacts..."

**Notification Delivery:**
- Toast (top-right, 3s): Quick status updates
- Banner (top of page): Persistent warnings
- Modal: Critical errors requiring action
- Console logs: Debug information

---

## 4. AI DATA CORRELATION

### Improved Claude Prompts for Data Understanding

#### Example: Role Enrichment
```
Contact Information:
- Name: Alex Hardlion
- Email: alex@company.com
- Job Title: Sales Director
- Company: TechCorp
- Company Type: B2B SaaS
- Company Size: 500+ employees
- Phone: (555) 123-4567
- Location: New York, NY

Available Role Options:
- Sales
- Marketing
- Design/Drafting
- Planning/Development
- Executive
- Approval Submission
- Approval Processing

Task: Based on the contact's job title "Sales Director", email format (corporate),
and company size (500+ employees suggesting enterprise sales), determine the most
likely role this person plays in our target workflow.

Analysis:
1. Title explicitly says "Sales" → Strong indicator for Sales role
2. "Director" title suggests leadership → Could indicate Executive
3. Email is corporate (company domain) → Professional/enterprise context
4. Company size (500+) → Enterprise sales environment

Conclusion: "Sales" with 95% confidence
```

#### Prompt Structure for AI Correlation
```python
prompt = f"""
You are a CRM data analyst. Analyze this contact and suggest a value.

CONTACT DATA:
{contact_data_formatted}

PROPERTY TO ENRICH: {property_name}
AVAILABLE OPTIONS: {property_options}

ANALYSIS INSTRUCTIONS:
1. Review ALL provided contact information
2. Look for explicit mentions (job title, email, etc.)
3. Correlate implicit signals (company type, size, location)
4. Cross-reference with similar roles/titles in your knowledge
5. Calculate confidence based on signal strength

PROVIDE:
- Suggested value (must be from OPTIONS)
- Confidence (0-100)
- Reasoning (cite specific data points)
- Alternative suggestions (if confidence < 80)
"""
```

---

## 5. ONLINE RESOURCE ENRICHMENT ROADMAP

### Multi-Source Enrichment Strategy

#### Phase 1: LinkedIn Integration
```
Endpoint: /api/enrich-linkedin
Process:
1. Get contact email/name from HubSpot
2. Search LinkedIn for matching profile
3. Extract: Job title, company, location, skills, recommendations
4. Return: Enriched data + confidence score
5. Compare with HubSpot data for validation

Data Points:
- Current role (validate job title)
- Experience level (infer seniority)
- Skills (enrich role inference)
- Endorsements (social proof)
```

#### Phase 2: Social Media Enrichment
```
Sources: Twitter, Facebook, Instagram
Process:
1. Search for contact by name/email
2. Validate it's the correct person (location, company matches)
3. Extract: Bio, followers, engagement, interests
4. Return: Social presence + influence score

Data Points:
- Industry involvement (tweets about industry)
- Thought leadership (article shares, speaking)
- Company involvement (company mentions)
- Personal interests (hobby signals)
```

#### Phase 3: Website/Company Research
```
Process:
1. Get company from HubSpot
2. Visit company website, LinkedIn company page
3. Extract: Company type, size, growth, specialties
4. Match contact to company roles available
5. Return: Role validation + enrichment suggestions

Data Points:
- Company organization structure
- Department information
- Typical role responsibilities
- Industry positioning
```

#### Confidence Scoring Across Sources
```json
{
  "internal_ai": 85,
  "linkedin": 90,
  "social_media": 60,
  "company_website": 75,
  "combined_score": 82.5,
  "recommendation": "linkedin"  // Most reliable source
}
```

---

## 6. CONTACT ENROLLMENT & TRACKING

### Contact Lifecycle in Enrichment

```
┌─────────────────────────────────────────────────────────┐
│ CONTACT STATES IN ENRICHMENT WORKFLOW                   │
└─────────────────────────────────────────────────────────┘

STATE 1: UNENRICHED (Initial)
├─ Contact exists in HubSpot
├─ Property is empty/null
└─ No enrichment_timestamp

STATE 2: SELECTED (When fetched for enrichment)
├─ Contact included in batch
├─ AI analysis in progress
└─ Status: "Analyzing..."

STATE 3: SUGGESTED (Awaiting approval)
├─ AI suggestion ready
├─ Shown to user
└─ Status: "Review Required"

STATE 4: APPROVED (User action)
├─ User clicked "Approve"
├─ HubSpot updated with value
├─ enriched_{property}_date = now()
└─ Status: "Enriched"

STATE 5: SKIPPED (User action)
├─ User clicked "Skip"
├─ enriched_{property}_date = now() (marked as reviewed)
├─ Property remains empty
└─ Status: "Skipped"

STATE 6: FAILED (Error)
├─ Enrichment error occurred
├─ enriched_{property}_date = null
├─ Error logged
└─ Status: "Failed"
```

### Tracking Database Structure
```python
ENRICHMENT_HISTORY = {
    contact_id: {
        property_name: {
            "status": "enriched|skipped|failed",
            "value": "enriched_value",
            "confidence": 85,
            "source": "claude|linkedin|social|web",
            "enriched_date": "2026-03-25T10:30:00",
            "user": "admin123",
            "error": null or "error message"
        }
    }
}
```

---

## 7. USER CONFIRMATION & NOTIFICATION FLOW

### Critical Confirmation Points

```
┌──────────────────────────────────────────────────────────┐
│ USER CONFIRMATION CHECKPOINTS                            │
└──────────────────────────────────────────────────────────┘

CHECKPOINT 1: Start Enrichment
Dialog: "Ready to enrich [5] contacts for [Role (L1)]?"
- Info: Shows batch size, credits needed, property
- Options: [Start] [Cancel]

CHECKPOINT 2: Review Suggestion (per contact)
Dialog: "Approve enrichment for [Alex Hardlion]?"
- Show: Current value (empty) → Suggested value
- Confidence: 85% based on...
- Options: [Approve] [Skip] [Manual Edit]

CHECKPOINT 3: Complete Enrichment
Dialog: "Enrichment complete: 5 updated, 1 skipped"
- Summary: Credits spent, contacts updated
- Options: [View Results] [Continue] [Done]

CHECKPOINT 4: Error Recovery
Dialog: "HubSpot API error on contact [ID]"
- Error: "Connection timeout"
- Options: [Retry] [Skip] [Cancel All]
```

---

## 8. NEXT IMPLEMENTATION STEPS

### Priority Order:
1. ✅ Fix contact fetching to use REAL HubSpot data
2. ✅ Add comprehensive error handling with notifications
3. ✅ Add user confirmation dialogs
4. ✅ Improve Claude prompts for data correlation
5. ✅ Build LinkedIn integration foundation
6. ✅ Add progress tracking with real statistics

### Timeline:
- Week 1: Real data extraction + error handling
- Week 2: Confirmations + improved AI
- Week 3: Online resource integrations
- Week 4: Full workflow testing + optimization

---

*Document created: 2026-03-25*
*Status: READY FOR IMPLEMENTATION*
