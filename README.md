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

### 2. Create and Configure `Config.py`

You need a configuration file to store the database connection string.

1.  **File Location:** Create a file named `config.py` in the root of your application, usually in the **`app/`** directory (e.g., `app/config.py`).

2.  **File Content:** Copy the following content into **`app/config.py`**.

    ```python
    import os

    class Config:
        """
        Contains the configuration variables for the Flask application.
        Reads from environment variables if available, otherwise uses a local fallback.
        """
     
        # Database Connection String (MySQL URI)
        # Prioritizes the environment variable 'DATABASE_URL' for deployment security.
        # FIX: The local fallback uses the 'pymysql' driver and generic credentials.
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>'
            
        # Recommended setting to disable SQLAlchemy event system for better performance.
        SQLALCHEMY_TRACK_MODIFICATIONS = False
    ```

3.  **Update Local Fallback:** **Replace** `<USER>`, `<PASSWORD>`, `<HOST>`, `<PORT>`, and `<DB_NAME>` in the `SQLALCHEMY_DATABASE_URI` line with your actual, personal database credentials (e.g., `'mysql+pymysql://root:mysecretpass@localhost:3306/salon_app'`).


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
