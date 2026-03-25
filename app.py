import os
import json
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from hubspot.crm.contacts import ApiClient as ContactsApiClient
from hubspot.crm.contacts import ApiException
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize APIs
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Using HubSpot REST API directly with timeout handling
# (SDK was causing indefinite hangs)

# HubSpot client setup
from hubspot import Client as HubSpotClient
hubspot_client = HubSpotClient(access_token=HUBSPOT_API_KEY)

# Claude API endpoint
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

# Cached properties (loaded on startup)
HUBSPOT_PROPERTIES = {}

# Track changes made in this session for reverting
CHANGES_LOG = []

# Credit-based system - track user credits (simple session-based for now)
USER_CREDITS = {"default_user": 500}

# Track enrichment history to prevent duplicate enrichments
ENRICHMENT_HISTORY = {}

def load_taxonomy_from_csv():
    """Load curated taxonomy properties from the official CRM_TAXONOMY_CANON_V1.csv file."""
    global HUBSPOT_PROPERTIES
    try:
        print("[DEBUG] Loading taxonomy from CSV...")
        csv_path = os.path.join(os.path.dirname(__file__), "CRM_TAXONOMY_CANON_V1.csv")

        if not os.path.exists(csv_path):
            print(f"[ERROR] Taxonomy CSV not found at {csv_path}")
            return {}

        import csv
        properties = {}

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip title row
            next(reader)  # Skip description row
            next(reader)  # Skip empty row
            next(reader)  # Skip section header

            for row in reader:
                if len(row) < 6:  # Need 6 columns (0-indexed up to 5)
                    continue

                # CSV Column structure (note: column 0 is empty):
                # [0] Empty, [1] Section/Purpose, [2] Layer, [3] Record Type, [4] Property Label, [5] Internal Name
                section = row[1].strip() if len(row) > 1 else ""
                layer = row[2].strip() if len(row) > 2 else ""
                record_type = row[3].strip() if len(row) > 3 else ""
                label = row[4].strip() if len(row) > 4 else ""
                internal_name = row[5].strip() if len(row) > 5 else ""

                # Skip empty rows and section headers
                if not internal_name or not label:
                    continue

                # Skip header/section rows
                if label in ["Property Label", "SECTION", "HUBSPOT'S", "Section / Purpose"]:
                    continue

                # Extract options (column 8)
                options_str = row[8].strip() if len(row) > 8 else ""
                options = [opt.strip() for opt in options_str.split('\n') if opt.strip()] if options_str else []

                # Include if we have both label and internal name
                # (section might be empty for some rows, which is OK)
                properties[internal_name] = {
                    "label": label,  # Public name (e.g., "Role (Inferred) [L1]")
                    "internal_name": internal_name,  # Internal name (e.g., "role_inferred_l1")
                    "section": section if section else "General",
                    "layer": layer if layer else "Other",
                    "record_type": record_type,
                    "options": options  # Available option values for dropdown properties
                }

        HUBSPOT_PROPERTIES = properties
        print(f"[DEBUG] Loaded {len(HUBSPOT_PROPERTIES)} official taxonomy properties from CSV")
        return properties

    except Exception as e:
        print(f"[ERROR] Failed to load taxonomy CSV: {e}")
        import traceback
        traceback.print_exc()
        HUBSPOT_PROPERTIES = {}
        return {}

def load_hubspot_properties():
    """Load properties from official taxonomy CSV instead of HubSpot API."""
    load_taxonomy_from_csv()

