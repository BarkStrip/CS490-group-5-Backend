from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Employees, Appointment, Service
from sqlalchemy import and_, extract
from datetime import datetime, timedelta
from decimal import Decimal

employee_payroll_bp = Blueprint("employee_payroll", __name__, url_prefix="/api/employee_payroll")

# Employee gets 70% of service price, salon gets 30%
EMPLOYEE_COMMISSION_RATE = Decimal("0.70")


def get_biweekly_period(target_date=None):
    """
    Calculate the current biweekly pay period.
    Returns (period_start, period_end) as datetime objects.
    
    Biweekly periods start on Sunday and end on Saturday (14 days).
    """
    if target_date is None:
        target_date = datetime.now().date()
    
    # Find the most recent Sunday
    days_since_sunday = target_date.weekday() + 1  # Monday = 0, so Sunday = 6
    if days_since_sunday == 7:  # If today is Sunday
        days_since_sunday = 0
    
    current_sunday = target_date - timedelta(days=days_since_sunday)
    
    # Determine if we're in the first or second week of the period
    # Use a reference date (e.g., Jan 1, 2024 was a Monday, so Jan 7, 2024 was the first Sunday)
    reference_sunday = datetime(2024, 1, 7).date()
    days_diff = (current_sunday - reference_sunday).days
    weeks_since_reference = days_diff // 7
    
    # If we're in an odd week number, go back one week to get period start
    if weeks_since_reference % 2 == 1:
        period_start = current_sunday - timedelta(days=7)
    else:
        period_start = current_sunday
    
    period_end = period_start + timedelta(days=13)  # 14 days total (0-13)
    
    return period_start, period_end


@employee_payroll_bp.route("/<int:employee_id>/current-period", methods=["GET"])
def get_current_period_payroll(employee_id):
    """
    GET /api/employee_payroll/<employee_id>/current-period
    Purpose: Calculate payroll information for the current biweekly pay period.
    
    Returns:
    - employee info
    - commission rate (70% of service prices)
    - hours worked (from COMPLETED appointments in current period)
    - projected paycheck amount (70% of total service revenue)
    - pay period dates (start and end)
    """
    
    # Check if employee exists
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    # Get current biweekly period
    period_start, period_end = get_biweekly_period()
    
    # Convert to datetime for querying (start of day and end of day)
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    
    # Query all COMPLETED appointments for this employee in the current period
    completed_appointments = db.session.query(Appointment).filter(
        and_(
            Appointment.employee_id == employee_id,
            # Appointment.status == "COMPLETED",
            Appointment.start_at >= period_start_dt,
            Appointment.end_at <= period_end_dt
        )
    ).all()
    
    # Calculate total hours worked and earnings
    total_hours = Decimal("0.00")
    total_service_revenue = Decimal("0.00")
    appointment_count = 0
    
    for apt in completed_appointments:
        if apt.start_at and apt.end_at:
            # Calculate hours
            duration = apt.end_at - apt.start_at
            hours = Decimal(str(duration.total_seconds() / 3600))
            total_hours += hours
            
            # Calculate revenue (use price_at_book if available, otherwise service price)
            if apt.price_at_book:
                price = Decimal(str(apt.price_at_book))
            else:
                price = Decimal("0")            
            total_service_revenue += price
            
            appointment_count += 1
    
    # Round to 2 decimal places
    total_hours = total_hours.quantize(Decimal("0.01"))
    total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))
    
    # Calculate employee earnings (70% of service revenue)
    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(Decimal("0.01"))
    salon_share = (total_service_revenue * (Decimal("1") - EMPLOYEE_COMMISSION_RATE)).quantize(Decimal("0.01"))
    
    result = {
        "employee_id": employee.id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
        "commission_percentage": "70%",
        "hours_worked": float(total_hours),
        "appointments_completed": appointment_count,
        "total_service_revenue": float(total_service_revenue),
        "employee_earnings": float(employee_earnings),
        "salon_share": float(salon_share),
        "projected_paycheck": float(employee_earnings),
        "pay_period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "period_label": f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}"
        }
    }
    
    return jsonify(result), 200


