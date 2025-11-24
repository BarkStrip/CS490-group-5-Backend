# Customer-employee communication
from flask import Blueprint, request, jsonify
import resend
import os

messaging_bp = Blueprint("messaging", __name__)

@messaging_bp.route("/send-email", methods=["POST"])
def send_email_route():
    data = request.json

    try:
        email = resend.Emails.send({
            "from": "Your App <onboarding@resend.dev>",
            "to": data["to"],
            "subject": data["subject"],
            "html": data["html"]
        })

        return jsonify({"success": True, "data": email})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
