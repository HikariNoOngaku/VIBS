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

# Role options from taxonomy
ROLE_OPTIONS = [
    "Sales",
    "Marketing",
    "Design/Drafting",
    "Planning/Development",
    "Executive",
    "Approval Submission",
    "Approval Processing"
]

def get_recent_contacts(limit=5):
    """Fetch recent contacts from HubSpot."""
    try:
        result = hubspot_client.crm.contacts.get_page(
            limit=limit,
            properties=["firstname", "lastname", "email", "jobtitle", "company", "lifecyclestage"]
        )
        return result.results
    except Exception as e:
        print(f"Error fetching contacts: {e}")
        return []

def deduce_role_with_claude(contact):
    """Use Claude to deduce contact role with confidence score."""

    # Extract contact data
    props = contact.properties
    first_name = props.get("firstname", "")
    last_name = props.get("lastname", "")
    email = props.get("email", "")
    job_title = props.get("jobtitle", "")
    company = props.get("company", "")

    # Build prompt
    prompt = f"""Based on the following contact information, deduce their role in the organization.

Contact Information:
- Name: {first_name} {last_name}
- Email: {email}
- Job Title: {job_title}
- Company: {company}

Available Role Categories:
{chr(10).join([f"- {role}" for role in ROLE_OPTIONS])}

Please respond in JSON format with:
{{
  "role": "<selected role from list>",
  "confidence": <0-100>,
  "reasoning": "<brief explanation>"
}}

Base confidence on how clear the role deduction is:
- >95%: Job title explicitly matches role (e.g., "Sales Director" → Sales)
- 75-95%: Job title implies role but less explicit (e.g., "Account Manager" → Sales)
- <75%: Job title is ambiguous (e.g., "Operations Manager" could be multiple roles)
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

        return result
    except Exception as e:
        print(f"Error calling Claude: {e}")
        return {
            "role": None,
            "confidence": 0,
            "reasoning": f"Error: {str(e)}"
        }

def update_hubspot_contact(contact_id, role, confidence):
    """Update contact with role_inferred_l1 property in HubSpot."""
    try:
        hubspot_client.crm.contacts.update(
            contact_id,
            properties={
                "role_inferred_l1": role,
                "role_inferred_l1_confidence": str(confidence)  # Store confidence as string
            }
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

    if action == "fetch":
        # Fetch contacts and analyze
        contacts = get_recent_contacts(limit=5)
        results = {
            "auto_approved": [],
            "review_queue": [],
            "errors": []
        }

        for contact in contacts:
            contact_id = contact.id
            first_name = contact.properties.get("firstname", "")
            last_name = contact.properties.get("lastname", "")
            job_title = contact.properties.get("jobtitle", "")

            # Deduce role
            deduction = deduce_role_with_claude(contact)
            confidence = deduction.get("confidence", 0)
            role = deduction.get("role")

            contact_info = {
                "id": contact_id,
                "name": f"{first_name} {last_name}",
                "job_title": job_title,
                "suggested_role": role,
                "confidence": confidence,
                "reasoning": deduction.get("reasoning", "")
            }

            # Route by confidence
            if confidence >= 95:
                # Auto-approve and save
                update_hubspot_contact(contact_id, role, confidence)
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
        role = data.get("role")
        confidence = data.get("confidence", 0)

        success = update_hubspot_contact(contact_id, role, confidence)
        return jsonify({"success": success})

    elif action == "skip":
        # Skip a contact (no update)
        return jsonify({"success": True})

    return jsonify({"error": "Invalid action"}), 400

@app.route("/api/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
