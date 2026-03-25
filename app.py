import os
import json
import requests
from flask import Flask, render_template, jsonify, request
from hubspot.crm.contacts import ApiClient as ContactsApiClient
from hubspot.crm.contacts import ApiException
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize APIs
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# HubSpot client setup
from hubspot import Client as HubSpotClient
hubspot_client = HubSpotClient(access_token=HUBSPOT_API_KEY)

# Claude API endpoint
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

# Property enrichment configuration
ENRICHABLE_PROPERTIES = {
    "role_inferred_l1": {
        "label": "Role (L1)",
        "options": ["Sales", "Marketing", "Design/Drafting", "Planning/Development", "Executive", "Approval Submission", "Approval Processing"]
    },
    "industry": {
        "label": "Industry",
        "options": ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing", "Services", "Other"]
    },
    "company_size": {
        "label": "Company Size",
        "options": ["1-10", "11-50", "51-200", "201-1000", "1000+"]
    }
}

def get_recent_contacts(limit=5):
    """Fetch recent contacts from HubSpot."""
    try:
        print(f"[DEBUG] Fetching {limit} contacts from HubSpot...")
        result = hubspot_client.crm.contacts.get_page(
            limit=limit,
            properties=["firstname", "lastname", "email", "jobtitle", "company", "lifecyclestage"]
        )
        print(f"[DEBUG] Found {len(result.results)} contacts")
        return result.results
    except Exception as e:
        print(f"[ERROR] Error fetching contacts: {e}")
        import traceback
        traceback.print_exc()
        return []

def enrich_with_claude(contact, property_name, property_options):
    """Use Claude to enrich any contact property with confidence score."""

    # Extract contact data
    props = contact.properties
    first_name = props.get("firstname", "")
    last_name = props.get("lastname", "")
    email = props.get("email", "")
    job_title = props.get("jobtitle", "")
    company = props.get("company", "")

    # Build dynamic prompt
    options_text = chr(10).join([f"- {opt}" for opt in property_options])

    prompt = f"""Based on the following contact information, deduce their {property_name}.

Contact Information:
- Name: {first_name} {last_name}
- Email: {email}
- Job Title: {job_title}
- Company: {company}

Available Options:
{options_text}

Please respond in JSON format with:
{{
  "value": "<selected option from list>",
  "confidence": <0-100>,
  "reasoning": "<brief explanation>"
}}

Base confidence on how clear the deduction is:
- >95%: Very clear match from existing data
- 75-95%: Likely match but some ambiguity
- <75%: Uncertain, requires review
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

        response = requests.post(CLAUDE_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        response_text = data["content"][0]["text"]

        # Extract JSON from response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        # Rename "value" to match property_name for consistency
        result[property_name] = result.pop("value", None)

        return result
    except Exception as e:
        print(f"Error calling Claude: {e}")
        return {
            property_name: None,
            "confidence": 0,
            "reasoning": f"Error: {str(e)}"
        }

def update_hubspot_contact(contact_id, property_name, value, confidence):
    """Update contact with enriched property in HubSpot."""
    try:
        update_data = {
            property_name: value,
            f"{property_name}_confidence": str(confidence)  # Store confidence as string
        }
        hubspot_client.crm.contacts.update(
            contact_id,
            properties=update_data
        )
        return True
    except Exception as e:
        print(f"Error updating contact: {e}")
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/enrich", methods=["POST"])
def enrich():
    """Main enrichment endpoint."""
    data = request.json
    action = data.get("action")
    property_name = data.get("property_name", "role_inferred_l1")

    # Get property config
    if property_name not in ENRICHABLE_PROPERTIES:
        return jsonify({"error": f"Property {property_name} not enrichable"}), 400

    prop_config = ENRICHABLE_PROPERTIES[property_name]
    property_options = prop_config["options"]

    if action == "fetch":
        # Fetch contacts and analyze
        print(f"[DEBUG] Starting enrichment for property: {property_name}")
        contacts = get_recent_contacts(limit=5)
        print(f"[DEBUG] Retrieved {len(contacts)} contacts")

        results = {
            "auto_approved": [],
            "review_queue": [],
            "errors": []
        }

        if not contacts:
            print("[ERROR] No contacts found in HubSpot!")
            return jsonify({"error": "No contacts found in HubSpot. Check API key and make sure you have contacts in your account.", "debug": "Retrieved 0 contacts from HubSpot"}), 400

        for contact in contacts:
            contact_id = contact.id
            first_name = contact.properties.get("firstname", "")
            last_name = contact.properties.get("lastname", "")
            job_title = contact.properties.get("jobtitle", "")

            # Enrich with Claude
            print(f"[DEBUG] Analyzing {first_name} {last_name} for {property_name}...")
            enrichment = enrich_with_claude(contact, property_name, property_options)
            confidence = enrichment.get("confidence", 0)
            value = enrichment.get(property_name)
            print(f"[DEBUG] Result: {value} (confidence: {confidence}%)")

            contact_info = {
                "id": contact_id,
                "name": f"{first_name} {last_name}",
                "job_title": job_title,
                "suggested_value": value,
                "confidence": confidence,
                "reasoning": enrichment.get("reasoning", ""),
                "property_name": property_name
            }

            # Route by confidence
            if confidence >= 95:
                # Auto-approve and save
                update_hubspot_contact(contact_id, property_name, value, confidence)
                contact_info["status"] = "auto_approved"
                results["auto_approved"].append(contact_info)
            else:
                # Add to review queue
                contact_info["status"] = "reviewing"
                results["review_queue"].append(contact_info)

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
    """Get available enrichable properties."""
    return jsonify({
        "properties": [
            {
                "name": name,
                "label": config["label"],
                "options": config["options"]
            }
            for name, config in ENRICHABLE_PROPERTIES.items()
        ]
    })

@app.route("/api/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
