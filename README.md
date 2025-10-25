# Salon Backend API

This is the backend repository for the Salon application, built using **Flask** and **SQLAlchemy** with a **MySQL** database.

## Prerequisites

Before starting, ensure you have the following installed:

* **Python 3.x**
* **MySQL Server** (running locally or accessible via network)
* **A Virtual Environment** (recommended, e.g., `myenv`)

---
> ⚠️ **Important:**  
> Make sure you run the new `.sql` file — which includes **new columns** and **updated data** — **before starting the backend server**.  
>
> 📂 [Download the SQL file here](https://drive.google.com/file/d/1Up1kC2FIogDFia8xwv9LOFLWqg4mzEQO/view?usp=drive_link)

## Setup Instructions

### 1. Environment Setup

1.  **Activate your Virtual Environment:**
    ```bash
    .\myenv\Scripts\activate
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    # (Example dependencies: Flask Flask-SQLAlchemy PyMySQL sqlacodegen)
    ```
### 2. Create and Configure Environment Variables

You need to set up environment variables to store your database connection string securely.

1.  **Create `.env` File:** Create a file named `.env` in the root of your application directory (same level as your main application file).

2.  **Add Database Configuration:** Copy one of the following configurations into your `.env` file:

   **For Local Database:**
```env
    # Local DB Credentials:
    MYSQL_PUBLIC_URL=mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/salon_app
```
   **For Railway Development Database:**
```env
    # Railway Development DB:
    MYSQL_PUBLIC_URL=mysql://root:<MYSQL_ROOT_PASSWORD>@mysql.railway.internal:3306/salon_app_dev
```

3.  **Update Your Credentials:** Replace the placeholder values with your actual database information:
    - `<USER>`: Your database username
    - `<PASSWORD>`: Your database password  
    - `<HOST>`: Your database host (typically `localhost` for local)
    - `<PORT>`: Your database port (typically `3306` for MySQL)
    - `<MYSQL_ROOT_PASSWORD>`: Your Railway MySQL root password (for Railway option)


4.  **Security Note:** Add `.env` to your `.gitignore` file to prevent committing sensitive credentials to version control:
```gitignore
    .env
```


### 3. Database Model Generation (`app/models.py`)

The Python models for your database tables are auto-generated from the live MySQL schema.

* **No need to run this command if models.py is up-to-date.**
* **Run this command** if a database schema change occurs or if your `app/models.py` file becomes corrupted (e.g., due to the null byte error you previously resolved).

To re-generate the models using the declarative base:


# Replace the connection string with your full, personal database URL
sqlacodegen_v2 --generator declarative "mysql+pymysql://<user>:<password>@<host>:<port>/<db_name>" > app/models.py



### 4. Run the Flask Application

Run the main application file:
python main.py


### Available Endpoints
The backend currently exposes two meta-data endpoints for populating the frontend user interface.


## Available Endpoints

The backend currently exposes two meta-data endpoints for populating the frontend user interface.

| Route | Method | Description | Example Output |
| :--- | :--- | :--- | :--- |
| `/api/cities` | `GET` | Fetches a unique list of **cities** that contain a salon that has been verified (`salon_verify.status = 'VERIFIED'`). | `["Newark", "Jersey City"]` |
| `/api/categories` | `GET` | Fetches a distinct list of all service **categories** (service names) and their associated `icon_url` (if the column exists). | `[{"name": "Braids", "icon_url": "..."}]` |
