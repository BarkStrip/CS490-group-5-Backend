# tests/seed_playwright_data.py

from datetime import date, time

import bcrypt

from app.extensions import db
from app.models import (
    AuthUser,
    Customers,
    SalonOwners,
    Salon,
    SalonHours,
    SalonVerify,
    Service,
    LoyaltyProgram,
    Employees,
)

PASSWORD_PLAINTEXT = "password123"


def make_password_hash(plain: str) -> bytes:
    """Use the same bcrypt logic as your update_password route."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def seed_playwright_users() -> None:
    """
    Seed fixed test data for Playwright into the *current* DB.

    IMPORTANT: Call this ONLY inside an app.app_context().
    """
    print("🔄 Seeding Playwright test data into TEST DB...")

    # 1) CUSTOMER account
    cust_user = AuthUser.query.filter_by(email="playwright_tester@jade.com").first()
    if not cust_user:
        cust_user = AuthUser(
            email="playwright_tester@jade.com",
            password_hash=make_password_hash(PASSWORD_PLAINTEXT),
            role="CUSTOMER",
        )
        db.session.add(cust_user)
        db.session.flush()
        print(f"  ✅ Created CUSTOMER auth_user id={cust_user.id}")
    else:
        print(f"  ℹ CUSTOMER auth_user already exists (id={cust_user.id})")

    customer_profile = Customers.query.filter_by(user_id=cust_user.id).first()
    if not customer_profile:
        customer_profile = Customers(
            user_id=cust_user.id,
            first_name="Playwright",
            last_name="Tester",
            phone_number="6091231234",
            address="12 Main Ave",
            gender="Other",
            date_of_birth=date(2000, 1, 1),
            age=25,
        )
        db.session.add(customer_profile)
        db.session.flush()
        print(f"  ✅ Created Customers profile id={customer_profile.id}")
    else:
        print(f"  ℹ Customers profile already exists (id={customer_profile.id})")

    # 2) SALON OWNER account
    owner_user = AuthUser.query.filter_by(
        email="playwright_tester_owner@jade.com"
    ).first()
    if not owner_user:
        owner_user = AuthUser(
            email="playwright_tester_owner@jade.com",
            password_hash=make_password_hash(PASSWORD_PLAINTEXT),
            role="OWNER",
        )
        db.session.add(owner_user)
        db.session.flush()
        print(f"  ✅ Created OWNER auth_user id={owner_user.id}")
    else:
        print(f"  ℹ OWNER auth_user already exists (id={owner_user.id})")

    owner_profile = SalonOwners.query.filter_by(user_id=owner_user.id).first()
    if not owner_profile:
        owner_profile = SalonOwners(
            user_id=owner_user.id,
            first_name="Playwright",
            last_name="TesterOwner",
            phone_number="1231231234",
            address="Owner Address",
        )
        db.session.add(owner_profile)
        db.session.flush()
        print(f"  ✅ Created SalonOwners profile id={owner_profile.id}")
    else:
        print(f"  ℹ SalonOwners profile already exists (id={owner_profile.id})")

    # 3) SALON linked to that owner
    salon = Salon.query.filter_by(name="PlaywrightTest").first()
    if not salon:
        salon = Salon(
            salon_owner_id=owner_profile.id,
            name="PlaywrightTest",
            latitude=40.735657,
            longitude=-74.172363,
            address="12 Main Street, Newark, NJ 07120",
            city="Newark",
            phone="2324741234",
            about="Playwright test salon for automated E2E tests.",
        )
        db.session.add(salon)
        db.session.flush()
        print(f"  ✅ Created Salon '{salon.name}' (id={salon.id})")
    else:
        print(f"  ℹ Salon '{salon.name}' already exists (id={salon.id})")

    # 3a) SALON HOURS 0–6, 09:00–17:00
    for weekday in range(7):
        hours = SalonHours.query.filter_by(salon_id=salon.id, weekday=weekday).first()
        if not hours:
            hours = SalonHours(
                salon_id=salon.id,
                weekday=weekday,
                is_open=1,
                open_time=time(9, 0, 0),
                close_time=time(17, 0, 0),
            )
            db.session.add(hours)
            print(f"  ✅ Created SalonHours weekday={weekday} 09:00–17:00")
        else:
            print(f"  ℹ SalonHours already exists for weekday={weekday}")

    # 3b) SALON VERIFY row: APPROVED
    verify = SalonVerify.query.filter_by(salon_id=salon.id).first()
    if not verify:
        verify = SalonVerify(
            salon_id=salon.id,
            status="APPROVED",
            admin_id=None,
        )
        db.session.add(verify)
        print("  ✅ Created SalonVerify with status=APPROVED")
    else:
        if verify.status != "APPROVED":
            verify.status = "APPROVED"
            print("  🔁 Updated existing SalonVerify to APPROVED")

    # 3c) SERVICE: Haircut
    service = Service.query.filter_by(salon_id=salon.id, name="Haircut").first()
    if not service:
        service = Service(
            salon_id=salon.id,
            name="Haircut",
            price=50.00,
            duration=30,
            is_active=1,
        )
        db.session.add(service)
        print("  ✅ Created Service 'Haircut'")
    else:
        print("  ℹ Service 'Haircut' already exists")

    # 3d) LOYALTY PROGRAM for the salon
    lp = LoyaltyProgram.query.filter_by(salon_id=salon.id).first()
    if not lp:
        lp = LoyaltyProgram(
            salon_id=salon.id,
            active=0,
            program_type="POINTS",
            visits_for_reward=None,
            reward_type=None,
        )
        db.session.add(lp)
        print("  ✅ Created LoyaltyProgram (inactive, POINTS)")
    else:
        print("  ℹ LoyaltyProgram already exists for this salon")

    # 4) EMPLOYEE account linked to this salon
    emp_user = AuthUser.query.filter_by(email="playwright_tester_emp@jade.com").first()
    if not emp_user:
        emp_user = AuthUser(
            email="playwright_tester_emp@jade.com",
            password_hash=make_password_hash(PASSWORD_PLAINTEXT),
            role="EMPLOYEE",
        )
        db.session.add(emp_user)
        db.session.flush()
        print(f"  ✅ Created EMPLOYEE auth_user id={emp_user.id}")
    else:
        print(f"  ℹ EMPLOYEE auth_user already exists (id={emp_user.id})")

    employee_profile = Employees.query.filter_by(user_id=emp_user.id).first()
    if not employee_profile:
        employee_profile = Employees(
            user_id=emp_user.id,
            salon_id=salon.id,
            first_name="Playwright",
            last_name="TesterEmp",
            phone_number="0000000000",
            address="34 Willow Ave, Jersey City, NJ 21412",
            employment_status="APPROVED",
            employee_type=None,
        )
        db.session.add(employee_profile)
        db.session.flush()
        print(f"  ✅ Created Employees profile id={employee_profile.id}")
    else:
        print(f"  ℹ Employees profile already exists (id={employee_profile.id})")

    db.session.commit()
    print("✅ Finished seeding Playwright test data.")
