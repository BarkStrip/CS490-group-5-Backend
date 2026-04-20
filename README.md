# JADE — Salon Marketplace Backend API

A production-grade REST API powering a multi-vendor salon marketplace. Built with Flask and SQLAlchemy, JADE supports 13+ salons with full booking lifecycle management, role-based access control, geospatial search, transactional email notifications, and AWS S3 media storage.

---

## Features

### Authentication & Authorization
- JWT-based authentication with Bearer token scheme
- Role-based access control across 4 roles: OWNER, CUSTOMER, EMPLOYEE, ADMIN
- Password update flow with email verification
- Secure token handling and route-level permission enforcement

### Salon Discovery
- Search salons by city, category, and service type
- Geospatial search using latitude/longitude with distance calculation (miles)
- Verified salon filtering (`salon_verify.status = 'VERIFIED'`)
- Salon detail pages with average rating and review count

### Booking & Appointments
- Full appointment lifecycle: create, view, update, cancel
- Employee assignment and scheduling
- Price-at-booking capture to handle service price changes over time
- Appointment status tracking (Booked, Completed, Cancelled)
- Notes and special instructions support

### Notifications (Email via Resend)
- Appointment confirmation email on booking
- Reminder email 1 hour before appointment (cron-triggered)
- Cancellation notifications (role-aware: customer vs. employee flow)
- In-app messaging between customer and employee about an appointment
- Post-appointment review request email with unique token
- Bulk employee notification for salon hours changes

### Services & Products
- Service management per salon (pricing, duration, active status)
- Product catalog with inventory tracking (SKU, stock quantity)
- Shopping cart operations
- Image upload per service and product via AWS S3

### Reviews
- Customer reviews with star ratings and comments
- Photo attachments on reviews
- Review request flow triggered after appointment completion

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | Flask 3.x |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Database | MySQL |
| Authentication | JWT (Flask-JWT-Extended) |
| Email | Resend API |
| File Storage | AWS S3 (Boto3) |
| API Docs | Swagger UI (Flasgger) |
| Deployment | Railway + Gunicorn |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Client (Frontend)               │
└────────────────────────┬────────────────────────┘
                         │ REST API (JWT)
                         │
┌────────────────────────▼────────────────────────┐
│               Flask Application                  │
│                                                  │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Auth & RBAC  │  │     Route Blueprints      │ │
│  │  Middleware  │  │  /auth  /salons  /appts   │ │
│  └──────────────┘  │  /services  /products     │ │
│                    │  /cart  /reviews  /images  │ │
│                    │  /notifications            │ │
│                    └──────────────────────────┘ │
│                                                  │
│  ┌──────────────┐  ┌─────────────┐              │
│  │  SQLAlchemy  │  │   AWS S3    │              │
│  │     ORM      │  │   Boto3     │              │
│  └──────┬───────┘  └─────────────┘              │
└─────────┼───────────────────────────────────────┘
          │
┌─────────▼──────────┐     ┌──────────────────────┐
│    MySQL Database   │     │     Resend Email      │
│   30+ tables        │     │  Transactional API    │
│   Strategic indexes │     └──────────────────────┘
└─────────────────────┘
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and receive JWT |
| POST | `/api/auth/password` | Update password |

### Salons
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/salons` | Search salons (city, category, geo) |
| GET | `/api/salons/<id>` | Get salon details |
| GET | `/api/cities` | List cities with verified salons |
| GET | `/api/categories` | List service categories |

### Appointments
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/appointments` | Book appointment |
| GET | `/api/appointments/<id>` | Get appointment details |
| PATCH | `/api/appointments/<id>` | Update appointment |
| DELETE | `/api/appointments/<id>` | Cancel appointment |

### Notifications
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/notifications/appointment/confirmation` | Send booking confirmation email |
| POST | `/api/notifications/appointment/reminder` | Send reminder (cron-triggered) |
| POST | `/api/notifications/appointment/cancel` | Send cancellation notification |
| POST | `/api/notifications/appointment/message` | Send message between parties |
| POST | `/api/notifications/review-request` | Send post-appointment review email |
| POST | `/api/notifications/hours-change` | Bulk notify employees of hours change |
| POST | `/api/notifications/test` | Test email configuration |

### Services, Products, Cart, Reviews, Images
Full CRUD available for each resource group — see `/api/docs` (Swagger UI) for complete endpoint reference.

---

## Database Schema (Highlights)

30+ tables managed via SQLAlchemy ORM. Key design decisions:

- **Isolated workflows per salon** — each salon's data is scoped to prevent cross-tenant access
- **Strategic indexing** on geospatial columns (latitude, longitude) and foreign keys for performant location-based queries
- **Price capture at booking** — `price_at_book` on appointments ensures historical accuracy independent of service price changes
- **Soft deletes** via `is_active` flags on services and products rather than hard deletes

---

## Getting Started

### Prerequisites
- Python 3.11+
- MySQL Server
- AWS S3 bucket + credentials
- Resend API key

### Installation

```bash
git clone https://github.com/TheRickMJ03/jade-backend.git
cd jade-backend

python -m venv myenv
source myenv/bin/activate        # macOS/Linux
# or: myenv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
MYSQL_PUBLIC_URL=mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/salon_app

# Authentication
JWT_SECRET_KEY=your_secret_key

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_S3_BUCKET=your_bucket_name

# Email
RESEND_API_KEY=your_resend_key
```

### Run the Server

```bash
cd backend
python main.py
```

API available at `http://localhost:5000`
Swagger docs at `http://localhost:5000/api/docs`

---

## Testing

Unit tests cover core business logic including authentication flows, appointment conflict detection, and notification triggers.

```bash
pytest tests/
```

Test files are located in `/tests` — contributions to improve coverage are welcome.

---

## Deployment

Deployed on Railway with Gunicorn as the WSGI server:

```bash
gunicorn main:app --workers 4 --bind 0.0.0.0:$PORT
```
