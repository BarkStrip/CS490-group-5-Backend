from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    CHAR,
    Column,
    DECIMAL,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    TIMESTAMP,
    Table,
    Text,
    Time,
    VARBINARY,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT, VARCHAR
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()
metadata = Base.metadata


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"comment": "Minimal audit trail capturing key changes."}

    id = mapped_column(BigInteger, primary_key=True)
    table_name = mapped_column(String(64), nullable=False)
    row_pk = mapped_column(String(64), nullable=False)
    action = mapped_column(Enum("INSERT", "UPDATE", "DELETE"), nullable=False)
    changed_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    details = mapped_column(JSON)


class AuthUser(Base):
    __tablename__ = "auth_user"
    __table_args__ = (
        Index("email", "email", unique=True),
        Index("firebase_uid", "firebase_uid", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    email = mapped_column(String(255), nullable=False)
    password_hash = mapped_column(VARBINARY(72), nullable=False)
    role = mapped_column(Enum("OWNER", "ADMIN", "CUSTOMER", "EMPLOYEE"), nullable=False)
    created_at = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )
    firebase_uid = mapped_column(String(128))

    admins: Mapped[List["Admins"]] = relationship(
        "Admins", uselist=True, back_populates="user"
    )
    customers: Mapped[List["Customers"]] = relationship(
        "Customers", uselist=True, back_populates="user"
    )
    salon_owners: Mapped[List["SalonOwners"]] = relationship(
        "SalonOwners", uselist=True, back_populates="user"
    )
    employees: Mapped[List["Employees"]] = relationship(
        "Employees", uselist=True, back_populates="user"
    )
    review_reply: Mapped[List["ReviewReply"]] = relationship(
        "ReviewReply", uselist=True, back_populates="replier"
    )


class Promos(Base):
    __tablename__ = "promos"
    __table_args__ = (Index("code", "code", unique=True),)

    id = mapped_column(Integer, primary_key=True)
    code = mapped_column(String(50), nullable=False)
    type = mapped_column(Enum("PERCENT", "FIXED_AMOUNT"), nullable=False)
    value = mapped_column(DECIMAL(10, 2), nullable=False)
    is_active = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    description = mapped_column(String(255))
    expires_at = mapped_column(DateTime)

    _order: Mapped[List["Order"]] = relationship(
        "Order", uselist=True, back_populates="promo"
    )


class Types(Base):
    __tablename__ = "types"
    __table_args__ = (Index("name", "name", unique=True),)

    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(100), nullable=False)

    salon: Mapped["Salon"] = relationship(
        "Salon", secondary="salon_type_assignments", back_populates="type"
    )


class Admins(Base):
    __tablename__ = "admins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["auth_user.id"], ondelete="CASCADE", name="fk_admin_auth_user"
        ),
        Index("user_id_unique", "user_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    first_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    phone_number = mapped_column(String(100))
    address = mapped_column(String(100))
    status = mapped_column(String(8))

    user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="admins")
    salon_verify: Mapped[List["SalonVerify"]] = relationship(
        "SalonVerify", uselist=True, back_populates="admin"
    )


class Customers(Base):
    __tablename__ = "customers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            ondelete="CASCADE",
            name="fk_customer_auth_user",
        ),
        Index("user_id_unique", "user_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    first_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    phone_number = mapped_column(String(100))
    address = mapped_column(String(100))
    gender = mapped_column(String(20))
    date_of_birth = mapped_column(Date)
    age = mapped_column(Integer)

    user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="customers")
    cart: Mapped[List["Cart"]] = relationship(
        "Cart", uselist=True, back_populates="user"
    )
    notify: Mapped[List["Notify"]] = relationship(
        "Notify", uselist=True, back_populates="customer"
    )
    pay_method: Mapped[List["PayMethod"]] = relationship(
        "PayMethod", uselist=True, back_populates="user"
    )
    user_image: Mapped[List["UserImage"]] = relationship(
        "UserImage", uselist=True, back_populates="customers"
    )
    _order: Mapped[List["Order"]] = relationship(
        "Order", uselist=True, back_populates="customer"
    )
    loyalty_account: Mapped[List["LoyaltyAccount"]] = relationship(
        "LoyaltyAccount", uselist=True, back_populates="user"
    )
    review: Mapped[List["Review"]] = relationship(
        "Review", uselist=True, back_populates="customers"
    )
    appointment: Mapped[List["Appointment"]] = relationship(
        "Appointment", uselist=True, back_populates="customer"
    )
    message: Mapped[List["Message"]] = relationship(
        "Message", uselist=True, back_populates="customer"
    )
    review_token: Mapped[List["ReviewToken"]] = relationship(
        "ReviewToken", uselist=True, back_populates="customer"
    )