@employee_payroll_bp.route("/<int:employee_id>/history", methods=["GET"])
def get_payroll_history(employee_id):
    """
    GET /api/employee_payroll/<employee_id>/history
    Purpose: Get payroll history for the last 6 biweekly periods.
    
    Returns:
    - Array of past pay periods with hours and earnings (70% commission)
    """
    
    # Check if employee exists
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    history = []
    
    # Get last 6 biweekly periods (including current)
    for i in range(6):
        # Calculate the pay period (going backwards)
        target_date = datetime.now().date() - timedelta(weeks=i*2)
        period_start, period_end = get_biweekly_period(target_date)
        
        # Convert to datetime
        period_start_dt = datetime.combine(period_start, datetime.min.time())
        period_end_dt = datetime.combine(period_end, datetime.max.time())
        
        # Query completed appointments for this period
        completed_appointments = db.session.query(Appointment).filter(
            and_(
                Appointment.employee_id == employee_id,
                # Appointment.status == "COMPLETED",
                Appointment.start_at >= period_start_dt,
                Appointment.end_at <= period_end_dt
            )
        ).all()
        
        # Calculate hours and earnings
        total_hours = Decimal("0.00")
        total_service_revenue = Decimal("0.00")
        appointment_count = 0
        
        for apt in completed_appointments:
            if apt.start_at and apt.end_at:
                duration = apt.end_at - apt.start_at
                hours = Decimal(str(duration.total_seconds() / 3600))
                total_hours += hours
                
                # Use price_at_book or service price
                if apt.price_at_book:
                    price = Decimal(str(apt.price_at_book))
                else:
                    price = Decimal("0")   
                
                total_service_revenue += price
                
                appointment_count += 1
        
        total_hours = total_hours.quantize(Decimal("0.01"))
        total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))
        employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(Decimal("0.01"))
        
        history.append({
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_label": f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}",
            "hours_worked": float(total_hours),
            "appointments_completed": appointment_count,
            "total_service_revenue": float(total_service_revenue),
            "earnings": float(employee_earnings)
        })
    
    return jsonify({
        "employee_id": employee.id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
        "commission_percentage": "70%",
        "history": history
    }), 200


@employee_payroll_bp.route("/<int:employee_id>/monthly-total", methods=["GET"])
def get_monthly_total(employee_id):
    """
    GET /api/employee_payroll/<employee_id>/monthly-total
    Purpose: Get total earnings for the current month.
    
    Returns:
    - Monthly total earnings (70% commission)
    - Month start and end dates
    """
    
    # Check if employee exists
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    # Get current month boundaries
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    
    # Calculate next month's first day, then subtract 1 second to get end of current month
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1) - timedelta(seconds=1)
    else:
        month_end = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1)
    
    # Query all COMPLETED appointments for this month
    completed_appointments = db.session.query(Appointment).filter(
        and_(
            Appointment.employee_id == employee_id,
            # Appointment.status == "COMPLETED",
            Appointment.start_at >= month_start,
            Appointment.end_at <= month_end
        )
    ).all()
    
    # Calculate monthly totals
    total_hours = Decimal("0.00")
    total_service_revenue = Decimal("0.00")
    appointment_count = 0
    
    for apt in completed_appointments:
        if apt.start_at and apt.end_at:
            duration = apt.end_at - apt.start_at
            hours = Decimal(str(duration.total_seconds() / 3600))
            total_hours += hours
            
            if apt.price_at_book:
                price = Decimal(str(apt.price_at_book))
            else:
                price = Decimal("0")           
            total_service_revenue += price
            
            appointment_count += 1
    
    total_hours = total_hours.quantize(Decimal("0.01"))
    total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))
    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(Decimal("0.01"))
    salon_share = (total_service_revenue * (Decimal("1") - EMPLOYEE_COMMISSION_RATE)).quantize(Decimal("0.01"))
    
    return jsonify({
        "employee_id": employee.id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "month": now.strftime("%B %Y"),
        "month_start": month_start.date().isoformat(),
        "month_end": month_end.date().isoformat(),
        "hours_worked": float(total_hours),
        "appointments_completed": appointment_count,
        "total_service_revenue": float(total_service_revenue),
        "employee_earnings": float(employee_earnings),
        "salon_share": float(salon_share),
        "commission_percentage": "70%"
    }), 200