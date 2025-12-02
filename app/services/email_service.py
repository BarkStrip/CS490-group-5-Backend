# Platform-wide notifications
import os
import resend
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()


class EmailService:
    """
    Centralized email service using Resend
    """

    def __init__(self):
        """Initialize Resend with API key"""
        if os.getenv("TESTING") == "1":
            self.disabled = True
            self.api_key = None
            self.from_email = "test@example.com"
            self.frontend_url = "http://localhost:3000"
            print("⚠️ EmailService running in TEST MODE — no API key required")
            return
        self.api_key = os.getenv("RESEND_API_KEY")
        if not self.api_key:
            raise ValueError("RESEND_API_KEY environment variable is required")

        resend.api_key = self.api_key
        self.from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    def send_test_email(self, to_email: str) -> Dict:
        """
        Send a test email to verify Resend is working

        Args:
            to_email: Recipient email address

        Returns:
            Dict with 'success' boolean and 'message' or 'error'
        """
        try:
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": "Test Email from Salon App",
                "html": """
                    <html>
                        <body>
                            <h1>🎉 Success!</h1>
                            <p>PERFECT </p>
                            <p>HELL YEAHHHHHH </p>
                        </body>
                    </html>
                """,
            }

            email_response = resend.Emails.send(params)

            return {
                "success": True,
                "message": "Test email sent successfully",
                "email_id": email_response.get("id"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_appointment_confirmation(
        self,
        to_email,
        customer_name,
        salon_name,
        service_name,
        appointment_date,
        appointment_time,
        stylist_name,
        appointment_id,
        salon_address,
        salon_phone,
    ):
        """
        Send appointment confirmation email immediately after booking
        """
        try:
            html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #d4e3d4;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #d4e3d4; padding: 30px 20px;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #fafdfb; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 24px rgba(74, 95, 74, 0.15);">
                            <!-- Header with JADE Branding -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #6B8A6B 0%, #ffffff 100%); padding: 45px 40px; text-align: center;">
                                    <div style="background-color: rgba(255,255,255,0.2); display: inline-block; padding: 12px 35px; border-radius: 50px; margin-bottom: 18px; border: 2px solid rgba(255,255,255,0.3);">
                                        <h1 style="color: #4A5F4A; margin: 0; font-size: 36px; font-weight: 700; letter-spacing: 4px;">
                                            JADE
                                        </h1>
                                    </div>
                                    <h2 style="color: #4A5F4A; margin: 15px 0 0 0; font-size: 26px; font-weight: 600;">
                                        Appointment Confirmed
                                    </h2>
                                    <p style="color: #4A5F4A; margin: 10px 0 0 0; font-size: 16px;">
                                        Your booking is all set
                                    </p>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 45px 40px; background-color: #ffffff;">
                                    <p style="color: #2d3748; font-size: 17px; line-height: 1.6; margin: 0 0 10px 0;">
                                        Hi <strong style="color: #4A5F4A;">{customer_name}</strong>,
                                    </p>
                                    <p style="color: #4a5568; font-size: 16px; line-height: 1.7; margin: 0 0 35px 0;">
                                        Great news! Your appointment at <strong style="color: #4A5F4A;">{salon_name}</strong> has been confirmed. We're looking forward to seeing you!
                                    </p>

                                    <!-- Appointment Details Card -->
                                    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; border: 2px solid #8BA888; margin: 0 0 35px 0; box-shadow: 0 2px 8px rgba(139, 168, 136, 0.15);">
                                        <tr>
                                            <td style="padding: 30px 35px;">
                                                <h3 style="color: #4A5F4A; margin: 0 0 25px 0; font-size: 19px; font-weight: 700; border-bottom: 3px solid #8BA888; padding-bottom: 15px;">
                                                    Appointment Details
                                                </h3>
                                                <table width="100%" cellpadding="0" cellspacing="0">
                                                    <tr>
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; width: 140px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Date</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 16px; font-weight: 600;">
                                                            {appointment_date}
                                                        </td>
                                                    </tr>
                                                    <tr style="border-top: 1px solid #e8ede8;">
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Time</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 16px; font-weight: 600;">
                                                            {appointment_time}
                                                        </td>
                                                    </tr>
                                                    <tr style="border-top: 1px solid #e8ede8;">
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Service</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 16px; font-weight: 600;">
                                                            {service_name}
                                                        </td>
                                                    </tr>
                                                    <tr style="border-top: 1px solid #e8ede8;">
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Stylist</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 16px; font-weight: 600;">
                                                            {stylist_name}
                                                        </td>
                                                    </tr>
                                                    <tr style="border-top: 1px solid #e8ede8;">
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Location</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 15px; line-height: 1.5; font-weight: 500;">
                                                            {salon_address}
                                                        </td>
                                                    </tr>
                                                    <tr style="border-top: 1px solid #e8ede8;">
                                                        <td style="padding: 14px 0; color: #4a5568; font-size: 15px; vertical-align: middle;">
                                                            <strong style="color: #2d3748;">Phone</strong>
                                                        </td>
                                                        <td style="padding: 14px 0; color: #2d3748; font-size: 15px; font-weight: 500;">
                                                            {salon_phone}
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>

                                    <!-- Action Button -->
                                    <table width="100%" cellpadding="0" cellspacing="0">
                                        <tr>
                                            <td align="center" style="padding: 10px 0 35px 0;">
                                                <a href="{self.frontend_url}/appointments/{appointment_id}"
                                                   style="display: inline-block; padding: 18px 50px; background: linear-gradient(135deg, #6B8A6B 0%, #4A5F4A 100%); color: #4A5F4A; text-decoration: none; border-radius: 10px; font-weight: 700; font-size: 16px; box-shadow: 0 6px 16px rgba(74, 95, 74, 0.3); letter-spacing: 0.5px; border: 2px solid rgba(255,255,255,0.2);">
                                                    View Appointment Details
                                                </a>
                                            </td>
                                        </tr>
                                    </table>

                                    <!-- Info Box -->
                                    <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #f0f7f0 0%, #e8ede8 100%); border-radius: 10px; border-left: 5px solid #6B8A6B; margin: 20px 0 0 0; box-shadow: 0 2px 8px rgba(107, 138, 107, 0.1);">
                                        <tr>
                                            <td style="padding: 25px 28px;">
                                                <p style="color: #2d3748; font-size: 15px; line-height: 1.7; margin: 0;">
                                                    <strong style="color: #4A5F4A; font-size: 16px;">Important Reminders:</strong><br><br>
                                                    <span style="color: #4a5568;">
                                                    • Please arrive 10 minutes before your appointment<br>
                                                    • To reschedule or cancel, please notify us at least 24 hours in advance<br>
                                                    • Bring any reference photos or inspiration for your service
                                                    </span>
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background: linear-gradient(to bottom, #e8ede8 0%, #d4e3d4 100%); padding: 30px 40px; text-align: center; border-top: 2px solid #c4d3c4;">
                                    <p style="color: #4A5F4A; font-size: 15px; margin: 0 0 10px 0; font-weight: 700; letter-spacing: 2px;">
                                        JADE
                                    </p>
                                    <p style="color: #6B8A6B; font-size: 14px; margin: 0 0 5px 0; font-weight: 600;">
                                        {salon_name}
                                    </p>
                                    <p style="color: #718096; font-size: 13px; margin: 0; line-height: 1.6;">
                                        This is an automated confirmation email.<br>
                                        Please do not reply to this message.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": f"Appointment Confirmed at {salon_name}",
                "html": html_content,
            }

            email = resend.Emails.send(params)

            return {
                "success": True,
                "message": f"Confirmation email sent to {to_email}",
                "email_id": email.get("id"),
            }

        except Exception as e:
            print(f"Error sending confirmation email: {str(e)}")
            return {"success": False, "error": str(e)}

    def send_appointment_reminder(
        self,
        to_email: str,
        customer_name: str,
        salon_name: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        stylist_name: str,
        appointment_id: int,
        salon_address: str = "",
    ) -> Dict:
        """
        Send appointment reminder email

        Args:
            to_email: Customer email
            customer_name: Customer's name
            salon_name: Name of the salon
            service_name: Service being provided
            appointment_date: Date of appointment (formatted)
            appointment_time: Time of appointment (formatted)
            stylist_name: Name of stylist/employee
            appointment_id: ID of the appointment
            salon_address: Optional salon address

        Returns:
            Dict with 'success' boolean and 'message' or 'error'
        """
        try:
            subject = f" Reminder: Your appointment at {salon_name} in 1 hour"

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                        }}
                        .container {{
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background-color: #4CAF50;
                            color: white;
                            padding: 20px;
                            text-align: center;
                            border-radius: 5px 5px 0 0;
                        }}
                        .content {{
                            background-color: #f9f9f9;
                            padding: 30px;
                            border-radius: 0 0 5px 5px;
                        }}
                        .appointment-details {{
                            background-color: white;
                            padding: 20px;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .detail-row {{
                            margin: 10px 0;
                            padding: 10px 0;
                            border-bottom: 1px solid #eee;
                        }}
                        .detail-label {{
                            font-weight: bold;
                            color: #666;
                        }}
                        .button {{
                            display: inline-block;
                            background-color: #4CAF50;
                            color: white;
                            padding: 12px 30px;
                            text-decoration: none;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .footer {{
                            text-align: center;
                            margin-top: 20px;
                            color: #666;
                            font-size: 12px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1> Appointment Reminder</h1>
                        </div>
                        <div class="content">
                            <p>Hi <strong>{customer_name}</strong>,</p>
                            <p>This is a friendly reminder that your appointment is coming up in <strong>1 hour</strong>!</p>
                            
                            <div class="appointment-details">
                                <h2>Appointment Details</h2>
                                <div class="detail-row">
                                    <span class="detail-label">Salon:</span> {salon_name}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Service:</span> {service_name}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Date:</span> {appointment_date}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Time:</span> {appointment_time}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Stylist:</span> {stylist_name}
                                </div>
                                {f'<div class="detail-row"><span class="detail-label">Address:</span> {salon_address}</div>' if salon_address else ''}
                            </div>

                            <p>We look forward to seeing you!</p>

                            <center>
                                <a href="{self.frontend_url}/my-appointments" class="button">
                                    View Appointment Details
                                </a>
                            </center>

                            <p style="margin-top: 30px; font-size: 14px; color: #666;">
                                Need to cancel or reschedule? Please contact the salon as soon as possible.
                            </p>
                        </div>
                        <div class="footer">
                            <p>This is an automated reminder from your salon booking system.</p>
                        </div>
                    </div>
                </body>
            </html>
            """

            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            email_response = resend.Emails.send(params)

            return {
                "success": True,
                "message": "Appointment reminder sent successfully",
                "email_id": email_response.get("id"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_cancellation_notification(
        self,
        to_email: str,
        to_name: str,
        cancelled_by: str,  # 'customer' or 'employee'
        salon_name: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        salon_id: int,
        cancellation_reason: str = "",
    ) -> Dict:
        """
        Send cancellation notification

        Args:
            to_email: Recipient email
            to_name: Recipient name
            cancelled_by: Who cancelled ('customer' or 'employee')
            salon_name: Name of salon
            service_name: Service that was booked
            appointment_date: Date of cancelled appointment
            appointment_time: Time of cancelled appointment
            salon_id: ID of the salon
            cancellation_reason: Optional reason for cancellation

        Returns:
            Dict with 'success' boolean and 'message' or 'error'
        """
        try:
            if cancelled_by == "customer":
                subject = f"Appointment Cancelled - {salon_name}"
                main_message = "Your appointment has been cancelled."
                color = "#ff9800"
            else:
                subject = f"Appointment Cancellation Notice - {salon_name}"
                main_message = "We're sorry, but your appointment has been cancelled."
                color = "#ff1100"

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                        }}
                        .container {{
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background-color: {color};
                            color: white;
                            padding: 20px;
                            text-align: center;
                            border-radius: 5px 5px 0 0;
                        }}
                        .content {{
                            background-color: #f9f9f9;
                            padding: 30px;
                            border-radius: 0 0 5px 5px;
                        }}
                        .appointment-details {{
                            background-color: white;
                            padding: 20px;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .detail-row {{
                            margin: 10px 0;
                            padding: 10px 0;
                            border-bottom: 1px solid #eee;
                        }}
                        .detail-label {{
                            font-weight: bold;
                            color: #666;
                        }}
                        .button {{
                            display: inline-block;
                            background-color: #4CAF50;
                            color: white;
                            padding: 12px 30px;
                            text-decoration: none;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .reason-box {{
                            background-color: #fff3cd;
                            border-left: 4px solid {color};
                            padding: 15px;
                            margin: 20px 0;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1> Appointment Cancelled</h1>
                        </div>
                        <div class="content">
                            <p>Hi <strong>{to_name}</strong>,</p>
                            <p>{main_message}</p>
                            
                            <div class="appointment-details">
                                <h2>Cancelled Appointment Details</h2>
                                <div class="detail-row">
                                    <span class="detail-label">Salon:</span> {salon_name}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Service:</span> {service_name}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Date:</span> {appointment_date}
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Time:</span> {appointment_time}
                                </div>
                            </div>
                            
                            {f'<div class="reason-box"><strong>Reason:</strong> {cancellation_reason}</div>' if cancellation_reason else ''}

                            <p>If you have any questions, please contact the salon directly.</p>

                            <center>
                                <a href="{self.frontend_url}/salons/{salon_id}" class="button">
                                    Book Another Appointment
                                </a>
                            </center>
                        </div>
                    </div>
                </body>
            </html>
            """

            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            email_response = resend.Emails.send(params)

            return {
                "success": True,
                "message": "Cancellation notification sent successfully",
                "email_id": email_response.get("id"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_review_request(
        self,
        to_email: str,
        customer_name: str,
        salon_name: str,
        salon_id: int,
        service_name: str,
    ) -> dict:
        """
        Send a review request email directing user to the Landing Page
        """
        try:
            review_link = self.frontend_url.rstrip("/")

            subject = f"How was your visit to {salon_name}?"

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ text-align: center; padding: 20px 0; border-bottom: 2px solid #eee; }}
                        .stars {{ font-size: 24px; color: #FFD700; letter-spacing: 5px; margin: 10px 0; }}
                        .content {{ padding: 30px 0; text-align: center; }}
                        .button {{
                            display: inline-block;
                            background-color: #000;
                            color: #fff;
                            padding: 15px 35px;
                            text-decoration: none;
                            border-radius: 25px;
                            font-weight: bold;
                            margin-top: 20px;
                        }}
                        .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; }}
                        .instruction-box {{
                            background-color: #f8f9fa;
                            border: 1px solid #e9ecef;
                            padding: 15px;
                            margin: 20px 0;
                            border-radius: 8px;
                            text-align: left;
                            font-size: 14px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>{salon_name}</h2>
                        </div>
                        <div class="content">
                            <p>Hi {customer_name},</p>
                            <p>Thanks for visiting us for your <strong>{service_name}</strong>!</p>

                            <div class="stars">★★★★★</div>

                            <p>Please visit our website and leave a review:</p>

                            <div class="instruction-box">
                                <strong>How to leave a review:</strong>
                                <ol style="padding-left: 20px; margin: 10px 0;">
                                    <li>Click the button below to visit our website.</li>
                                    <li>Click on the <strong>{salon_name}</strong> icon on the landing page.</li>
                                    <li>Scroll down to the "Reviews" section.</li>
                                </ol>
                            </div>

                            <a href="{review_link}" class="button">Go to Website</a>

                        </div>
                        <div class="footer">
                            <p>If you didn't visit {salon_name} recently, please ignore this email.</p>
                        </div>
                    </div>
                </body>
            </html>
            """

            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            email_response = resend.Emails.send(params)

            return {
                "success": True,
                "message": "Review request sent successfully",
                "email_id": email_response.get("id"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_appointment_message(
        self,
        to_email: str,
        to_name: str,
        from_name: str,
        message_text: str,
        salon_name: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        appointment_id: int,
        mailto_link: str,
    ) -> dict:
        """
        Send a message regarding an appointment with a Reply button
        """
        try:
            subject = f"Message about your appointment at {salon_name}"

            html_content = f"""
                <html>
                    <head>
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                line-height: 1.6;
                                color: #333;
                            }}
                            .container {{
                                max-width: 600px;
                                margin: 0 auto;
                                padding: 20px;
                            }}
                            .header {{
                                background-color: #673AB7;
                                color: white;
                                padding: 20px;
                                text-align: center;
                                border-radius: 5px 5px 0 0;
                            }}
                            .content {{
                                background-color: #f9f9f9;
                                padding: 30px;
                                border-radius: 0 0 5px 5px;
                            }}
                            .message-box {{
                                background-color: white;
                                border-left: 4px solid #673AB7;
                                padding: 20px;
                                margin: 20px 0;
                                font-style: italic;
                            }}
                            .appointment-details {{
                                background-color: white;
                                padding: 20px;
                                border-radius: 5px;
                                margin: 20px 0;
                            }}
                            .detail-row {{
                                margin: 10px 0;
                                padding: 10px 0;
                                border-bottom: 1px solid #eee;
                            }}
                            .detail-label {{
                                font-weight: bold;
                                color: #666;
                            }}
                            .button {{
                                display: inline-block;
                                background-color: #673AB7;
                                color: white;
                                padding: 12px 30px;
                                text-decoration: none;
                                border-radius: 5px;
                                margin: 20px 0;
                                font-weight: bold;
                            }}
                            .sub-text {{
                                font-size: 12px;
                                color: #888;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <h1>💬 New Message</h1>
                            </div>
                            <div class="content">
                                <p>Hi <strong>{to_name}</strong>,</p>
                                <p><strong>{from_name}</strong> sent you a message regarding your appointment:</p>

                                <div class="message-box">
                                    "{message_text}"
                                </div>

                                <div class="appointment-details">
                                    <h3>Appointment Details</h3>
                                    <div class="detail-row">
                                        <span class="detail-label">Salon:</span> {salon_name}
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">Service:</span> {service_name}
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">Date:</span> {appointment_date}
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">Time:</span> {appointment_time}
                                    </div>
                                </div>

                                <center>
                                    <a href="{mailto_link}" class="button">
                                        Reply via Email
                                    </a>
                                    <p class="sub-text">
                                        Clicking reply will open your default email client to send a response directly to {from_name}.
                                    </p>
                                </center>
                            </div>
                        </div>
                    </body>
                </html>
                """

            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Ensure you have imported 'resend' at the top of your service file
            email_response = resend.Emails.send(params)

            return {
                "success": True,
                "message": "Message sent successfully",
                "email_id": email_response.get("id"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_hours_change_notification(
        self, to_emails: List[str], salon_name: str, new_hours: Dict[str, str]
    ) -> Dict:
        """
        Send notification about hours change to employees

        Args:
            to_emails: List of employee emails
            salon_name: Name of salon
            new_hours: Dictionary of day -> hours (e.g., {"Monday": "9AM-5PM"})

        Returns:
            Dict with 'success' boolean and 'message' or 'error'
        """
        try:
            subject = f"📅 Schedule Update - {salon_name}"

            hours_html = ""
            for day, hours in new_hours.items():
                hours_html += f"""
                <div class="detail-row">
                    <span class="detail-label">{day}:</span> {hours}
                </div>
                """

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                        }}
                        .container {{
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background-color: #FF5722;
                            color: white;
                            padding: 20px;
                            text-align: center;
                            border-radius: 5px 5px 0 0;
                        }}
                        .content {{
                            background-color: #f9f9f9;
                            padding: 30px;
                            border-radius: 0 0 5px 5px;
                        }}
                        .hours-box {{
                            background-color: white;
                            padding: 20px;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .detail-row {{
                            margin: 10px 0;
                            padding: 10px 0;
                            border-bottom: 1px solid #eee;
                        }}
                        .detail-label {{
                            font-weight: bold;
                            color: #666;
                            display: inline-block;
                            width: 120px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>📅 Schedule Update</h1>
                        </div>
                        <div class="content">
                            <p>Hello Team,</p>
                            <p>The salon hours for <strong>{salon_name}</strong> have been updated:</p>

                            <div class="hours-box">
                                <h3>New Schedule</h3>
                                {hours_html}
                            </div>

                            <p>Please adjust your availability accordingly and ensure you're aware of these changes.</p>

                            <p>If you have any questions or concerns about the new schedule, please contact the salon owner.</p>

                            <p>Thank you,<br><strong>{salon_name} Management</strong></p>
                        </div>
                    </div>
                </body>
            </html>
            """

            # Send to all employees
            success_count = 0
            for email in to_emails:
                try:
                    params = {
                        "from": self.from_email,
                        "to": [email],
                        "subject": subject,
                        "html": html_content,
                    }
                    resend.Emails.send(params)
                    success_count += 1
                except Exception as e:
                    print(f"Failed to send to {email}: {e}")

            return {
                "success": success_count > 0,
                "message": f"Sent to {success_count}/{len(to_emails)} employees",
                "success_count": success_count,
                "total_count": len(to_emails),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# Create a singleton instance
email_service = EmailService()