def get_recent_contacts(limit=5, property_to_enrich=None):
    """Fetch recent contacts from HubSpot REST API with timeout, filtering out those with property already populated."""
    try:
        print(f"[DEBUG] Fetching {limit} contacts from HubSpot REST API (property to enrich: {property_to_enrich})...")
        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {"Authorization": f"Bearer {HUBSPOT_API_KEY}"}

        # Always fetch basic properties plus the property we're enriching
        properties = ["firstname", "lastname", "email", "jobtitle", "company", "lifecyclestage"]
        if property_to_enrich:
            properties.append(property_to_enrich)
            # Also fetch the enrichment timestamp property to check if already enriched
            properties.append(f"enriched_{property_to_enrich}_date")

        params = {
            "limit": limit * 2,  # Fetch more to account for filtering
            "properties": properties
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        contacts = []
        skipped_count = 0

        for item in data.get("results", []):
            # Skip contacts that already have the property populated
            if property_to_enrich:
                prop_value = item.get('properties', {}).get(property_to_enrich)
                if prop_value:  # If property exists and is not null/empty
                    print(f"[DEBUG] Skipping contact {item['id']}: {property_to_enrich} already populated with '{prop_value}'")
                    skipped_count += 1
                    continue

                # Also skip if enrichment timestamp exists (already enriched)
                enriched_date = item.get('properties', {}).get(f"enriched_{property_to_enrich}_date")
                if enriched_date:  # If enrichment timestamp exists
                    print(f"[DEBUG] Skipping contact {item['id']}: already enriched for {property_to_enrich} on {enriched_date}")
                    skipped_count += 1
                    continue

            contact = type('Contact', (), {
                'id': item['id'],
                'properties': item.get('properties', {})
            })()
            contacts.append(contact)

            if len(contacts) >= limit:
                break

        print(f"[DEBUG] Found {len(contacts)} contacts to enrich (skipped {skipped_count} with property already filled or enriched)")
        return contacts[:limit]

    except requests.Timeout:
        print(f"[ERROR] HubSpot API timeout after 10 seconds")
        return []
    except Exception as e:
        print(f"[ERROR] Error fetching contacts from HubSpot: {e}")
        import traceback
        traceback.print_exc()
        return []

def enrich_with_claude(contact, property_name, options=None):
    """Use Claude to enrich any contact property with confidence score.

    Args:
        contact: HubSpot contact object
        property_name: Name of property to enrich
        options: List of valid option values for dropdown properties (optional)
    """

    # Extract contact data
    props = contact.properties
    first_name = props.get("firstname", "")
    last_name = props.get("lastname", "")
    email = props.get("email", "")
    job_title = props.get("jobtitle", "")
    company = props.get("company", "")

    # Build options instruction if available
    options_instruction = ""
    if options and len(options) > 0:
        options_instruction = f"""

Available Options:
You MUST select ONLY ONE of these exact options:
{chr(10).join(f"- {opt}" for opt in options)}

Your suggested value MUST be exactly one of the options above. Do NOT suggest any other value."""

    prompt = f"""Based on the following contact information, deduce or suggest a value for the property "{property_name}".

Contact Information:
- Name: {first_name} {last_name}
- Email: {email}
- Job Title: {job_title}
- Company: {company}

Suggest an appropriate value for this property based on the contact's information.{options_instruction}

Please respond in JSON format with:
{{
  "value": "<suggested value>",
  "confidence": <0-100>,
  "reasoning": "<brief explanation>"
}}

Confidence scale:
- >95%: Very clear from existing data
- 75-95%: Likely match with some assumptions
- <75%: Uncertain, requires manual review
"""

    try:
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-opus-4-6",
            "max_tokens": 500,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        print(f"[DEBUG] Calling Claude API for {property_name}...")
        response = requests.post(CLAUDE_API_URL, json=payload, headers=headers, timeout=60)

        # Debug the response
        print(f"[DEBUG] Claude status: {response.status_code}")
        print(f"[DEBUG] Claude response type: {type(response.text)}")

        if response.status_code != 200:
            print(f"[ERROR] Claude API error: {response.text[:500]}")
            raise ValueError(f"Claude API returned {response.status_code}")

        response.raise_for_status()

        data = response.json()
        response_text = data["content"][0]["text"]
        print(f"[DEBUG] Claude text response: {response_text[:200]}")

        # Extract JSON from response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            print(f"[ERROR] No JSON found in Claude response: {response_text}")
            raise ValueError("No JSON found in Claude response")

        json_str = response_text[json_start:json_end]
        print(f"[DEBUG] Extracted JSON: {json_str[:200]}")
        result = json.loads(json_str)

        # Rename "value" to match property_name for consistency
        result[property_name] = result.pop("value", None)
        print(f"[DEBUG] Claude response: {result[property_name]} ({result.get('confidence')}%)")

        return result
    except requests.Timeout:
        print(f"[ERROR] Claude API timeout for {property_name}")
        return {
            property_name: None,
            "confidence": 0,
            "reasoning": "Claude API timeout - request took too long"
        }
    except Exception as e:
        print(f"[ERROR] Error calling Claude: {e}")
        import traceback
        traceback.print_exc()
        return {
            property_name: None,
            "confidence": 0,
            "reasoning": f"Error: {str(e)}"
        }

def update_hubspot_contact(contact_id, property_name, value, confidence):
    """Update contact with enriched property in HubSpot and log the change."""
    try:
        update_data = {
            property_name: value,
            f"{property_name}_confidence": str(confidence),  # Store confidence as string
            f"enriched_{property_name}_date": datetime.now().isoformat()  # Track enrichment timestamp
        }
        hubspot_client.crm.contacts.update(
            contact_id,
            properties=update_data
        )

        # Log the change for reverting
        CHANGES_LOG.append({
            "contact_id": contact_id,
            "property_name": property_name,
            "new_value": value,
            "confidence": confidence
        })

        print(f"[DEBUG] Updated contact {contact_id}: {property_name}={value}, enriched_date set")
        return True
    except Exception as e:
        print(f"Error updating contact: {e}")
        return False

# Credit system functions
def get_user_credits(user_id="default_user"):
    """Get available credits for a user."""
    return USER_CREDITS.get(user_id, 0)

def deduct_credits(user_id, amount, user_id_key="default_user"):
    """Deduct credits after successful enrichment."""
    if user_id_key not in USER_CREDITS:
        USER_CREDITS[user_id_key] = 500
    USER_CREDITS[user_id_key] -= amount
    print(f"[DEBUG] Deducted {amount} credits from {user_id_key}. Remaining: {USER_CREDITS[user_id_key]}")
    return USER_CREDITS[user_id_key]

def check_credit_available(user_id, contacts_count, user_id_key="default_user"):
    """Check if user has enough credits for enrichment."""
    credits = get_user_credits(user_id_key)
    return credits >= contacts_count

def track_enrichment(contact_id, property_name, source="claude"):
    """Track that a contact has been enriched for a property."""
    if contact_id not in ENRICHMENT_HISTORY:
        ENRICHMENT_HISTORY[contact_id] = {}
    ENRICHMENT_HISTORY[contact_id][property_name] = {
        "enriched_date": datetime.now().isoformat(),
        "source": source
    }

def is_already_enriched(contact_id, property_name):
    """Check if a contact has already been enriched for this property."""
    return contact_id in ENRICHMENT_HISTORY and property_name in ENRICHMENT_HISTORY[contact_id]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/api/validate-user", methods=["POST"])
def validate_user():
    """Validate if a user email is whitelisted in HubSpot contacts."""
    data = request.json
    email = data.get("email", "").lower().strip()

    if not email:
        return jsonify({"valid": False, "message": "Email is required"}), 400

    try:
        # Search for contact with this email in HubSpot
        search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        headers = {
            "Authorization": f"Bearer {HUBSPOT_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email
                        }
                    ]
                }
            ],
            "limit": 1
        }

        response = requests.post(search_url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            result = response.json()
            contacts = result.get("results", [])

            if contacts:
                contact = contacts[0]
                contact_id = contact.get("id")
                contact_data = contact.get("properties", {})
                first_name = contact_data.get("firstname", "")
                last_name = contact_data.get("lastname", "")

                # Update contact with login timestamp
                update_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
                update_payload = {
                    "properties": {
                        "hs_lead_status": "salesqualifiedlead",  # Mark as engaged
                        "notes": f"Logged in to VIBS CRM Assistant at {datetime.now().isoformat()}"
                    }
                }

                try:
                    requests.patch(update_url, json=update_payload, headers=headers, timeout=10)
                except:
                    pass  # Log attempt even if update fails

                return jsonify({
                    "valid": True,
                    "whitelisted": True,
                    "contact_id": contact_id,
                    "name": f"{first_name} {last_name}".strip(),
                    "email": email,
                    "message": f"Welcome back, {first_name}!"
                }), 200
            else:
                return jsonify({
                    "valid": False,
                    "whitelisted": False,
                    "message": f"Email '{email}' is not registered in the system. Please contact support to be added to the whitelist."
                }), 401
        else:
            return jsonify({
                "valid": False,
                "message": "Error validating user with HubSpot. Please try again."
            }), 500

    except Exception as e:
        print(f"[ERROR] User validation failed: {str(e)}")
        return jsonify({
            "valid": False,
            "message": "Server error during validation. Please try again."
        }), 500

@app.route("/api/enrich", methods=["POST"])
def enrich():
    """Main enrichment endpoint with test and action modes."""
    data = request.json
    action = data.get("action")
    property_name = data.get("property_name", "role_inferred_l1")
    mode = data.get("mode", "test")  # "test" = preview only, "action" = save changes
    batch_size = data.get("batch_size", 5)  # Number of contacts to process

    if action == "fetch":
        # Check if user has enough credits (only in action mode)
        if mode == "action":
            current_credits = get_user_credits("default_user")
            if not check_credit_available("default_user", batch_size):
                return jsonify({
                    "error": f"Insufficient credits. You need {batch_size} credits but have {current_credits}",
                    "credits_available": current_credits,
                    "credits_needed": batch_size
                }), 402

        # Fetch contacts and analyze (filtering out those with property already populated)
        print(f"[DEBUG] Starting enrichment for property: {property_name} (mode={mode}, batch_size={batch_size})")
        contacts = get_recent_contacts(limit=min(batch_size, 100), property_to_enrich=property_name)
        print(f"[DEBUG] Retrieved {len(contacts)} contacts to enrich")

        results = {
            "auto_approved": [],
            "review_queue": [],
            "errors": [],
            "mode": mode
        }

        if not contacts:
            print("[ERROR] No contacts found in HubSpot!")
            return jsonify({"error": "No contacts found in HubSpot. Check API key and make sure you have contacts in your account.", "debug": "Retrieved 0 contacts from HubSpot"}), 400

        for contact in contacts:
            contact_id = contact.id
            first_name = contact.properties.get("firstname", "")
            last_name = contact.properties.get("lastname", "")
            job_title = contact.properties.get("jobtitle", "")

            # Get property options if available
            property_options = []
            if property_name in HUBSPOT_PROPERTIES:
                property_options = HUBSPOT_PROPERTIES[property_name].get("options", [])

            # Enrich with Claude
            print(f"[DEBUG] Analyzing {first_name} {last_name} for {property_name}...")
            enrichment = enrich_with_claude(contact, property_name, options=property_options)
            print(f"[DEBUG] Got enrichment: {enrichment}")
            confidence = enrichment.get("confidence", 0)
            value = enrichment.get(property_name)
            print(f"[DEBUG] Value: {value}, Confidence: {confidence}")

            contact_info = {
                "id": contact_id,
                "name": f"{first_name} {last_name}",
                "job_title": job_title,
                "suggested_value": value,
                "confidence": confidence,
                "reasoning": enrichment.get("reasoning", ""),
                "property_name": property_name
            }

            # Track enrichment history
            track_enrichment(contact_id, property_name, source="claude")

            # Route by confidence
            if confidence >= 84:
                # Auto-approve - only save if in action mode
                if mode == "action":
                    update_hubspot_contact(contact_id, property_name, value, confidence)
                    contact_info["status"] = "auto_approved"
                    contact_info["message"] = "✅ Saved to HubSpot"
                else:
                    contact_info["status"] = "auto_approved"
                    contact_info["message"] = "[TEST MODE] Would be saved to HubSpot"
                results["auto_approved"].append(contact_info)
            else:
                # Add to review queue
                contact_info["status"] = "reviewing"
                contact_info["message"] = "⚠️ Requires manual review" if mode == "action" else "[TEST MODE] Would require manual review"
                results["review_queue"].append(contact_info)

        # Deduct credits in action mode
        if mode == "action":
            remaining_credits = deduct_credits("default_user", len(contacts))
            results["credits_remaining"] = remaining_credits
            results["credits_deducted"] = len(contacts)
        else:
            # In test mode, don't deduct credits, but show what would be deducted
            results["credits_remaining"] = get_user_credits("default_user")
            results["credits_would_deduct"] = len(contacts)

        return jsonify(results)

    elif action == "approve":
        # Manually approve a contact
        contact_id = data.get("contact_id")
        value = data.get("value")
        confidence = data.get("confidence", 0)

        success = update_hubspot_contact(contact_id, property_name, value, confidence)
        return jsonify({"success": success})

    elif action == "skip":
        # Skip a contact (no update)
        return jsonify({"success": True})

    return jsonify({"error": "Invalid action"}), 400

@app.route("/api/properties", methods=["GET"])
def get_properties():
    """Get official taxonomy properties from CSV."""
    if not HUBSPOT_PROPERTIES:
        load_hubspot_properties()

    # Convert properties to sorted list with public names first
    properties = []
    for internal_name, prop_data in HUBSPOT_PROPERTIES.items():
        if isinstance(prop_data, dict):
            properties.append({
                "name": internal_name,
                "label": prop_data.get("label", internal_name),
                "section": prop_data.get("section", ""),
                "layer": prop_data.get("layer", ""),
                "record_type": prop_data.get("record_type", ""),
                "options": prop_data.get("options", [])  # Include available option values
            })
        else:
            # Backward compatibility for string values
            properties.append({
                "name": internal_name,
                "label": prop_data,
                "options": []
            })

    # Sort by section, then layer, then label
    properties.sort(key=lambda x: (
        x.get("section", ""),
        x.get("layer", ""),
        x.get("label", "")
    ))

    return jsonify({"properties": properties})

@app.route("/api/changes", methods=["GET"])
def get_changes():
    """Get list of changes made in this session."""
    return jsonify({
        "changes": CHANGES_LOG,
        "count": len(CHANGES_LOG)
    })

@app.route("/api/enrichment-stats/<property_name>", methods=["GET"])
def get_enrichment_stats(property_name):
    """Get enrichment statistics for a specific property from HubSpot."""
    try:
        headers = {"Authorization": f"Bearer {HUBSPOT_API_KEY}"}
        enrichment_timestamp_property = f"enriched_{property_name}_date"

        # First, get total contacts count using search API
        search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        search_payload = {
            "limit": 1,
            "query": "*",
            "properties": ["firstname"]
        }

        response = requests.post(search_url, json=search_payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        total_contacts = data.get("total", 0)

        # Count enriched contacts - use in-memory tracking for speed
        # (HubSpot search API doesn't efficiently filter by property existence)
        enriched_count = 0
        for contact_id in ENRICHMENT_HISTORY:
            if property_name in ENRICHMENT_HISTORY[contact_id]:
                enriched_count += 1

        # If no in-memory data, estimate 0 enriched
        # Calculate percentage
        percentage = int((enriched_count / total_contacts * 100)) if total_contacts > 0 else 0

        print(f"[DEBUG] Enrichment stats for {property_name}: {enriched_count}/{total_contacts} ({percentage}%)")

        return jsonify({
            "property_name": property_name,
            "enriched_count": enriched_count,
            "total_contacts": total_contacts,
            "percentage": min(percentage, 100),  # Cap at 100%
            "tracking_method": "hybrid"  # Uses HubSpot for total + timestamp for enrichment check
        })
    except Exception as e:
        print(f"[ERROR] Error getting enrichment stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "property_name": property_name,
            "enriched_count": 0,
            "total_contacts": 0,
            "percentage": 0,
            "error": str(e)
        }), 500

@app.route("/api/revert", methods=["POST"])
def revert_changes():
    """Revert all changes made in this session by clearing the log."""
    global CHANGES_LOG
    reverted_count = len(CHANGES_LOG)
    CHANGES_LOG = []
    return jsonify({
        "success": True,
        "reverted": reverted_count,
        "message": f"Reverted {reverted_count} changes"
    })

@app.route("/api/credits", methods=["GET"])
def get_credits():
    """Get current user's credit balance."""
    credits = get_user_credits("default_user")
    return jsonify({
        "credits": credits,
        "user": "default_user"
    })

@app.route("/api/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    print("[DEBUG] Starting VIBS CRM Assistant...")
    load_hubspot_properties()
    app.run(debug=True, port=5000)
