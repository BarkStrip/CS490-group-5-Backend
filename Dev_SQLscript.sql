/* -----------------------------------------------------------------------------
   Salon App — schema + seed

   What we have here
   • We started clean by dropping and recreating the database.
   • We created every table we need with created_at and updated_at columns.
   • We kept sign-in stuff separate from customer/salon data.
   • We sticked to simple, clean 3NF so tables stay tidy and easy to query.
   • We added a small audit log so we can see inserts/updates/deletes on key tables.
   • We loaded all the mock data generated from Makaro.

   • If we need more rules later, we will add CHECKs/ENUMs or extend triggers.
   • There is clear separation betweengit branch 
 auth and PII to keep things safer and simpler.
----------------------------------------------------------------------------- */

/* We have a clean reset: drop the database if it exists, then create it again so we can run this script anytime without leftovers. */
DROP DATABASE IF EXISTS salon_app;
CREATE DATABASE salon_app CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE salon_app;

/* We have our core identity tables here. These define people and let other tables point to them. */
/* We have a users table. Salons use owner_id to reference this table.
   We include created_at and updated_at so we can see when each row was made or changed. */

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

/* We kept real people info (name, email, phone, role) in customers—separate from auth—so PII stays clean, unique, timestamped, and easy for other tables to reference via customers.id. */
CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50),
  email VARCHAR(50),
  phone VARCHAR(50),
  role VARCHAR(8),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

