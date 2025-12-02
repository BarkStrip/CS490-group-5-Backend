from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from datetime import datetime

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize the APScheduler scheduler with Flask app context."""

    @scheduler.scheduled_job("interval", minutes=5)
    def scheduled_task():
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[SCHEDULER] {current_time} - Periodic task running")

    scheduler.start()
    print("[SCHEDULER] Scheduler started")

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
