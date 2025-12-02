from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from datetime import datetime
from app.extensions import db
from app.models import Appointment

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize the APScheduler scheduler with Flask app context."""

    @scheduler.scheduled_job("interval", minutes=5)
    def scheduled_task():
        """Auto-complete appointments that have ended."""
        current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

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
                    # Update status to "COMPLETED"
                    for appointment in expired_appointments:
                        appointment.status = "COMPLETED"

                    db.session.commit()
                    count = len(expired_appointments)
                    print(
                        f"[SCHEDULER] {current_time_str} - Auto-completed {count} appointment(s)"
                    )
                else:
                    print(
                        f"[SCHEDULER] {current_time_str} - No appointments to auto-complete"
                    )

        except Exception as e:
            print(
                f"[SCHEDULER] {current_time_str} - Error auto-completing appointments: {e}"
            )
            db.session.rollback()

    if not scheduler.running:
        scheduler.start()
        print("[SCHEDULER] Scheduler started")
    else:
        print("[SCHEDULER] Scheduler already running (skipping duplicate start)")

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
