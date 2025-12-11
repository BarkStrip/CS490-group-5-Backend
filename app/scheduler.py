# app/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerNotRunningError
import atexit
from datetime import datetime, timedelta
import pytz
from app.extensions import db
from app.models import Appointment, Customers, AuthUser, Salon, Service, Employees
from app.services.email_service import email_service

# Configurable scheduler interval (in seconds)
SCHEDULER_INTERVAL_SECONDS = 30

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize the APScheduler scheduler with Flask app context."""
    import os

    # Don't start scheduler in Flask reloader parent process
    if os.environ.get("FLASK_ENV") == "development" and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("[SCHEDULER] Skipping initialization in reloader parent process")
        return

    # Check if job already exists to prevent duplicates
    existing_jobs = scheduler.get_jobs()
    if existing_jobs:
        print(f"[SCHEDULER] Already has {len(existing_jobs)} job(s) registered, skipping duplicate init")
        return

    @scheduler.scheduled_job("interval", seconds=SCHEDULER_INTERVAL_SECONDS)
    def scheduled_task():
        """Auto-complete appointments that have ended."""
        # Use Eastern Time to match how appointments are stored
        eastern = pytz.timezone('America/New_York')
        current_time = datetime.now(eastern)
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        try:
            with app.app_context():
                # Query appointments with status "BOOKED" or "Booked" where end_at is in the past
                expired_appointments = (
                    db.session.query(Appointment)
                    .filter(
                        Appointment.status.in_(["BOOKED", "Booked"]),
                        Appointment.end_at < current_time,
                    )
                    .all()
                )

                if expired_appointments:
                    count = len(expired_appointments)
                    print(
                        f"[SCHEDULER] Found {count} expired appointment(s):", flush=True
                    )

                    for appointment in expired_appointments:
                        print(
                            f"[SCHEDULER]   - Apt #{appointment.id}: end_at={appointment.end_at} (current={current_time})", flush=True
                        )
                        appointment.status = "COMPLETED"

                    db.session.commit()
                    print(
                        f"[SCHEDULER] Auto-completed {count} appointment(s)", flush=True
                    )
                else:
                    print(
                        f"[SCHEDULER] No appointments to auto-complete", flush=True
                    )

        except Exception as e:
            print(
                f"[SCHEDULER] Error auto-completing appointments: {e}"
            )
            db.session.rollback()

    @scheduler.scheduled_job("interval", seconds=SCHEDULER_INTERVAL_SECONDS)
    def send_appointment_reminders():
        """Send reminder emails for appointments starting in 1 hour."""
        # Use Eastern Time to match how appointments are stored
        eastern = pytz.timezone('America/New_York')
        current_time = datetime.now(eastern)

        # Calculate time window: 1 hour to 1 hour + scheduler interval
        # This ensures we catch all appointments exactly 1 hour ahead without duplicates
        reminder_start = current_time + timedelta(hours=1)
        reminder_end = current_time + timedelta(hours=1, seconds=SCHEDULER_INTERVAL_SECONDS)

        try:
            with app.app_context():
                # Query appointments in the reminder time window with BOOKED status
                appointments_to_remind = (
                    db.session.query(Appointment)
                    .filter(
                        Appointment.status.in_(["BOOKED", "Booked"]),
                        Appointment.start_at >= reminder_start,
                        Appointment.start_at <= reminder_end,
                    )
                    .all()
                )

                if appointments_to_remind:
                    count = len(appointments_to_remind)
                    print(
                        f"[SCHEDULER] Found {count} appointment(s) needing reminders (window: {reminder_start.strftime('%H:%M:%S')} - {reminder_end.strftime('%H:%M:%S')})",
                        flush=True
                    )

                    for appointment in appointments_to_remind:
                        try:
                            # Validate required relationships exist
                            if not appointment.customer:
                                print(f"[SCHEDULER] Skipping appointment #{appointment.id}: no customer", flush=True)
                                continue

                            if not appointment.customer.user:
                                print(f"[SCHEDULER] Skipping appointment #{appointment.id}: customer has no user account", flush=True)
                                continue

                            if not appointment.salon:
                                print(f"[SCHEDULER] Skipping appointment #{appointment.id}: no salon", flush=True)
                                continue

                            if not appointment.service:
                                print(f"[SCHEDULER] Skipping appointment #{appointment.id}: no service", flush=True)
                                continue

                            if not appointment.employee:
                                print(f"[SCHEDULER] Skipping appointment #{appointment.id}: no employee", flush=True)
                                continue

                            # Gather appointment details
                            customer_email = appointment.customer.user.email
                            customer_name = f"{appointment.customer.first_name} {appointment.customer.last_name}"
                            salon_name = appointment.salon.name
                            service_name = appointment.service.name
                            employee_name = f"{appointment.employee.first_name} {appointment.employee.last_name}"
                            salon_address = appointment.salon.address or ""

                            # Format date and time
                            formatted_date = appointment.start_at.strftime("%B %d, %Y")
                            formatted_time = appointment.start_at.strftime("%I:%M %p")

                            # Send reminder email
                            result = email_service.send_appointment_reminder(
                                to_email=customer_email,
                                customer_name=customer_name,
                                salon_name=salon_name,
                                service_name=service_name,
                                appointment_date=formatted_date,
                                appointment_time=formatted_time,
                                stylist_name=employee_name,
                                appointment_id=appointment.id,
                                salon_address=salon_address,
                            )

                            if result.get("success"):
                                print(
                                    f"[SCHEDULER]   ✓ Sent reminder for appointment #{appointment.id} to {customer_email}",
                                    flush=True
                                )
                            else:
                                error = result.get("error", "Unknown error")
                                print(
                                    f"[SCHEDULER]   ✗ Failed to send reminder for appointment #{appointment.id}: {error}",
                                    flush=True
                                )

                        except Exception as email_error:
                            print(
                                f"[SCHEDULER]   ✗ Error sending reminder for appointment #{appointment.id}: {email_error}",
                                flush=True
                            )
                            # Continue processing other appointments
                            continue

                    print(
                        f"[SCHEDULER] Finished processing {count} reminder(s)",
                        flush=True
                    )
                else:
                    print(
                        f"[SCHEDULER] No appointment reminders to send",
                        flush=True
                    )

        except Exception as e:
            print(
                f"[SCHEDULER] Error processing appointment reminders: {e}",
                flush=True
            )
            # Don't rollback - this is a read-only operation

    if not scheduler.running:
        scheduler.start()
        print("[SCHEDULER] Scheduler started")
    else:
        print("[SCHEDULER] Scheduler already running (skipping duplicate start)")

    def safe_shutdown():
        try:
            scheduler.shutdown(wait=False)
        except SchedulerNotRunningError:
            pass

    atexit.register(safe_shutdown)