class SalonOwners(Base):
    __tablename__ = "salon_owners"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["auth_user.id"], ondelete="CASCADE", name="fk_owner_auth_user"
        ),
        Index("uq_user_id", "user_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    first_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    phone_number = mapped_column(String(100))
    address = mapped_column(String(100))

    user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="salon_owners")
    salon: Mapped[List["Salon"]] = relationship(
        "Salon", uselist=True, back_populates="salon_owner"
    )


class Cart(Base):
    __tablename__ = "cart"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["customers.id"], ondelete="CASCADE", name="fk_cart_user"
        ),
        Index("uq_cart_user", "user_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(
        TIMESTAMP, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    user: Mapped["Customers"] = relationship("Customers", back_populates="cart")
    cart_item: Mapped[List["CartItem"]] = relationship(
        "CartItem", uselist=True, back_populates="cart"
    )


class Notify(Base):
    __tablename__ = "notify"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="CASCADE", name="fk_nf_user"
        ),
        Index("customers_id", "customer_id", "created_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    customer_id = mapped_column(Integer, nullable=False)
    channel = mapped_column(Enum("EMAIL", "SMS", "INAPP"), nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    title = mapped_column(String(160))
    body = mapped_column(Text)
    read_at = mapped_column(DateTime)

    customer: Mapped["Customers"] = relationship("Customers", back_populates="notify")


class PayMethod(Base):
    __tablename__ = "pay_method"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["customers.id"], ondelete="CASCADE", name="fk_pm_user"
        ),
        Index("user_id", "user_id", "is_default"),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    is_default = mapped_column(TINYINT(1), nullable=False, server_default=text("'0'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    brand = mapped_column(String(50))
    last4 = mapped_column(CHAR(4))
    Expiration = mapped_column(Date)

    user: Mapped["Customers"] = relationship("Customers", back_populates="pay_method")
    payment: Mapped[List["Payment"]] = relationship(
        "Payment", uselist=True, back_populates="pay_method"
    )


class Salon(Base):
    __tablename__ = "salon"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_owner_id"],
            ["salon_owners.id"],
            ondelete="RESTRICT",
            name="fk_salon_owner_profile",
        ),
        Index("fk_salon_owner_profile", "salon_owner_id"),
        Index("idx_city", "city"),
        Index("idx_coords", "latitude", "longitude"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_owner_id = mapped_column(Integer, nullable=False)
    name = mapped_column(String(120), nullable=False)
    latitude = mapped_column(DECIMAL(9, 6), nullable=False)
    longitude = mapped_column(DECIMAL(9, 6), nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    address = mapped_column(String(255))
    city = mapped_column(String(100))
    phone = mapped_column(String(25))
    about = mapped_column(Text)

    salon_owner: Mapped["SalonOwners"] = relationship(
        "SalonOwners", back_populates="salon"
    )
    type: Mapped[List["Types"]] = relationship(
        "Types", secondary="salon_type_assignments", back_populates="salon"
    )
    _order: Mapped[List["Order"]] = relationship(
        "Order", uselist=True, back_populates="salon"
    )
    cancel_policy: Mapped[List["CancelPolicy"]] = relationship(
        "CancelPolicy", uselist=True, back_populates="salon"
    )
    employees: Mapped[List["Employees"]] = relationship(
        "Employees", uselist=True, back_populates="salon"
    )
    loyalty_account: Mapped[List["LoyaltyAccount"]] = relationship(
        "LoyaltyAccount", uselist=True, back_populates="salon"
    )
    loyalty_program: Mapped[List["LoyaltyProgram"]] = relationship(
        "LoyaltyProgram", uselist=True, back_populates="salon"
    )
    noshow_policy: Mapped[List["NoshowPolicy"]] = relationship(
        "NoshowPolicy", uselist=True, back_populates="salon"
    )
    product: Mapped[List["Product"]] = relationship(
        "Product", uselist=True, back_populates="salon"
    )
    review: Mapped[List["Review"]] = relationship(
        "Review", uselist=True, back_populates="salon"
    )
    salon_hours: Mapped[List["SalonHours"]] = relationship(
        "SalonHours", uselist=True, back_populates="salon"
    )
    salon_image: Mapped[List["SalonImage"]] = relationship(
        "SalonImage", uselist=True, back_populates="salon"
    )
    salon_verify: Mapped[List["SalonVerify"]] = relationship(
        "SalonVerify", uselist=True, back_populates="salon"
    )
    service: Mapped[List["Service"]] = relationship(
        "Service", uselist=True, back_populates="salon"
    )
    appointment: Mapped[List["Appointment"]] = relationship(
        "Appointment", uselist=True, back_populates="salon"
    )
    review_token: Mapped[List["ReviewToken"]] = relationship(
        "ReviewToken", uselist=True, back_populates="salon"
    )
    time_block: Mapped[List["TimeBlock"]] = relationship(
        "TimeBlock", uselist=True, back_populates="salon"
    )


class UserImage(Base):
    __tablename__ = "user_image"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customers_id"], ["customers.id"], ondelete="CASCADE", name="fk_ui_user"
        ),
        Index("fk_ui_user", "customers_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    customers_id = mapped_column(Integer, nullable=False)
    url = mapped_column(String(2000), nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    customers: Mapped["Customers"] = relationship(
        "Customers", back_populates="user_image"
    )


class Order(Base):
    __tablename__ = "_order"
    __table_args__ = (
        ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_ord_user"),
        ForeignKeyConstraint(
            ["promo_id"], ["promos.id"], ondelete="SET NULL", name="fk_order_promo"
        ),
        ForeignKeyConstraint(["salon_id"], ["salon.id"], name="fk_ord_salon"),
        Index("customer_id", "customer_id", "created_at"),
        Index("fk_order_promo", "promo_id"),
        Index("salon_id", "salon_id", "created_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    customer_id = mapped_column(Integer)
    salon_id = mapped_column(Integer)
    status = mapped_column(String(9))
    subtotal = mapped_column(DECIMAL(10, 2))
    tip_amnt = mapped_column(DECIMAL(10, 2))
    tax_amnt = mapped_column(DECIMAL(10, 2))
    total_amnt = mapped_column(DECIMAL(10, 2))
    promo_id = mapped_column(Integer)
    submitted_at = mapped_column(DateTime)
    refund_reason = mapped_column(Text)

    customer: Mapped[Optional["Customers"]] = relationship(
        "Customers", back_populates="_order"
    )
    promo: Mapped[Optional["Promos"]] = relationship("Promos", back_populates="_order")
    salon: Mapped[Optional["Salon"]] = relationship("Salon", back_populates="_order")
    order_item: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", uselist=True, back_populates="order"
    )
    payment: Mapped[List["Payment"]] = relationship(
        "Payment", uselist=True, back_populates="order"
    )
    review_token: Mapped[List["ReviewToken"]] = relationship(
        "ReviewToken", uselist=True, back_populates="order"
    )
    loyalty_transaction: Mapped[List["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", uselist=True, back_populates="order"
    )


class CancelPolicy(Base):
    __tablename__ = "cancel_policy"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_cp_salon"
        ),
        Index("fk_cp_salon", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    salon_id = mapped_column(Integer)
    cutoff_hours = mapped_column(Integer)
    fee = mapped_column(Integer)

    salon: Mapped[Optional["Salon"]] = relationship(
        "Salon", back_populates="cancel_policy"
    )


class Employees(Base):
    __tablename__ = "employees"
    __table_args__ = (
        ForeignKeyConstraint(["salon_id"], ["salon.id"], name="fk_emp_salon"),
        ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            ondelete="CASCADE",
            name="fk_employee_auth_user",
        ),
        Index("fk_emp_salon", "salon_id"),
        Index("user_id_unique", "user_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    salon_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    first_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    phone_number = mapped_column(String(100))
    address = mapped_column(String(100))
    employment_status = mapped_column(String(15))
    employee_type = mapped_column(String(50))

    salon: Mapped["Salon"] = relationship("Salon", back_populates="employees")
    user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="employees")
    appointment: Mapped[List["Appointment"]] = relationship(
        "Appointment", uselist=True, back_populates="employee"
    )
    emp_avail: Mapped[List["EmpAvail"]] = relationship(
        "EmpAvail", uselist=True, back_populates="employee"
    )
    message: Mapped[List["Message"]] = relationship(
        "Message", uselist=True, back_populates="employee"
    )
    time_block: Mapped[List["TimeBlock"]] = relationship(
        "TimeBlock", uselist=True, back_populates="employee"
    )


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_account"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_la_salon"
        ),
        ForeignKeyConstraint(
            ["user_id"], ["customers.id"], ondelete="CASCADE", name="fk_la_user"
        ),
        Index("fk_la_salon", "salon_id"),
        Index("uq_la", "user_id", "salon_id", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, nullable=False)
    salon_id = mapped_column(Integer, nullable=False)
    points = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    salon: Mapped["Salon"] = relationship("Salon", back_populates="loyalty_account")
    user: Mapped["Customers"] = relationship(
        "Customers", back_populates="loyalty_account"
    )
    loyalty_transaction: Mapped[List["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", uselist=True, back_populates="loyalty_account"
    )


class LoyaltyProgram(Base):
    __tablename__ = "loyalty_program"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_lp_salon"
        ),
        Index("fk_lp_salon", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    active = mapped_column(TINYINT(1), nullable=False, server_default=text("'0'"))
    program_type = mapped_column(
        Enum("POINTS", "VISITS"), nullable=False, server_default=text("'POINTS'")
    )
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    points_per_dollar = mapped_column(DECIMAL(10, 2), server_default=text("'1.00'"))
    visits_for_reward = mapped_column(Integer)
    reward_type = mapped_column(Enum("PERCENT", "FIXED_AMOUNT", "FREE_ITEM"))
    reward_value = mapped_column(DECIMAL(10, 2))
    reward_description = mapped_column(String(255), server_default=text("'Reward'"))
    points_for_reward = mapped_column(Integer, server_default=text("'1000'"))

    salon: Mapped["Salon"] = relationship("Salon", back_populates="loyalty_program")


class NoshowPolicy(Base):
    __tablename__ = "noshow_policy"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_np_salon"
        ),
        Index("fk_np_salon", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    grace_min = mapped_column(Integer)
    fee = mapped_column(DECIMAL(10, 2))

    salon: Mapped["Salon"] = relationship("Salon", back_populates="noshow_policy")


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="RESTRICT", name="fk_prod_salon"
        ),
        Index("salon_id", "salon_id", "is_active"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    name = mapped_column(String(120), nullable=False)
    price = mapped_column(DECIMAL(10, 2), nullable=False)
    stock_qty = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    is_active = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    description = mapped_column(Text)
    image_url = mapped_column(String(512))
    sku = mapped_column(String(64))

    salon: Mapped["Salon"] = relationship("Salon", back_populates="product")
    cart_item: Mapped[List["CartItem"]] = relationship(
        "CartItem", uselist=True, back_populates="product"
    )
    order_item: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", uselist=True, back_populates="product"
    )


class Review(Base):
    __tablename__ = "review"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customers_id"], ["customers.id"], ondelete="CASCADE", name="fk_rv_user"
        ),
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_rv_salon"
        ),
        Index("fk_rv_user", "customers_id"),
        Index("salon_id", "salon_id", "created_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    customers_id = mapped_column(Integer, nullable=False)
    rating = mapped_column(TINYINT, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    comment = mapped_column(String(500))

    customers: Mapped["Customers"] = relationship("Customers", back_populates="review")
    salon: Mapped["Salon"] = relationship("Salon", back_populates="review")
    review_image: Mapped[List["ReviewImage"]] = relationship(
        "ReviewImage", uselist=True, back_populates="review"
    )
    review_reply: Mapped[List["ReviewReply"]] = relationship(
        "ReviewReply", uselist=True, back_populates="review"
    )


class SalonHours(Base):
    __tablename__ = "salon_hours"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_sh_salon"
        ),
        Index("uq_salon_day", "salon_id", "weekday", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    weekday = mapped_column(Integer, nullable=False)
    is_open = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    open_time = mapped_column(Time)
    close_time = mapped_column(Time)

    salon: Mapped["Salon"] = relationship("Salon", back_populates="salon_hours")


class SalonImage(Base):
    __tablename__ = "salon_image"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_si_salon"
        ),
        Index("salon_id_order", "salon_id", "display_order"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    url = mapped_column(Text, nullable=False)
    display_order = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    salon: Mapped["Salon"] = relationship("Salon", back_populates="salon_image")


t_salon_type_assignments = Table(
    "salon_type_assignments",
    metadata,
    Column("salon_id", Integer, primary_key=True, nullable=False),
    Column("type_id", Integer, primary_key=True, nullable=False),
    ForeignKeyConstraint(
        ["salon_id"],
        ["salon.id"],
        ondelete="CASCADE",
        onupdate="CASCADE",
        name="fk_salon_type_assignments_salon",
    ),
    ForeignKeyConstraint(
        ["type_id"],
        ["types.id"],
        ondelete="CASCADE",
        onupdate="CASCADE",
        name="fk_salon_type_assignments_type",
    ),
    Index("idx_salon_id", "salon_id"),
    Index("idx_type_id", "type_id"),
)


class SalonVerify(Base):
    __tablename__ = "salon_verify"
    __table_args__ = (
        ForeignKeyConstraint(
            ["admin_id"], ["admins.id"], ondelete="SET NULL", name="fk_sv_admin"
        ),
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="RESTRICT", name="fk_sv_salon"
        ),
        Index("fk_sv_admin", "admin_id"),
        Index("salon_id", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    status = mapped_column(
        Enum("PENDING", "APPROVED", "REJECTED"),
        nullable=False,
        server_default=text("'PENDING'"),
    )
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    admin_id = mapped_column(Integer)

    admin: Mapped[Optional["Admins"]] = relationship(
        "Admins", back_populates="salon_verify"
    )
    salon: Mapped["Salon"] = relationship("Salon", back_populates="salon_verify")


class Service(Base):
    __tablename__ = "service"
    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="RESTRICT", name="fk_serv_salon"
        ),
        Index("fk_serv_salon", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    salon_id = mapped_column(Integer, nullable=False)
    name = mapped_column(String(50), nullable=False)
    price = mapped_column(DECIMAL(10, 2), nullable=False, server_default=text("'0.00'"))
    duration = mapped_column(Integer, nullable=False, server_default=text("'30'"))
    is_active = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    icon_url = mapped_column(Text)

    salon: Mapped["Salon"] = relationship("Salon", back_populates="service")
    appointment: Mapped[List["Appointment"]] = relationship(
        "Appointment", uselist=True, back_populates="service"
    )
    cart_item: Mapped[List["CartItem"]] = relationship(
        "CartItem", uselist=True, back_populates="service"
    )
    order_item: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", uselist=True, back_populates="service"
    )


class Appointment(Base):
    __tablename__ = "appointment"
    __table_args__ = (
        ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_ap_customer"),
        ForeignKeyConstraint(["employee_id"], ["employees.id"], name="fk_ap_employee"),
        ForeignKeyConstraint(["salon_id"], ["salon.id"], name="fk_ap_salon"),
        ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="SET NULL", name="fk_ap_service"
        ),
        Index("customer_id", "customer_id", "start_at"),
        Index("employee_id", "employee_id", "start_at"),
        Index("fk_ap_service", "service_id"),
        Index("salon_id", "salon_id", "start_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer)
    customer_id = mapped_column(Integer)
    employee_id = mapped_column(Integer)
    service_id = mapped_column(Integer)
    start_at = mapped_column(DateTime, nullable=False)
    end_at = mapped_column(DateTime, nullable=False)
    status = mapped_column(String(9))
    price_at_book = mapped_column(DECIMAL(10, 2))
    notes = mapped_column(Text)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    customer: Mapped[Optional["Customers"]] = relationship(
        "Customers", back_populates="appointment"
    )
    employee: Mapped[Optional["Employees"]] = relationship(
        "Employees", back_populates="appointment"
    )
    salon: Mapped[Optional["Salon"]] = relationship(
        "Salon", back_populates="appointment"
    )
    service: Mapped[Optional["Service"]] = relationship(
        "Service", back_populates="appointment"
    )
    appointment_image: Mapped[List["AppointmentImage"]] = relationship(
        "AppointmentImage", uselist=True, back_populates="appointment"
    )
    booking: Mapped[List["Booking"]] = relationship(
        "Booking", uselist=True, back_populates="appointment"
    )
    loyalty_transaction: Mapped[List["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", uselist=True, back_populates="appointment"
    )


class CartItem(Base):
    __tablename__ = "cart_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cart_id"], ["cart.id"], ondelete="CASCADE", name="fk_ci_cart"
        ),
        ForeignKeyConstraint(
            ["product_id"], ["product.id"], ondelete="SET NULL", name="fk_ci_prod"
        ),
        ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="SET NULL", name="fk_ci_serv"
        ),
        Index("fk_ci_cart", "cart_id"),
        Index("fk_ci_prod", "product_id"),
        Index("fk_ci_serv", "service_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    cart_id = mapped_column(Integer, nullable=False)
    qty = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    kind = mapped_column(String(7))
    product_id = mapped_column(Integer)
    service_id = mapped_column(Integer)
    price = mapped_column(DECIMAL(10, 2))
    added_at = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(
        TIMESTAMP, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )
    start_at = mapped_column(DateTime)
    end_at = mapped_column(DateTime)
    notes = mapped_column(Text)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="cart_item")
    product: Mapped[Optional["Product"]] = relationship(
        "Product", back_populates="cart_item"
    )
    service: Mapped[Optional["Service"]] = relationship(
        "Service", back_populates="cart_item"
    )
    appointment_image: Mapped[List["AppointmentImage"]] = relationship(
        "AppointmentImage", uselist=True, back_populates="cart_item"
    )


class EmpAvail(Base):
    __tablename__ = "emp_avail"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE", name="fk_av_emp"
        ),
        Index("uq_avail", "employee_id", "weekday", "effective_from", unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    employee_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    weekday = mapped_column(Integer)
    start_time = mapped_column(Time)
    end_time = mapped_column(Time)
    effective_from = mapped_column(Date)
    effective_to = mapped_column(Date)

    employee: Mapped["Employees"] = relationship(
        "Employees", back_populates="emp_avail"
    )


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_msg_customer",
        ),
        ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
            name="fk_msg_employee",
        ),
        Index("employees_id", "employee_id"),
        Index("fk_msg_sender", "customer_id"),
        Index("idx_customer_thread", "customer_id", "created_at"),
        Index("idx_employee_thread", "employee_id", "created_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    customer_id = mapped_column(Integer, nullable=False)
    employee_id = mapped_column(Integer, nullable=False)
    sender_role = mapped_column(Enum("CUSTOMER", "EMPLOYEE"), nullable=False)
    body = mapped_column(Text, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    customer: Mapped["Customers"] = relationship("Customers", back_populates="message")
    employee: Mapped["Employees"] = relationship("Employees", back_populates="message")


class OrderItem(Base):
    __tablename__ = "order_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id"], ["_order.id"], ondelete="CASCADE", name="fk_oi_ord"
        ),
        ForeignKeyConstraint(
            ["product_id"], ["product.id"], ondelete="SET NULL", name="fk_oi_prod"
        ),
        ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="SET NULL", name="fk_oi_srv"
        ),
        Index("fk_oi_prod", "product_id"),
        Index("fk_oi_srv", "service_id"),
        Index("order_id", "order_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    order_id = mapped_column(Integer, nullable=False)
    qty = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    kind = mapped_column(String(7))
    service_id = mapped_column(Integer)
    product_id = mapped_column(Integer)
    unit_price = mapped_column(DECIMAL(10, 2))
    line_total = mapped_column(DECIMAL(10, 2))

    order: Mapped["Order"] = relationship("Order", back_populates="order_item")
    product: Mapped[Optional["Product"]] = relationship(
        "Product", back_populates="order_item"
    )
    service: Mapped[Optional["Service"]] = relationship(
        "Service", back_populates="order_item"
    )
    booking: Mapped[List["Booking"]] = relationship(
        "Booking", uselist=True, back_populates="order_item"
    )


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (
        ForeignKeyConstraint(["order_id"], ["_order.id"], name="fk_pay_order"),
        ForeignKeyConstraint(
            ["pay_method_id"], ["pay_method.id"], name="fk_pay_method"
        ),
        Index("fk_pay_method", "pay_method_id"),
        Index("fk_pay_order", "order_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    order_id = mapped_column(Integer, nullable=False)
    pay_method_id = mapped_column(Integer, nullable=False)
    amount = mapped_column(DECIMAL(10, 2), nullable=False)
    status = mapped_column(
        Enum("PENDING", "SUCCESSFUL", "FAILED"),
        nullable=False,
        server_default=text("'PENDING'"),
    )
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    transaction_id = mapped_column(String(255))

    order: Mapped["Order"] = relationship("Order", back_populates="payment")
    pay_method: Mapped["PayMethod"] = relationship(
        "PayMethod", back_populates="payment"
    )
    invoice: Mapped[List["Invoice"]] = relationship(
        "Invoice", uselist=True, back_populates="payment"
    )


class ReviewImage(Base):
    __tablename__ = "review_image"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id"], ["review.id"], ondelete="CASCADE", name="review_image_ibfk_1"
        ),
        Index("review_id", "review_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    url = mapped_column(String(512), nullable=False)
    review_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    review: Mapped["Review"] = relationship("Review", back_populates="review_image")


class ReviewReply(Base):
    __tablename__ = "review_reply"
    __table_args__ = (
        ForeignKeyConstraint(
            ["replier_id"],
            ["auth_user.id"],
            ondelete="RESTRICT",
            name="fk_rr_replier_user",
        ),
        ForeignKeyConstraint(
            ["review_id"], ["review.id"], ondelete="CASCADE", name="fk_rr_review"
        ),
        Index("fk_rr_review", "review_id"),
        Index("fk_rr_user", "replier_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    review_id = mapped_column(Integer, nullable=False)
    replier_id = mapped_column(Integer, nullable=False)
    text_body = mapped_column(Text, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    replier: Mapped["AuthUser"] = relationship(
        "AuthUser", back_populates="review_reply"
    )
    review: Mapped["Review"] = relationship("Review", back_populates="review_reply")


class ReviewToken(Base):
    __tablename__ = "review_token"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="CASCADE", name="fk_rt_customer"
        ),
        ForeignKeyConstraint(
            ["order_id"], ["_order.id"], ondelete="SET NULL", name="fk_rt_order"
        ),
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_rt_salon"
        ),
        Index("customer_salon_expires", "customer_id", "salon_id", "expires_at"),
        Index("fk_rt_order", "order_id"),
        Index("fk_rt_salon", "salon_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    customer_id = mapped_column(Integer, nullable=False)
    salon_id = mapped_column(Integer, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    order_id = mapped_column(Integer)
    used_at = mapped_column(DateTime)

    customer: Mapped["Customers"] = relationship(
        "Customers", back_populates="review_token"
    )
    order: Mapped[Optional["Order"]] = relationship(
        "Order", back_populates="review_token"
    )
    salon: Mapped["Salon"] = relationship("Salon", back_populates="review_token")


class TimeBlock(Base):
    __tablename__ = "time_block"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE", name="fk_tb_emp"
        ),
        ForeignKeyConstraint(
            ["salon_id"], ["salon.id"], ondelete="CASCADE", name="fk_tb_salon"
        ),
        Index("idx_employee_start", "employee_id", "start_at"),
        Index("idx_salon_start", "salon_id", "start_at"),
    )

    id = mapped_column(Integer, primary_key=True)
    employee_id = mapped_column(Integer, nullable=False)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    salon_id = mapped_column(Integer)
    start_at = mapped_column(DateTime)
    end_at = mapped_column(DateTime)
    reason = mapped_column(Text)

    employee: Mapped["Employees"] = relationship(
        "Employees", back_populates="time_block"
    )
    salon: Mapped[Optional["Salon"]] = relationship(
        "Salon", back_populates="time_block"
    )


class AppointmentImage(Base):
    __tablename__ = "appointment_image"
    __table_args__ = (
        ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            ondelete="CASCADE",
            name="appointment_image_appointment_FK",
        ),
        ForeignKeyConstraint(
            ["cart_item_id"],
            ["cart_item.id"],
            ondelete="CASCADE",
            name="appointment_image_cart_item_FK",
        ),
        Index("appointment_image_appointment_FK", "appointment_id"),
        Index("appointment_image_cart_item_FK", "cart_item_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    url = mapped_column(VARCHAR(512), nullable=False)
    cart_item_id = mapped_column(Integer)
    appointment_id = mapped_column(Integer)
    created_at = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    appointment: Mapped[Optional["Appointment"]] = relationship(
        "Appointment", back_populates="appointment_image"
    )
    cart_item: Mapped[Optional["CartItem"]] = relationship(
        "CartItem", back_populates="appointment_image"
    )


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            ondelete="CASCADE",
            name="fk_bk_appt",
        ),
        ForeignKeyConstraint(
            ["order_item_id"], ["order_item.id"], ondelete="CASCADE", name="fk_bk_item"
        ),
        Index("fk_bk_appt", "appointment_id"),
        Index("order_item_id", "order_item_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    order_item_id = mapped_column(Integer)
    appointment_id = mapped_column(Integer)

    appointment: Mapped[Optional["Appointment"]] = relationship(
        "Appointment", back_populates="booking"
    )
    order_item: Mapped[Optional["OrderItem"]] = relationship(
        "OrderItem", back_populates="booking"
    )


class Invoice(Base):
    __tablename__ = "invoice"
    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id"], ["payment.id"], ondelete="SET NULL", name="fk_inv_pay"
        ),
        Index("fk_inv_pay", "payment_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    payment_id = mapped_column(Integer)
    subtotal = mapped_column(DECIMAL(10, 2))
    tax_rate = mapped_column(DECIMAL(6, 3))
    tax_amount = mapped_column(DECIMAL(10, 2))
    total = mapped_column(DECIMAL(10, 2))
    emailed_to = mapped_column(String(255))

    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment", back_populates="invoice"
    )


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transaction"
    __table_args__ = (
        ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            ondelete="SET NULL",
            name="loyalty_transaction_ibfk_3",
        ),
        ForeignKeyConstraint(
            ["loyalty_account_id"],
            ["loyalty_account.id"],
            ondelete="CASCADE",
            name="loyalty_transaction_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["order_id"],
            ["_order.id"],
            ondelete="SET NULL",
            name="loyalty_transaction_ibfk_2",
        ),
        Index("idx_appointment", "appointment_id"),
        Index("idx_loyalty_account", "loyalty_account_id"),
        Index("idx_order", "order_id"),
    )

    id = mapped_column(Integer, primary_key=True)
    loyalty_account_id = mapped_column(Integer, nullable=False)
    points_change = mapped_column(
        Integer, nullable=False, comment="Positive for earned, negative for spent"
    )
    created_at = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    reason = mapped_column(
        String(50), comment="e.g., PURCHASE, REDEEM_REWARD, MANUAL_ADJUST"
    )
    order_id = mapped_column(Integer)
    appointment_id = mapped_column(Integer)

    appointment: Mapped[Optional["Appointment"]] = relationship(
        "Appointment", back_populates="loyalty_transaction"
    )
    loyalty_account: Mapped["LoyaltyAccount"] = relationship(
        "LoyaltyAccount", back_populates="loyalty_transaction"
    )
    order: Mapped[Optional["Order"]] = relationship(
        "Order", back_populates="loyalty_transaction"
    )