/* We kept admin names, emails, status, and role here as a business table—separate from login/auth—so other tables can reference admins by _id without mixing PII with credentials. */
CREATE TABLE admins (
  _id INT PRIMARY KEY,
  first_name VARCHAR(50),
  last_name VARCHAR(50),
  email VARCHAR(50),
  status VARCHAR(8),
  role VARCHAR(5),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

/* Authentication - Auth rows link an email to a role and password hash. Application code owns passwords. */
CREATE TABLE auth_user (
  id INT PRIMARY KEY,                       -- use same id values where desired
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARBINARY(72) NULL,         -- placeholder; app sets this
  role ENUM('OWNER','ADMIN','CUSTOMER','EMPLOYEE') NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

/* Payment placeholder - Invoice needs a payment FK. We kept a minimal stub and can extend later. */
CREATE TABLE payment (
  id INT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

/* Domain tables - Core domain (salons, people-facing data) */
CREATE TABLE salon (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  owner_id     INT NOT NULL,              
  name         VARCHAR(120) NOT NULL,
  type         VARCHAR(40),                
  address      VARCHAR(255),
  city         VARCHAR(100),
  latitude     DECIMAL(9, 6) NOT NULL,
  longitude    DECIMAL(9, 6) NOT NULL,
  phone        VARCHAR(25),
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_salon_owner FOREIGN KEY (owner_id) REFERENCES users(id),
  INDEX idx_city (city),                     -- For fast searching by city name
  INDEX idx_coords (latitude, longitude)
);

/* One cart per customer. We enforce that with UNIQUE on user_id and cascade on delete. */
CREATE TABLE cart (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_cart_user (user_id),
  CONSTRAINT fk_cart_user FOREIGN KEY (user_id) REFERENCES customers(id) ON DELETE CASCADE
);

/* Table for Profile photos for customers */
CREATE TABLE user_image (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  customers_id    INT NOT NULL,
  url        VARCHAR(2000) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_ui_user FOREIGN KEY (customers_id) REFERENCES customers(id) ON DELETE CASCADE
);
/* We have Lightweight notifications log (email / SMS / in-app), one row per send. */
CREATE TABLE notify (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  customers_id    INT NOT NULL,
  channel    ENUM('EMAIL','SMS','INAPP') NOT NULL,
  title      VARCHAR(160),
  body       VARCHAR(1000),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(customers_id, created_at),
  CONSTRAINT fk_nf_user FOREIGN KEY (customers_id) REFERENCES customers(id) ON DELETE CASCADE
);

/* Saved payment methods tied to a customer; we accept true/false strings in is_default to match the provided data. */
CREATE TABLE pay_method (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  brand VARCHAR(50),
  last4 INT,
  is_default VARCHAR(50),  /* keep varchar to accept both TRUE/FALSE and 'true' as in your data */
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(user_id, is_default),
  CONSTRAINT fk_pm_user FOREIGN KEY (user_id) REFERENCES customers(id) ON DELETE CASCADE
);

/* Invoices carry math fields and link back to payment. */
CREATE TABLE invoice (
  id INT AUTO_INCREMENT PRIMARY KEY,
  payment_id INT,
  subtotal DECIMAL(5,2),
  tax_rate DECIMAL(6,3),
  tax_amount DECIMAL(23,2),
  total DECIMAL(23,2),
  emailed_to VARCHAR(255),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_inv_pay FOREIGN KEY (payment_id) REFERENCES payment(id) ON DELETE CASCADE
);

/* Salon staff. We keep employment status and role simple so seed data fits. */
CREATE TABLE employees (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  first_name VARCHAR(50),
  last_name VARCHAR(50),
  email VARCHAR(50),
  employment_status VARCHAR(6),
  role VARCHAR(12),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_emp_salon FOREIGN KEY (salon_id) REFERENCES salon(id)  ON DELETE CASCADE
);

/* Retail products sold by a salon. Price is money, stock is integer, is_active is a tinyint for simple on/off. */
CREATE TABLE product (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  salon_id    INT NOT NULL,
  name        VARCHAR(120) NOT NULL,
  description VARCHAR(400),
  price       DECIMAL(10,2) NOT NULL,
  sku         VARCHAR(64),
  stock_qty   INT NOT NULL DEFAULT 0,
  is_active   TINYINT(1) NOT NULL DEFAULT 1,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(salon_id, is_active),
  CONSTRAINT fk_prod_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* Salon gallery photos. */
CREATE TABLE salon_image (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  salon_id   INT NOT NULL,
  url        VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_si_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* Opening hours per weekday. We keep weekday NULL-able because the seed omits it; UNIQUE keeps one row per (salon, day). */
CREATE TABLE salon_hours (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  weekday INT NULL,
  hours VARCHAR(8),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_salon_day (salon_id, weekday),
  CONSTRAINT fk_sh_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* Admin verification status for a salon. Separate table keeps history clean if we want multiple rows over time. */
CREATE TABLE salon_verify (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  admin_id INT,
  status VARCHAR(9),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(salon_id),
  CONSTRAINT fk_sv_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE,
  CONSTRAINT fk_sv_admin FOREIGN KEY (admin_id) REFERENCES admins(_id)
);

/* Bookable services offered by a salon. Duration in minutes, basic active flag matches the seed. */
CREATE TABLE service (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  name VARCHAR(50),
  price INT,
  duration INT,
  is_active VARCHAR(50),
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_serv_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* Policies (cancellation and no-show) stored per salon. Each row is a simple rule we can read at booking time. */
CREATE TABLE cancel_policy (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  cutoff_hours INT,
  fee INT,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cp_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

CREATE TABLE noshow_policy (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  grace_min INT,
  fee DECIMAL(4,2),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_np_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* loyalty rules per salon */
CREATE TABLE loyalty_program (
  id INT AUTO_INCREMENT PRIMARY KEY,
  salon_id INT,
  active VARCHAR(50),
  visits_for_reward INT,
  reward_type VARCHAR(12),
  reward_value DECIMAL(5,2),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_lp_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/* Orders & reviews */
CREATE TABLE _order (
  id INT PRIMARY KEY,
  customer_id INT,
  salon_id INT,
  status VARCHAR(9),
  subtotal DECIMAL(5,2),
  tip_amnt INT,
  tax_amnt INT,
  total_amnt INT,
  promo_id VARCHAR(50),
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submitted_at  DATETIME NULL,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(customer_id, created_at),
  INDEX(salon_id, created_at),
  CONSTRAINT fk_ord_user  FOREIGN KEY (customer_id)  REFERENCES customers(id),
  CONSTRAINT fk_ord_salon FOREIGN KEY (salon_id) REFERENCES salon(id)
);

/* Customer reviews for salons; replies are separate so we can thread responses. */
CREATE TABLE review (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  salon_id   INT NOT NULL,
  customers_id    INT NOT NULL,
  rating     TINYINT NOT NULL,
  comment    VARCHAR(500),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(salon_id, created_at),
  CONSTRAINT fk_rv_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE,
  CONSTRAINT fk_rv_user  FOREIGN KEY (customers_id)  REFERENCES customers(id) ON DELETE CASCADE
);

/* Loyalty balance per (customer, salon). Unique key avoids duplicates. */
CREATE TABLE loyalty_account (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  salon_id INT,
  points INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_la (user_id, salon_id),
  CONSTRAINT fk_la_user  FOREIGN KEY (user_id)  REFERENCES customers(id)  ON DELETE CASCADE,
  CONSTRAINT fk_la_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE
);

/*
Messaging & scheduling
// Simple customer → employee messages with a timestamp index for inbox speed. */

CREATE TABLE message (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  sender_id   INT NOT NULL,
  employees_id INT NOT NULL,
  body        VARCHAR(200) NOT NULL,
  sent_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(employees_id, sent_at),
  CONSTRAINT fk_msg_sender   FOREIGN KEY (sender_id)   REFERENCES customers(id) ON DELETE CASCADE,
  CONSTRAINT fk_msg_receiver FOREIGN KEY (employees_id) REFERENCES employees(id) ON DELETE CASCADE
);


/* Staff availability and temporary time blocks; we keep strings in seed format so data loads as given. */
CREATE TABLE emp_avail (
  id INT AUTO_INCREMENT PRIMARY KEY,
  employee_id INT,
  weekday INT,
  start_time VARCHAR(50),
  end_time VARCHAR(50),
  effective_from VARCHAR(10),
  effective_to VARCHAR(10),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_avail (employee_id, weekday, effective_from),
  CONSTRAINT fk_av_emp FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE time_block (
  id INT PRIMARY KEY,
  salon_id INT,
  employee_id INT,
  start_at VARCHAR(10),
  end_at VARCHAR(10),
  reason TEXT,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(salon_id, start_at),
  INDEX(employee_id, start_at),
  CONSTRAINT fk_tb_salon FOREIGN KEY (salon_id) REFERENCES salon(id) ON DELETE CASCADE,
  CONSTRAINT fk_tb_emp FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

/* Appointments link a salon, customer, staff, and service with a price snapshot. */
CREATE TABLE appointment (
  id INT PRIMARY KEY,
  salon_id INT,
  customer_id INT,
  employee_id INT,
  service_id INT,
  start_at VARCHAR(20),
  end_at VARCHAR(20),
  status VARCHAR(9),
  price_at_book DECIMAL(5,2),
  notes TEXT,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(salon_id, start_at),
  INDEX(employee_id, start_at),
  INDEX(customer_id, start_at),
  CONSTRAINT fk_ap_salon    FOREIGN KEY (salon_id)    REFERENCES salon(id),
  CONSTRAINT fk_ap_customer FOREIGN KEY (customer_id) REFERENCES customers(id),
  CONSTRAINT fk_ap_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
);


/* 
Cart & order items
/ Cart items can be services or products. We keep soft FKs that allow NULL if an item type doesn’t apply. */
CREATE TABLE cart_item (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cart_id INT,
  kind VARCHAR(7),
  service_id INT,
  product_id INT,
  qty INT,
  price DECIMAL(5,2),
  added_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(cart_id),
  CONSTRAINT fk_ci_cart FOREIGN KEY (cart_id) REFERENCES cart(id) ON DELETE CASCADE,
  CONSTRAINT fk_ci_prod FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE SET NULL
);

/* Reply thread for reviews; separate table so we can support multiple replies later. */
CREATE TABLE review_reply (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  review_id  INT NOT NULL,
  replier_id INT NOT NULL,                 -- customers.id
  text_body  VARCHAR(500) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_rr_review FOREIGN KEY (review_id)  REFERENCES review(id) ON DELETE CASCADE,
  CONSTRAINT fk_rr_user   FOREIGN KEY (replier_id) REFERENCES customers(id)
);

/* Tokens invite customers to review after an order; we track expiration and usage. */
CREATE TABLE review_token (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  customers_id    INT NOT NULL,
  salon_id   INT NOT NULL,
  order_id   INT NULL,
  expires_at DATETIME NOT NULL,
  used_at    DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(customers_id, salon_id, expires_at),
  CONSTRAINT fk_rt_user  FOREIGN KEY (customers_id)  REFERENCES customers(id)  ON DELETE CASCADE,
  CONSTRAINT fk_rt_salon FOREIGN KEY (salon_id) REFERENCES salon(id)  ON DELETE CASCADE,
  CONSTRAINT fk_rt_order FOREIGN KEY (order_id) REFERENCES _order(id) ON DELETE SET NULL
);

/* Line items for orders. We support both service and product rows and keep line_total for quick reads. */
CREATE TABLE order_item (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT,
  kind VARCHAR(7),
  service_id INT,
  product_id INT,
  qty INT,
  unit_price DECIMAL(4,2),
  line_total DECIMAL(9,2),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(order_id),
  CONSTRAINT fk_oi_ord  FOREIGN KEY (order_id)  REFERENCES _order(id) ON DELETE CASCADE,
  CONSTRAINT fk_oi_srv  FOREIGN KEY (service_id) REFERENCES service(id) ON DELETE SET NULL,
  CONSTRAINT fk_oi_prod FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE SET NULL
);


/* Booking links an order item to the actual appointment it books. */
CREATE TABLE booking (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_item_id INT,
  appointment_id INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX(order_item_id),
  CONSTRAINT fk_bk_item FOREIGN KEY (order_item_id) REFERENCES order_item(id) ON DELETE CASCADE,
  CONSTRAINT fk_bk_appt FOREIGN KEY (appointment_id) REFERENCES appointment(id) ON DELETE CASCADE
);

/* DATA ENTRY */

insert into users (id) values (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11), (12), (13);

insert into admins (_id, first_name, last_name, email, status, role) values (1, 'Joell', 'Minton', 'jminton0@foxnews.com', 'inactive', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (2, 'Dorotea', 'Lyttle', 'dlyttle1@ucoz.com', 'inactive', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (3, 'Cecilia', 'Penhearow', 'cpenhearow2@apache.org', 'inactive', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (4, 'Admin', 'Four', 'admin4@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (5, 'Admin', 'Five', 'admin5@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (6, 'Admin', 'Six', 'admin6@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (7, 'Admin', 'Seven', 'admin7@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (8, 'Admin', 'Eight', 'admin8@example.com', 'active', 'admin');

insert into admins (_id, first_name, last_name, email, status, role) values (9, 'Admin', 'Nine', 'admin9@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (10, 'Admin', 'Ten', 'admin10@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (11, 'Admin', 'Eleven', 'admin11@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (12, 'Admin', 'Twelve', 'admin12@example.com', 'active', 'admin');
insert into admins (_id, first_name, last_name, email, status, role) values (13, 'Admin', 'Thirteen', 'admin13@example.com', 'active', 'admin');

insert into customers (id, name, email, phone, role) values (1, 'Vassili Isoldi', 'visoldi0@odnoklassniki.ru', '493-932-1279', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (2, 'Charlie Beig', 'cbeig1@google.ru', '253-945-3737', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (3, 'Benedict Edgeon', 'bedgeon2@ask.com', '808-375-1321', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (4, 'Torrey Bedboro', 'tbedboro3@webnode.com', '638-458-6447', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (5, 'Kristo Bourtoumieux', 'kbourtoumieux4@merriam-webster.com', '826-716-9261', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (6, 'Cordy Reina', 'creina5@washington.edu', '291-141-5162', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (7, 'Alvie Benza', 'abenza6@vinaora.com', '745-584-0766', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (8, 'Elise Smither', 'esmither7@vimeo.com', '179-649-0024', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (9, 'Christophe Payler', 'cpayler8@mit.edu', '888-117-4143', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (10, 'Rickert Casini', 'rcasini9@surveymonkey.com', '372-947-7208', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (11, 'Natty Adamovitch', 'nadamovitcha@mashable.com', '962-126-9162', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (12, 'Dana Mosdell', 'dmosdellb@jimdo.com', '291-868-2618', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (13, 'Papagena Hentze', 'phentzec@t-online.de', '829-906-7735', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (14, 'Dacie Slyvester', 'dslyvesterd@china.com.cn', '618-372-5829', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (15, 'Wally Broschek', 'wbroscheke@cdc.gov', '127-664-4286', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (16, 'Janaye Spacey', 'jspaceyf@1und1.de', '384-432-5331', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (17, 'Ban Sparshutt', 'bsparshuttg@angelfire.com', '596-833-3363', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (18, 'Mikkel Gunstone', 'mgunstoneh@wiley.com', '389-343-0057', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (19, 'Mathian Tanzig', 'mtanzigi@guardian.co.uk', '839-669-0450', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (20, 'Obediah Chinge de Hals', 'ochingej@cafepress.com', '172-214-0367', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (21, 'Peter Pritchitt', 'ppritchittk@addtoany.com', '113-494-5765', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (22, 'Antonius Wark', 'awarkl@cdbaby.com', '997-544-3311', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (23, 'Savina Grout', 'sgroutm@mapy.cz', '672-371-4631', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (24, 'Patsy De Ruggero', 'pden@istockphoto.com', '937-109-0847', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (25, 'Nonie Vogeler', 'nvogelero@smugmug.com', '203-729-8387', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (26, 'Welbie de Juares', 'wdep@joomla.org', '117-360-8773', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (27, 'Viv Wadge', 'vwadgeq@usatoday.com', '392-942-5304', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (28, 'Vivyan Tether', 'vtetherr@reverbnation.com', '512-742-6540', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (29, 'Ileane Hitscher', 'ihitschers@indiegogo.com', '785-627-6367', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (30, 'Philip Moggie', 'pmoggiet@guardian.co.uk', '848-479-4421', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (31, 'Costanza Gemlbett', 'cgemlbettu@wikia.com', '909-859-7318', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (32, 'Bethina Abrahmson', 'babrahmsonv@huffingtonpost.com', '555-408-5708', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (33, 'Anita Licciardello', 'alicciardellow@mac.com', '941-567-2343', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (34, 'Cyndi McKinley', 'cmckinleyx@1und1.de', '182-657-1489', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (35, 'Leshia Giraudou', 'lgiraudouy@nasa.gov', '870-758-8787', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (36, 'Carmen Whitwell', 'cwhitwellz@omniture.com', '861-839-4865', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (37, 'Shepherd Paton', 'spaton10@vkontakte.ru', '877-658-2734', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (38, 'Shane Brunesco', 'sbrunesco11@ed.gov', '602-488-4642', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (39, 'Isidro Renackowna', 'irenackowna12@yellowpages.com', '894-235-7673', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (40, 'Valery Melmar', 'vmelmar13@japanpost.jp', '346-405-0936', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (41, 'Roman Draisey', 'rdraisey14@odnoklassniki.ru', '361-146-5090', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (42, 'Francoise Parsonage', 'fparsonage15@etsy.com', '463-192-5223', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (43, 'Amabel Lindores', 'alindores16@squarespace.com', '726-779-3449', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (44, 'Wang Tant', 'wtant17@statcounter.com', '888-633-7653', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (45, 'Morey Oager', 'moager18@clickbank.net', '423-372-9555', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (46, 'Kleon Coverlyn', 'kcoverlyn19@abc.net.au', '922-527-9101', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (47, 'Lurline Cristofaro', 'lcristofaro1a@sun.com', '244-746-0056', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (48, 'Carmel Beaushaw', 'cbeaushaw1b@shinystat.com', '255-691-5471', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (49, 'Sander Bosomworth', 'sbosomworth1c@samsung.com', '962-564-0022', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (50, 'Novelia Ghirigori', 'nghirigori1d@gravatar.com', '367-287-9159', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (51, 'Kipp O''Flaverty', 'koflaverty1e@digg.com', '304-966-0047', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (52, 'Karin Grealey', 'kgrealey1f@cocolog-nifty.com', '909-397-1972', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (53, 'Jilleen Drust', 'jdrust1g@themeforest.net', '297-345-2262', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (54, 'Maure Drains', 'mdrains1h@ezinearticles.com', '448-929-3832', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (55, 'Tobe Galle', 'tgalle1i@netlog.com', '649-308-9655', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (56, 'Alberik Ewles', 'aewles1j@quantcast.com', '724-717-1873', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (57, 'Robinette McDonagh', 'rmcdonagh1k@timesonline.co.uk', '684-671-5442', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (58, 'Zach Le Noury', 'zle1l@virginia.edu', '103-710-6877', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (59, 'Susannah Gallagher', 'sgallagher1m@merriam-webster.com', '565-378-9001', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (60, 'Leonid Praill', 'lpraill1n@bloglines.com', '224-502-4317', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (61, 'Sianna Olford', 'solford1o@wordpress.com', '263-983-6052', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (62, 'Josephine Ayres', 'jayres1p@archive.org', '631-126-2199', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (63, 'Jobina MacCaffery', 'jmaccaffery1q@scribd.com', '697-541-4023', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (64, 'Amalee Shillington', 'ashillington1r@themeforest.net', '770-266-4718', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (65, 'Nicki Plett', 'nplett1s@t.co', '646-638-0268', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (66, 'Marge Jeffress', 'mjeffress1t@jiathis.com', '204-205-6268', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (67, 'Minnie Grzegorzewicz', 'mgrzegorzewicz1u@weather.com', '382-371-5420', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (68, 'Dixie Saffin', 'dsaffin1v@sfgate.com', '454-123-1111', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (69, 'Annabela Wackett', 'awackett1w@github.com', '313-923-1072', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (70, 'Kristyn Entres', 'kentres1x@salon.com', '718-326-2211', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (71, 'Harlen McLaine', 'hmclaine1y@blogs.com', '742-994-9412', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (72, 'Reeta Petriello', 'rpetriello1z@google.cn', '579-788-3818', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (73, 'Mirna Mathivon', 'mmathivon20@constantcontact.com', '214-536-8618', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (74, 'Leicester Sanches', 'lsanches21@xinhuanet.com', '687-432-9815', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (75, 'Chanda Simm', 'csimm22@yahoo.com', '438-520-3380', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (76, 'Eldredge Rothchild', 'erothchild23@geocities.com', '251-907-7810', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (77, 'Henrie Robardet', 'hrobardet24@twitter.com', '470-468-0887', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (78, 'Arlin Stoner', 'astoner25@istockphoto.com', '446-300-9652', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (79, 'Edita Clayhill', 'eclayhill26@sakura.ne.jp', '789-221-4902', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (80, 'Candida McCulley', 'cmcculley27@cafepress.com', '226-239-1266', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (81, 'Gunner Faber', 'gfaber28@boston.com', '848-888-6855', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (82, 'Ashley Sunman', 'asunman29@newyorker.com', '660-759-3409', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (83, 'Llewellyn Postgate', 'lpostgate2a@seattletimes.com', '890-869-8804', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (84, 'Hodge Cancutt', 'hcancutt2b@reddit.com', '512-296-7841', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (85, 'Isadora Pieper', 'ipieper2c@webs.com', '390-260-4050', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (86, 'Sarge Candelin', 'scandelin2d@netvibes.com', '596-716-2711', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (87, 'Filmer Altofts', 'faltofts2e@xing.com', '260-232-9286', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (88, 'Chryste Blythin', 'cblythin2f@theatlantic.com', '582-773-2226', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (89, 'Cheri Pfaff', 'cpfaff2g@uiuc.edu', '368-336-9277', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (90, 'Wally Teresse', 'wteresse2h@nationalgeographic.com', '325-602-0071', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (91, 'Moyna Drejer', 'mdrejer2i@paypal.com', '912-566-8306', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (92, 'Shermie Avramov', 'savramov2j@technorati.com', '920-260-5142', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (93, 'Lucy Barkshire', 'lbarkshire2k@princeton.edu', '731-612-0278', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (94, 'Tiffani Gabbett', 'tgabbett2l@economist.com', '347-280-5825', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (95, 'Claudian Kneeland', 'ckneeland2m@nasa.gov', '950-780-3483', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (96, 'Jen Hoyes', 'jhoyes2n@vistaprint.com', '639-933-3479', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (97, 'Bradney Dyball', 'bdyball2o@studiopress.com', '437-289-2716', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (98, 'Kenna Halbard', 'khalbard2p@go.com', '114-354-2086', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (99, 'Jewell Berrow', 'jberrow2q@comcast.net', '383-669-4051', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (100, 'Serena Isac', 'sisac2r@devhub.com', '438-984-5238', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (101, 'Kaleb Lomax', 'klomax2s@fotki.com', '283-526-7471', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (102, 'Benedetto Gurdon', 'bgurdon2t@unblog.fr', '633-944-8840', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (103, 'Wain Cousin', 'wcousin2u@nps.gov', '815-446-2850', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (104, 'Farlay Heinzel', 'fheinzel2v@google.com.au', '854-504-0628', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (105, 'Hughie Hutchins', 'hhutchins2w@usa.gov', '686-640-8629', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (106, 'Moira Tinghill', 'mtinghill2x@vkontakte.ru', '729-345-1990', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (107, 'Joachim McGrowther', 'jmcgrowther2y@alexa.com', '479-613-5370', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (108, 'Britta Ormston', 'bormston2z@google.nl', '230-142-4153', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (109, 'Enos Meddings', 'emeddings30@bbc.co.uk', '679-759-1211', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (110, 'Sheba Daddow', 'sdaddow31@shinystat.com', '988-883-1737', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (111, 'Christos Ropp', 'cropp32@shareasale.com', '315-183-0201', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (112, 'Hansiain Jewers', 'hjewers33@engadget.com', '440-917-2544', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (113, 'Barth Ferebee', 'bferebee34@theatlantic.com', '901-975-0852', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (114, 'Corabel De L''Isle', 'cde35@ovh.net', '531-795-5918', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (115, 'Spenser Vondrak', 'svondrak36@noaa.gov', '955-748-7817', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (116, 'Sherri Gatecliff', 'sgatecliff37@digg.com', '647-654-6012', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (117, 'Elfrida Cunnow', 'ecunnow38@marketwatch.com', '693-338-8715', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (118, 'Kristine Falkus', 'kfalkus39@fc2.com', '843-428-7830', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (119, 'Humberto Halesworth', 'hhalesworth3a@mozilla.org', '665-834-7765', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (120, 'Cleopatra Olivella', 'colivella3b@opensource.org', '177-135-8319', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (121, 'Customer', '121', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (122, 'Customer', '122', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (123, 'Customer', '123', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (124, 'Customer', '124', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (125, 'Customer', '125', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (126, 'Customer', '126', '123', 'CUSTOMER');
insert into customers (id, name, email, phone, role) values (127, 'Customer', '127', '123', 'CUSTOMER');

insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (1, 1, 'Valene', 'Hair', '521 Esch Court', 'Newark', '835-196-2708', 40.735660, -74.172370);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (2, 2, 'Geraldine', 'Nails', '57 Ryan Place', 'Jersey City', '896-925-5906', 40.728220, -74.077640);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (3, 3, 'George', 'Nails', '66342 Stone Corner Point', 'Hoboken', '828-469-7732', 40.743990, -74.032360);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (4, 4, 'Nathan', 'Hair', '3024 Lunder Alley', 'Montclair', '381-563-8060', 40.823990, -74.211000);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (5, 5, 'Jermain', 'Nails', '317 Lindbergh Place', 'Paterson', '741-321-8383', 40.916770, -74.171820);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (6, 6, 'Colene', 'Extension', '31 Annamark Terrace', 'Princeton', '187-715-5483', 40.343060, -74.655070);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (7, 7, 'Bennie', 'Color', '5 Kensington Point', 'Atlantic City', '188-669-4263', 39.364280, -74.422930);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (8, 8, 'Jemima', 'Hair', '20 Hoard Place', 'Trenton', '232-455-1249', 40.220590, -74.759720);

insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (9, 9, 'Albert', 'Extension', '88 Bergen Street', 'Newark', '908-552-6732', 40.744950, -74.161850);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (10, 10, 'Henry', 'Color', '142 Lexington Avenue', 'Clifton', '973-715-4428', 40.869220, -74.157430);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (11, 11, 'Randy', 'Extension', '56 Stephenville Parkway', 'Edison', '732-931-7804', 40.530300, -74.372500);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (12, 12, 'Janice', 'Color', '2200 Chapel Avenue W', 'Cherry Hill', '856-744-9683', 39.928600, -75.021300);
insert into salon (id, owner_id, name, type, address, city, phone, latitude, longitude) values (13, 13, 'Meadow', 'Color', '17 South Street', 'Morristown', '973-582-4609', 40.796000, -74.481800);


insert into pay_method (id, user_id, brand, last4, is_default) values (1, 116, 'mastercard', 6458, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (2, 3, 'mastercard', 9520, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (3, 22, 'mastercard', 2166, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (4, 51, 'mastercard', 38, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (5, 96, 'mastercard', 9256, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (6, 14, 'mastercard', 626, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (7, 101, 'mastercard', 4704, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (8, 60, 'mastercard', 69, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (9, 119, 'mastercard', 5369, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (10, 81, 'mastercard', 5294, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (11, 6, 'mastercard', 9316, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (12, 16, 'mastercard', 8674, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (13, 83, 'mastercard', 2948, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (14, 39, 'mastercard', 4613, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (15, 80, 'mastercard', 6088, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (16, 87, 'mastercard', 2291, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (17, 42, 'mastercard', 2272, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (18, 1, 'mastercard', 2367, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (19, 94, 'mastercard', 1705, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (20, 79, 'mastercard', 8690, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (21, 23, 'mastercard', 1491, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (22, 41, 'mastercard', 5597, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (23, 123, 'mastercard', 2991, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (24, 123, 'mastercard', 5252, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (25, 96, 'mastercard', 4884, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (26, 106, 'mastercard', 5583, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (27, 3, 'mastercard', 1907, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (28, 102, 'mastercard', 2716, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (29, 87, 'mastercard', 9529, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (30, 22, 'mastercard', 6293, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (31, 62, 'mastercard', 8321, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (32, 22, 'mastercard', 6080, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (33, 52, 'mastercard', 224, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (34, 81, 'mastercard', 1438, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (35, 4, 'mastercard', 4701, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (36, 82, 'mastercard', 794, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (37, 49, 'mastercard', 6998, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (38, 101, 'mastercard', 3961, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (39, 93, 'mastercard', 4059, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (40, 55, 'mastercard', 7815, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (41, 84, 'mastercard', 2154, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (42, 66, 'mastercard', 4350, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (43, 67, 'mastercard', 8338, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (44, 95, 'mastercard', 7827, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (45, 110, 'mastercard', 1385, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (46, 117, 'mastercard', 2954, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (47, 45, 'mastercard', 9220, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (48, 35, 'mastercard', 2417, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (49, 16, 'mastercard', 4820, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (50, 63, 'mastercard', 9615, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (51, 106, 'mastercard', 6481, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (52, 66, 'mastercard', 5632, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (53, 83, 'mastercard', 376, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (54, 33, 'mastercard', 5067, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (55, 10, 'mastercard', 46, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (56, 115, 'mastercard', 154, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (57, 4, 'mastercard', 5248, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (58, 31, 'mastercard', 2543, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (59, 50, 'mastercard', 2496, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (60, 8, 'mastercard', 8654, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (61, 44, 'mastercard', 8836, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (62, 2, 'mastercard', 7638, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (63, 118, 'mastercard', 1269, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (64, 62, 'mastercard', 5755, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (65, 124, 'mastercard', 5395, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (66, 109, 'mastercard', 6563, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (67, 117, 'mastercard', 7686, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (68, 81, 'mastercard', 7447, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (69, 87, 'mastercard', 3217, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (70, 95, 'mastercard', 9936, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (71, 72, 'mastercard', 8547, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (72, 2, 'mastercard', 8723, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (73, 28, 'mastercard', 9592, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (74, 23, 'mastercard', 9486, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (75, 114, 'mastercard', 3915, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (76, 84, 'mastercard', 2189, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (77, 52, 'mastercard', 9548, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (78, 109, 'mastercard', 8368, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (79, 86, 'mastercard', 1135, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (80, 102, 'mastercard', 677, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (81, 105, 'mastercard', 1045, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (82, 11, 'mastercard', 4757, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (83, 6, 'mastercard', 2552, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (84, 85, 'mastercard', 3687, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (85, 91, 'mastercard', 4142, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (86, 120, 'mastercard', 8433, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (87, 99, 'mastercard', 2856, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (88, 61, 'mastercard', 7866, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (89, 61, 'mastercard', 8975, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (90, 71, 'mastercard', 83, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (91, 2, 'mastercard', 1301, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (92, 116, 'mastercard', 1804, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (93, 46, 'mastercard', 282, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (94, 19, 'mastercard', 7076, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (95, 98, 'mastercard', 7851, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (96, 4, 'mastercard', 544, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (97, 58, 'mastercard', 3548, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (98, 64, 'mastercard', 8123, false);
insert into pay_method (id, user_id, brand, last4, is_default) values (99, 25, 'mastercard', 5298, true);
insert into pay_method (id, user_id, brand, last4, is_default) values (100, 64, 'mastercard', 6283, true);

insert into cart (id, user_id) values (1, 36);
insert into cart (id, user_id) values (2, 15);
insert into cart (id, user_id) values (3, 96);
insert into cart (id, user_id) values (4, 110);
insert into cart (id, user_id) values (5, 102);
insert into cart (id, user_id) values (6, 23);
insert into cart (id, user_id) values (7, 13);
insert into cart (id, user_id) values (8, 101);
insert into cart (id, user_id) values (9, 3);
insert into cart (id, user_id) values (10, 38);
insert into cart (id, user_id) values (11, 81);
insert into cart (id, user_id) values (12, 87);
insert into cart (id, user_id) values (13, 18);
insert into cart (id, user_id) values (15, 39);
insert into cart (id, user_id) values (16, 45);
insert into cart (id, user_id) values (17, 31);
insert into cart (id, user_id) values (18, 49);
insert into cart (id, user_id) values (19, 119);
insert into cart (id, user_id) values (22, 127);
insert into cart (id, user_id) values (23, 55);
insert into cart (id, user_id) values (24, 52);
insert into cart (id, user_id) values (26, 78);
insert into cart (id, user_id) values (27, 77);
insert into cart (id, user_id) values (28, 42);
insert into cart (id, user_id) values (29, 58);
insert into cart (id, user_id) values (33, 105);
insert into cart (id, user_id) values (34, 103);
insert into cart (id, user_id) values (35, 25);
insert into cart (id, user_id) values (36, 74);
insert into cart (id, user_id) values (40, 117);
insert into cart (id, user_id) values (41, 67);

insert into user_image (id, customers_id, url) values (1, 1, 'https://intel.com/nam/ultrices/libero/non/mattis/pulvinar.aspx');
insert into user_image (id, customers_id, url) values (2, 2, 'http://goodreads.com/at/turpis/donec/posuere.js');
insert into user_image (id, customers_id, url) values (3, 3, 'https://omniture.com/ligula/suspendisse/ornare/consequat/lectus/in/est.json');
insert into user_image (id, customers_id, url) values (50, 50, 'https://pbs.org/vitae/nisi/nam/ultrices.html');

insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (1, 7, 'Ianthe', 'Carmel', 'icarmel0@nifty.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (2, 1, 'Joli', 'Busain', 'jbusain1@gizmodo.com', 'active', 'receptionist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (3, 7, 'Gal', 'Mayler', 'gmayler2@mysql.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (4, 5, 'Rebe', 'Erett', 'rerett3@cnn.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (5, 7, 'Glenna', 'Wodham', 'gwodham4@xing.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (6, 5, 'Cyrillus', 'Irdale', 'cirdale5@mozilla.org', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (7, 6, 'Tam', 'Metrick', 'tmetrick6@stumbleupon.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (8, 3, 'Seumas', 'Blow', 'sblow7@last.fm', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (9, 8, 'Laetitia', 'Brugh', 'lbrugh8@latimes.com', 'active', 'manager');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (10, 3, 'Angie', 'Atkyns', 'aatkyns9@fotki.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (11, 7, 'Piotr', 'Sollon', 'psollona@buzzfeed.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (12, 7, 'Bailey', 'Cardenas', 'bcardenasb@usa.gov', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (13, 5, 'Balduin', 'Teal', 'btealc@tamu.edu', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (14, 7, 'Gasparo', 'Arbor', 'garbord@blogger.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (15, 6, 'Cordey', 'Castleman', 'ccastlemane@wiley.com', 'active', 'receptionist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (16, 6, 'Jessa', 'Rutherfoord', 'jrutherfoordf@who.int', 'active', 'manager');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (17, 4, 'Louisette', 'Fingleton', 'lfingletong@eventbrite.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (18, 5, 'Sarah', 'Lednor', 'slednorh@theatlantic.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (19, 5, 'Luis', 'Hussey', 'lhusseyi@sfgate.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (20, 4, 'Natalina', 'Robbey', 'nrobbeyj@tamu.edu', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (21, 2, 'Liam', 'Goulston', 'lgoulstonk@unc.edu', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (22, 4, 'Marney', 'Purdy', 'mpurdyl@disqus.com', 'active', 'manager');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (23, 2, 'Calley', 'Temple', 'ctemplem@blinklist.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (24, 7, 'Caril', 'Gaitung', 'cgaitungn@ehow.com', 'active', 'manager');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (25, 7, 'Alford', 'Merriott', 'amerriotto@washingtonpost.com', 'active', 'receptionist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (26, 7, 'Maxwell', 'Bradock', 'mbradockp@hp.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (27, 5, 'Theo', 'Aldington', 'taldingtonq@cyberchimps.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (28, 7, 'Blondy', 'Lalonde', 'blalonder@imgur.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (29, 8, 'Kailey', 'Voysey', 'kvoyseys@vk.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (30, 6, 'Ainsley', 'Bullard', 'abullardt@webnode.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (31, 7, 'Sabrina', 'Strapp', 'sstrappu@youku.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (32, 3, 'Debra', 'Ricciardiello', 'dricciardiellov@dagondesign.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (33, 7, 'Powell', 'Augar', 'paugarw@com.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (34, 3, 'Thain', 'Comley', 'tcomleyx@bizjournals.com', 'active', 'stylist');
insert into employees (id, salon_id, first_name, last_name, email, employment_status, role) values (35, 8, 'Justen', 'Cumber', 'jcumbery@netvibes.com', 'active', 'stylist');

insert into product (id, salon_id, name, description, price, sku, stock_qty, is_active) values (1, 2, 'Yoga Mat Carrier', 'dapibus', 39.61, 'aliquam non', 18, false);
insert into product (id, salon_id, name, description, price, sku, stock_qty, is_active) values (2, 6, 'Multi-Cooker', 'amet', 28.98, 'augue quam', 1, true);
insert into product (id, salon_id, name, description, price, sku, stock_qty, is_active) values (3, 4, 'Chocolate Peanut Butter Cups', 'diam in', 44.46, 'natoque', 12, false);
insert into product (id, salon_id, name, description, price, sku, stock_qty, is_active) values (30, 7, 'Peanut Butter Chocolate Chip Bars', 'eleifend luctus', 0.36, 'nisi', 13, true);

insert into salon_hours (id, salon_id, hours) values (1, 1, '10AM-7PM');
insert into salon_hours (id, salon_id, hours) values (2, 2, '8AM-5PM');
insert into salon_hours (id, salon_id, hours) values (3, 3, '9AM-6PM');
insert into salon_hours (id, salon_id, hours) values (4, 4, '8AM-5PM');
insert into salon_hours (id, salon_id, hours) values (5, 5, '10AM-7PM');
insert into salon_hours (id, salon_id, hours) values (6, 6, '10AM-7PM');
insert into salon_hours (id, salon_id, hours) values (7, 7, '8AM-5PM');
insert into salon_hours (id, salon_id, hours) values (8, 8, '10AM-7PM');

insert into salon_verify (id, salon_id, admin_id, status) values (1, 1, 1, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (2, 2, 2, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (3, 3, 3, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (4, 4, 4, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (5, 5, 5, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (6, 6, 6, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (7, 7, 7, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (8, 8, 8, 'VERIFIED');

insert into salon_verify (id, salon_id, admin_id, status) values (9, 9, 9, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (10, 10, 10, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (11, 11, 11, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (12, 12, 12, 'VERIFIED');
insert into salon_verify (id, salon_id, admin_id, status) values (13, 13, 13, 'VERIFIED');

insert into service (id, salon_id, name, price, duration, is_active) values (1, 1, 'haircut', 76, 57, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (2, 1, 'color', 67, 59, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (3, 1, 'extension', 56, 46, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (4, 1, 'nails', 41, 54, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (5, 2, 'haircut', 69, 62, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (6, 2, 'color', 44, 37, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (7, 2, 'extension', 46, 50, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (8, 2, 'nails', 71, 43, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (9, 3, 'haircut', 75, 72, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (10, 3, 'color', 57, 32, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (11, 3, 'extension', 45, 69, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (12, 3, 'nails', 64, 54, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (13, 4, 'haircut', 55, 46, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (14, 4, 'color', 68, 73, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (15, 4, 'extension', 45, 34, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (16, 4, 'nails', 47, 80, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (17, 5, 'haircut', 61, 44, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (18, 5, 'color', 40, 78, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (19, 5, 'extension', 58, 73, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (20, 5, 'nails', 51, 65, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (21, 6, 'haircut', 53, 47, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (22, 6, 'color', 66, 80, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (23, 6, 'extension', 64, 31, 'false');
insert into service (id, salon_id, name, price, duration, is_active) values (24, 6, 'nails', 55, 46, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (25, 7, 'haircut', 49, 31, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (26, 7, 'color', 74, 61, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (27, 7, 'extension', 66, 48, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (28, 7, 'nails', 44, 44, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (29, 8, 'haircut', 68, 75, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (30, 8, 'color', 53, 38, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (31, 8, 'extension', 52, 39, 'true');
insert into service (id, salon_id, name, price, duration, is_active) values (32, 8, 'nails', 50, 56, 'false');

insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (1, 3, 23, 4);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (2, 8, 16, 4);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (3, 5, 5, 9);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (4, 2, 18, 2);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (5, 6, 1, 2);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (6, 8, 22, 8);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (7, 4, 17, 18);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (8, 8, 8, 20);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (9, 1, 12, 9);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (10, 7, 7, 7);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (11, 3, 11, 1);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (12, 5, 0, 2);
insert into cancel_policy (id, salon_id, cutoff_hours, fee) values (13, 1, 22, 6);

insert into noshow_policy (id, salon_id, grace_min, fee) values (1, 1, 15, 30.49);
insert into noshow_policy (id, salon_id, grace_min, fee) values (2, 6, 15, 46.92);
insert into noshow_policy (id, salon_id, grace_min, fee) values (3, 5, 15, 37.67);
insert into noshow_policy (id, salon_id, grace_min, fee) values (4, 4, 15, 39.67);
insert into noshow_policy (id, salon_id, grace_min, fee) values (5, 7, 15, 32.7);
insert into noshow_policy (id, salon_id, grace_min, fee) values (6, 2, 15, 40.13);
insert into noshow_policy (id, salon_id, grace_min, fee) values (7, 9, 15, 29.23);
insert into noshow_policy (id, salon_id, grace_min, fee) values (8, 10, 15, 35.99);
insert into noshow_policy (id, salon_id, grace_min, fee) values (9, 8, 15, 28.41);
insert into noshow_policy (id, salon_id, grace_min, fee) values (10, 3, 15, 37.75);

insert into noshow_policy (id, salon_id, grace_min, fee) values (11, 11, 15, 35.99);
insert into noshow_policy (id, salon_id, grace_min, fee) values (12, 12, 15, 28.41);
insert into noshow_policy (id, salon_id, grace_min, fee) values (13, 13, 15, 37.75);

insert into _order (id, customer_id, salon_id, status, subtotal, tip_amnt, tax_amnt, total_amnt, promo_id) values (1, 1, 1, 'OPEN', 24.74, 17, 3, 9, 'LA3944');
insert into _order (id, customer_id, salon_id, status, subtotal, tip_amnt, tax_amnt, total_amnt, promo_id) values (2, 2, 2, 'SUBMITTED', 67.8, 20, 6, 6, 'AI6621');
insert into _order (id, customer_id, salon_id, status, subtotal, tip_amnt, tax_amnt, total_amnt, promo_id) values (3, 3, 3, 'OPEN', 62.67, 15, 10, 2, 'LA2799');
insert into _order (id, customer_id, salon_id, status, subtotal, tip_amnt, tax_amnt, total_amnt, promo_id) values (111, 111, 7, 'FULFILLED', 78.43, 11, 8, 5, 'NH5739');

insert into loyalty_account (id, user_id, salon_id, points) values (1, 1, 3, 12);
insert into loyalty_account (id, user_id, salon_id, points) values (2, 2, 1, 12);
insert into loyalty_account (id, user_id, salon_id, points) values (3, 3, 3, 17);
insert into loyalty_account (id, user_id, salon_id, points) values (111, 111, 6, 90);

-- Salon 1
insert into review (id, salon_id, customers_id, rating, comment) values (5, 1, 12, 5, 'Excellent service and friendly staff');
insert into review (id, salon_id, customers_id, rating, comment) values (6, 1, 27, 4, 'Nice haircut, would return');
insert into review (id, salon_id, customers_id, rating, comment) values (7, 1, 33, 3, 'Average experience, a bit slow');

-- Salon 2
insert into review (id, salon_id, customers_id, rating, comment) values (8, 2, 14, 5, 'Amazing nail art!');
insert into review (id, salon_id, customers_id, rating, comment) values (9, 2, 21, 4, 'Good service, clean environment');
insert into review (id, salon_id, customers_id, rating, comment) values (10, 2, 37, 3, 'Decent, but waiting time was long');

-- Salon 3
insert into review (id, salon_id, customers_id, rating, comment) values (11, 3, 45, 5, 'Loved my nails, very professional');
insert into review (id, salon_id, customers_id, rating, comment) values (12, 3, 22, 4, 'Friendly staff and cozy atmosphere');
insert into review (id, salon_id, customers_id, rating, comment) values (13, 3, 30, 4, 'Good service overall');

-- Salon 4
insert into review (id, salon_id, customers_id, rating, comment) values (14, 4, 18, 5, 'Haircut was perfect, highly recommend');
insert into review (id, salon_id, customers_id, rating, comment) values (15, 4, 29, 4, 'Great stylist, will come again');
insert into review (id, salon_id, customers_id, rating, comment) values (16, 4, 41, 3, 'Okay experience, nothing special');

-- Salon 5
insert into review (id, salon_id, customers_id, rating, comment) values (17, 5, 20, 5, 'Excellent nail designs');
insert into review (id, salon_id, customers_id, rating, comment) values (18, 5, 26, 4, 'Staff was friendly and helpful');
insert into review (id, salon_id, customers_id, rating, comment) values (19, 5, 35, 3, 'Average, but nails turned out fine');

-- Salon 6
insert into review (id, salon_id, customers_id, rating, comment) values (20, 6, 23, 5, 'Loved the extensions, very professional');
insert into review (id, salon_id, customers_id, rating, comment) values (21, 6, 32, 4, 'Good service, felt comfortable');
insert into review (id, salon_id, customers_id, rating, comment) values (22, 6, 38, 3, 'Average experience, nothing special');

-- Salon 7
insert into review (id, salon_id, customers_id, rating, comment) values (23, 7, 16, 4, 'Nice color service');
insert into review (id, salon_id, customers_id, rating, comment) values (24, 7, 25, 3, 'Decent, could be faster');
insert into review (id, salon_id, customers_id, rating, comment) values (25, 7, 34, 2, 'Not satisfied with the outcome');

-- Salon 8
insert into review (id, salon_id, customers_id, rating, comment) values (26, 8, 19, 1, 'Very poor experience');
insert into review (id, salon_id, customers_id, rating, comment) values (27, 8, 28, 2, 'Staff was rude');
insert into review (id, salon_id, customers_id, rating, comment) values (28, 8, 36, 3, 'Okay, nothing special');

-- Salon 9
insert into review (id, salon_id, customers_id, rating, comment) values (29, 9, 13, 5, 'Great extension service');
insert into review (id, salon_id, customers_id, rating, comment) values (30, 9, 24, 4, 'Friendly and professional');
insert into review (id, salon_id, customers_id, rating, comment) values (31, 9, 39, 4, 'Good overall experience');

-- Salon 10
insert into review (id, salon_id, customers_id, rating, comment) values (32, 10, 15, 5, 'Loved my new hair color');
insert into review (id, salon_id, customers_id, rating, comment) values (33, 10, 26, 4, 'Nice stylist and service');
insert into review (id, salon_id, customers_id, rating, comment) values (34, 10, 37, 3, 'Okay, could be better');

-- Salon 11
insert into review (id, salon_id, customers_id, rating, comment) values (35, 11, 21, 5, 'Excellent extension job');
insert into review (id, salon_id, customers_id, rating, comment) values (36, 11, 30, 4, 'Very happy with service');
insert into review (id, salon_id, customers_id, rating, comment) values (37, 11, 42, 3, 'Average, but nice staff');

-- Salon 12
insert into review (id, salon_id, customers_id, rating, comment) values (38, 12, 14, 5, 'Amazing color work');
insert into review (id, salon_id, customers_id, rating, comment) values (39, 12, 27, 4, 'Good experience');
insert into review (id, salon_id, customers_id, rating, comment) values (40, 12, 33, 4, 'Would return again');

-- Salon 13
insert into review (id, salon_id, customers_id, rating, comment) values (41, 13, 18, 5, 'Fantastic color service');
insert into review (id, salon_id, customers_id, rating, comment) values (42, 13, 29, 4, 'Very satisfied with results');
insert into review (id, salon_id, customers_id, rating, comment) values (43, 13, 35, 4, 'Good, professional staff');


insert into emp_avail (id, employee_id, weekday, start_time, end_time, effective_from, effective_to) values (1, 1, 2, '7:18 AM', '1:48 AM', '1/29/2026', '7/15/2017');
insert into emp_avail (id, employee_id, weekday, start_time, end_time, effective_from, effective_to) values (2, 2, 4, '7:00 AM', '1:36 AM', '1/6/2021', '7/9/2007');
insert into emp_avail (id, employee_id, weekday, start_time, end_time, effective_from, effective_to) values (35, 35, 1, '2:51 PM', '4:44 PM', '11/13/2027', '7/22/2003');

insert into message (id, sender_id, employees_id, body, sent_at) values (1, 27, 29, 'fermentum justo', '2013-02-18 03:04:49');
insert into message (id, sender_id, employees_id, body, sent_at) values (2, 53, 14, 'elementum nullam', '2022-01-26 14:15:53');
insert into message (id, sender_id, employees_id, body, sent_at) values (50, 57, 18, 'aliquet', '2007-09-11 06:03:39');

insert into appointment (id, salon_id, customer_id, employee_id, service_id, start_at, end_at, status, price_at_book, notes) values (1, 1, 82, 29, 2, '12/10/2022 07:10:18', '11/2/2022 07:26:55', 'CANCELLED', 72.54, 'mauris vulputate');
insert into appointment (id, salon_id, customer_id, employee_id, service_id, start_at, end_at, status, price_at_book, notes) values (2, 8, 109, 30, 31, '10/23/2022 19:25:49', '11/21/2022 09:30:41', 'DONE', 96.21, 'cras mi');
insert into appointment (id, salon_id, customer_id, employee_id, service_id, start_at, end_at, status, price_at_book, notes) values (100, 1, 118, 27, 5, '10/26/2022 09:08:04', '7/24/2022 02:21:37', 'DONE', 87.17, 'aliquet');

/* Auth data input */
/* Owners for salons 1..8 as auth users; id matches users.id so FKs/models remain simple */
INSERT INTO auth_user (id, email, role)
VALUES
  (1,'owner1@example.com','OWNER'),
  (2,'owner2@example.com','OWNER'),
  (3,'owner3@example.com','OWNER'),
  (4,'owner4@example.com','OWNER'),
  (5,'owner5@example.com','OWNER'),
  (6,'owner6@example.com','OWNER'),
  (7,'owner7@example.com','OWNER'),
  (8,'owner8@example.com','OWNER')
ON DUPLICATE KEY UPDATE email=VALUES(email), role=VALUES(role);

/* Admins mirrored into auth */
INSERT INTO auth_user (id, email, role)
SELECT _id, email, 'ADMIN' FROM admins
ON DUPLICATE KEY UPDATE email=VALUES(email), role=VALUES(role);

/* Audit log + triggers */
CREATE TABLE audit_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  table_name VARCHAR(64) NOT NULL,
  row_pk VARCHAR(64) NOT NULL,
  action ENUM('INSERT','UPDATE','DELETE') NOT NULL,
  changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details JSON NULL
) COMMENT='Minimal audit trail capturing key changes.';

DROP PROCEDURE IF EXISTS _audit_write;
DELIMITER $$
CREATE PROCEDURE _audit_write(
  IN p_table VARCHAR(64), IN p_pk VARCHAR(64), IN p_action VARCHAR(10), IN p_details JSON
)
BEGIN
  INSERT INTO audit_log(table_name,row_pk,action,details)
  VALUES(p_table,p_pk,p_action,p_details);
END$$
DELIMITER ;

/* Helper to build OLD/NEW JSON safely */
DROP FUNCTION IF EXISTS _json_safe;
DELIMITER $$
CREATE FUNCTION _json_safe(p TEXT) RETURNS TEXT
DETERMINISTIC
BEGIN
  RETURN p;
END$$
DELIMITER ;

/* Triggers for a few critical tables to “keep track of events” */

DROP TRIGGER IF EXISTS trg_salon_ai;
DROP TRIGGER IF EXISTS trg_salon_au;
DROP TRIGGER IF EXISTS trg_salon_ad;
DELIMITER $$
CREATE TRIGGER trg_salon_ai AFTER INSERT ON salon
FOR EACH ROW BEGIN
  CALL _audit_write('salon', NEW.id, 'INSERT',
    JSON_OBJECT('name', NEW.name, 'owner_id', NEW.owner_id, 'city', NEW.city));
END$$
CREATE TRIGGER trg_salon_au AFTER UPDATE ON salon
FOR EACH ROW BEGIN
  CALL _audit_write('salon', NEW.id, 'UPDATE',
    JSON_OBJECT('old', JSON_OBJECT('name', OLD.name, 'city', OLD.city),
                'new', JSON_OBJECT('name', NEW.name, 'city', NEW.city)));
END$$
CREATE TRIGGER trg_salon_ad AFTER DELETE ON salon
FOR EACH ROW BEGIN
  CALL _audit_write('salon', OLD.id, 'DELETE',
    JSON_OBJECT('name', OLD.name, 'owner_id', OLD.owner_id));
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_appointment_ai;
DROP TRIGGER IF EXISTS trg_appointment_au;
DROP TRIGGER IF EXISTS trg_appointment_ad;
DELIMITER $$
CREATE TRIGGER trg_appointment_ai AFTER INSERT ON appointment
FOR EACH ROW BEGIN
  CALL _audit_write('appointment', NEW.id, 'INSERT',
    JSON_OBJECT('customer_id', NEW.customer_id, 'employee_id', NEW.employee_id, 'status', NEW.status));
END$$
CREATE TRIGGER trg_appointment_au AFTER UPDATE ON appointment
FOR EACH ROW BEGIN
  CALL _audit_write('appointment', NEW.id, 'UPDATE',
    JSON_OBJECT('old_status', OLD.status, 'new_status', NEW.status));
END$$
CREATE TRIGGER trg_appointment_ad AFTER DELETE ON appointment
FOR EACH ROW BEGIN
  CALL _audit_write('appointment', OLD.id, 'DELETE',
    JSON_OBJECT('customer_id', OLD.customer_id, 'employee_id', OLD.employee_id, 'status', OLD.status));
END$$
DELIMITER ;

/* triggers for product & review to extend audit coverage */
DROP TRIGGER IF EXISTS trg_product_ai;
DELIMITER $$
CREATE TRIGGER trg_product_ai AFTER INSERT ON product
FOR EACH ROW BEGIN
  CALL _audit_write('product', NEW.id, 'INSERT',
    JSON_OBJECT('name', NEW.name, 'price', NEW.price, 'salon_id', NEW.salon_id));
END$$
DELIMITER ;


-- Barek Stripling 11/5/25 - Added columns to cart_item and appointments table
ALTER TABLE t_salon_app.cart_item ADD start_at DATETIME NULL;
ALTER TABLE t_salon_app.cart_item ADD end_at DATETIME NULL;
ALTER TABLE t_salon_app.cart_item ADD notes TEXT NULL;

-- Barek Stripling 11/5/25 - Add appointment_image table to store images for carts --> appointments
CREATE TABLE t_salon_app.appointment_image (
	id int auto_increment NOT NULL,
	url varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
	cart_item_id int NULL,
	appointment_id int NULL,
	created_at datetime DEFAULT CURRENT_TIMESTAMP  NULL,
	updated_at datetime DEFAULT CURRENT_TIMESTAMP  on update CURRENT_TIMESTAMP NULL,
	CONSTRAINT appointment_image_pk PRIMARY KEY (id),
	CONSTRAINT appointment_image_cart_item_FK FOREIGN KEY (cart_item_id) REFERENCES t_salon_app.cart_item(id) ON DELETE CASCADE,
	CONSTRAINT appointment_image_appointment_FK FOREIGN KEY (appointment_id) REFERENCES t_salon_app.appointment(id) ON DELETE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
AUTO_INCREMENT=3;

-- Barek Stripling 11/6/25 - Add expieration date to payment methods
ALTER TABLE t_salon_app.pay_method ADD Expiration DATE NULL;



