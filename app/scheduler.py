# app/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerNotRunningError
import atexit
from datetime import datetime
import pytz
from app.extensions import db
from app.models import Appointment

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize the APScheduler scheduler with Flask app context."""
    import os

    # Don't start scheduler in Flask reloader parent process
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("[SCHEDULER] Skipping initialization in reloader parent process")
        return

    # Check if job already exists to prevent duplicates
    existing_jobs = scheduler.get_jobs()
    if existing_jobs:
        print(f"[SCHEDULER] Already has {len(existing_jobs)} job(s) registered, skipping duplicate init")
        return

    @scheduler.scheduled_job("interval", seconds=30)
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
                        f"[SCHEDULER] Found {count} expired appointment(s)"
                    )
                    for appointment in expired_appointments:
                        print(
                            f"[SCHEDULER]   - Apt #{appointment.id}: end_at={appointment.end_at} (current={current_time})"
                        )
                        appointment.status = "COMPLETED"

                    db.session.commit()
                    print(
                        f"[SCHEDULER] Auto-completed {count} appointment(s)"
                    )
                else:
                    print(
                        f"[SCHEDULER] No appointments to auto-complete"
                    )

        except Exception as e:
            print(
                f"[SCHEDULER] Error auto-completing appointments: {e}"
            )
            db.session.rollback()

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
