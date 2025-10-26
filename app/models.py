from typing import List, Optional

from sqlalchemy import BigInteger, Column, DECIMAL, DateTime, Enum, ForeignKeyConstraint, Index, Integer, JSON, String, Table, Text, VARBINARY, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship
from sqlalchemy.orm.base import Mapped

Base = declarative_base()
metadata = Base.metadata


class Admins(Base):
    __tablename__ = 'admins'

    _id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    first_name = mapped_column(String(50))
    last_name = mapped_column(String(50))
    email = mapped_column(String(50))
    status = mapped_column(String(8))
    role = mapped_column(String(5))

    salon_verify: Mapped[List['SalonVerify']] = relationship('SalonVerify', uselist=True, back_populates='admin')


class AuditLog(Base):
    __tablename__ = 'audit_log'
    __table_args__ = {'comment': 'Minimal audit trail capturing key changes.'}

    id = mapped_column(BigInteger, primary_key=True)
    table_name = mapped_column(String(64), nullable=False)
    row_pk = mapped_column(String(64), nullable=False)
    action = mapped_column(Enum('INSERT', 'UPDATE', 'DELETE'), nullable=False)
    changed_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    details = mapped_column(JSON)


class AuthUser(Base):
    __tablename__ = 'auth_user'
    __table_args__ = (
        Index('email', 'email', unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    email = mapped_column(String(255), nullable=False)
    role = mapped_column(Enum('OWNER', 'ADMIN', 'CUSTOMER', 'EMPLOYEE'), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    password_hash = mapped_column(VARBINARY(72))


class Customers(Base):
    __tablename__ = 'customers'

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    name = mapped_column(String(50))
    email = mapped_column(String(50))
    phone = mapped_column(String(50))
    role = mapped_column(String(8))

    cart: Mapped[List['Cart']] = relationship('Cart', uselist=True, back_populates='user')
    notify: Mapped[List['Notify']] = relationship('Notify', uselist=True, back_populates='customers')
    pay_method: Mapped[List['PayMethod']] = relationship('PayMethod', uselist=True, back_populates='user')
    user_image: Mapped[List['UserImage']] = relationship('UserImage', uselist=True, back_populates='customers')
    _order: Mapped[List['Order']] = relationship('Order', uselist=True, back_populates='customer')
    loyalty_account: Mapped[List['LoyaltyAccount']] = relationship('LoyaltyAccount', uselist=True, back_populates='user')
    review: Mapped[List['Review']] = relationship('Review', uselist=True, back_populates='customers')
    appointment: Mapped[List['Appointment']] = relationship('Appointment', uselist=True, back_populates='customer')
    message: Mapped[List['Message']] = relationship('Message', uselist=True, back_populates='sender')
    review_reply: Mapped[List['ReviewReply']] = relationship('ReviewReply', uselist=True, back_populates='replier')
    review_token: Mapped[List['ReviewToken']] = relationship('ReviewToken', uselist=True, back_populates='customers')


class Payment(Base):
    __tablename__ = 'payment'

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    invoice: Mapped[List['Invoice']] = relationship('Invoice', uselist=True, back_populates='payment')


class Types(Base):
    __tablename__ = 'types'
    __table_args__ = (
        Index('name', 'name', unique=True),
    )

    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(100), nullable=False)

    salon: Mapped['Salon'] = relationship('Salon', secondary='salon_type_assignments', back_populates='type_')


class Users(Base):
    __tablename__ = 'users'

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    salon: Mapped[List['Salon']] = relationship('Salon', uselist=True, back_populates='owner')


class Cart(Base):
    __tablename__ = 'cart'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['customers.id'], ondelete='CASCADE', name='fk_cart_user'),
        Index('uq_cart_user', 'user_id', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    user_id = mapped_column(Integer)

    user: Mapped[Optional['Customers']] = relationship('Customers', back_populates='cart')
    cart_item: Mapped[List['CartItem']] = relationship('CartItem', uselist=True, back_populates='cart')


class Invoice(Base):
    __tablename__ = 'invoice'
    __table_args__ = (
        ForeignKeyConstraint(['payment_id'], ['payment.id'], ondelete='CASCADE', name='fk_inv_pay'),
        Index('fk_inv_pay', 'payment_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    payment_id = mapped_column(Integer)
    subtotal = mapped_column(DECIMAL(5, 2))
    tax_rate = mapped_column(DECIMAL(6, 3))
    tax_amount = mapped_column(DECIMAL(23, 2))
    total = mapped_column(DECIMAL(23, 2))
    emailed_to = mapped_column(String(255))

    payment: Mapped[Optional['Payment']] = relationship('Payment', back_populates='invoice')


class Notify(Base):
    __tablename__ = 'notify'
    __table_args__ = (
        ForeignKeyConstraint(['customers_id'], ['customers.id'], ondelete='CASCADE', name='fk_nf_user'),
        Index('customers_id', 'customers_id', 'created_at')
    )

    id = mapped_column(Integer, primary_key=True)
    customers_id = mapped_column(Integer, nullable=False)
    channel = mapped_column(Enum('EMAIL', 'SMS', 'INAPP'), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    title = mapped_column(String(160))
    body = mapped_column(String(1000))

    customers: Mapped['Customers'] = relationship('Customers', back_populates='notify')


class PayMethod(Base):
    __tablename__ = 'pay_method'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['customers.id'], ondelete='CASCADE', name='fk_pm_user'),
        Index('user_id', 'user_id', 'is_default')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    user_id = mapped_column(Integer)
    brand = mapped_column(String(50))
    last4 = mapped_column(Integer)
    is_default = mapped_column(String(50))

    user: Mapped[Optional['Customers']] = relationship('Customers', back_populates='pay_method')


class Salon(Base):
    __tablename__ = 'salon'
    __table_args__ = (
        ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_salon_owner'),
        Index('fk_salon_owner', 'owner_id'),
        Index('idx_city', 'city'),
        Index('idx_coords', 'latitude', 'longitude')
    )

    id = mapped_column(Integer, primary_key=True)
    owner_id = mapped_column(Integer, nullable=False)
    name = mapped_column(String(120), nullable=False)
    latitude = mapped_column(DECIMAL(9, 6), nullable=False)
    longitude = mapped_column(DECIMAL(9, 6), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    type = mapped_column(String(40))
    address = mapped_column(String(255))
    city = mapped_column(String(100))
    phone = mapped_column(String(25))
    about = mapped_column(Text)

    owner: Mapped['Users'] = relationship('Users', back_populates='salon')
    type_: Mapped['Types'] = relationship('Types', secondary='salon_type_assignments', back_populates='salon')
    _order: Mapped[List['Order']] = relationship('Order', uselist=True, back_populates='salon')
    cancel_policy: Mapped[List['CancelPolicy']] = relationship('CancelPolicy', uselist=True, back_populates='salon')
    employees: Mapped[List['Employees']] = relationship('Employees', uselist=True, back_populates='salon')
    loyalty_account: Mapped[List['LoyaltyAccount']] = relationship('LoyaltyAccount', uselist=True, back_populates='salon')
    loyalty_program: Mapped[List['LoyaltyProgram']] = relationship('LoyaltyProgram', uselist=True, back_populates='salon')
    noshow_policy: Mapped[List['NoshowPolicy']] = relationship('NoshowPolicy', uselist=True, back_populates='salon')
    product: Mapped[List['Product']] = relationship('Product', uselist=True, back_populates='salon')
    review: Mapped[List['Review']] = relationship('Review', uselist=True, back_populates='salon')
    salon_hours: Mapped[List['SalonHours']] = relationship('SalonHours', uselist=True, back_populates='salon')
    salon_image: Mapped[List['SalonImage']] = relationship('SalonImage', uselist=True, back_populates='salon')
    salon_verify: Mapped[List['SalonVerify']] = relationship('SalonVerify', uselist=True, back_populates='salon')
    service: Mapped[List['Service']] = relationship('Service', uselist=True, back_populates='salon')
    appointment: Mapped[List['Appointment']] = relationship('Appointment', uselist=True, back_populates='salon')
    review_token: Mapped[List['ReviewToken']] = relationship('ReviewToken', uselist=True, back_populates='salon')
    time_block: Mapped[List['TimeBlock']] = relationship('TimeBlock', uselist=True, back_populates='salon')


class UserImage(Base):
    __tablename__ = 'user_image'
    __table_args__ = (
        ForeignKeyConstraint(['customers_id'], ['customers.id'], ondelete='CASCADE', name='fk_ui_user'),
        Index('fk_ui_user', 'customers_id')
    )

    id = mapped_column(Integer, primary_key=True)
    customers_id = mapped_column(Integer, nullable=False)
    url = mapped_column(String(2000), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    customers: Mapped['Customers'] = relationship('Customers', back_populates='user_image')


class Order(Base):
    __tablename__ = '_order'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_ord_user'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], name='fk_ord_salon'),
        Index('customer_id', 'customer_id', 'created_at'),
        Index('salon_id', 'salon_id', 'created_at')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    customer_id = mapped_column(Integer)
    salon_id = mapped_column(Integer)
    status = mapped_column(String(9))
    subtotal = mapped_column(DECIMAL(5, 2))
    tip_amnt = mapped_column(Integer)
    tax_amnt = mapped_column(Integer)
    total_amnt = mapped_column(Integer)
    promo_id = mapped_column(String(50))
    submitted_at = mapped_column(DateTime)

    customer: Mapped[Optional['Customers']] = relationship('Customers', back_populates='_order')
    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='_order')
    order_item: Mapped[List['OrderItem']] = relationship('OrderItem', uselist=True, back_populates='order')
    review_token: Mapped[List['ReviewToken']] = relationship('ReviewToken', uselist=True, back_populates='order')


class CancelPolicy(Base):
    __tablename__ = 'cancel_policy'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_cp_salon'),
        Index('fk_cp_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    cutoff_hours = mapped_column(Integer)
    fee = mapped_column(Integer)

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='cancel_policy')


class Employees(Base):
    __tablename__ = 'employees'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_emp_salon'),
        Index('fk_emp_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    first_name = mapped_column(String(50))
    last_name = mapped_column(String(50))
    email = mapped_column(String(50))
    employment_status = mapped_column(String(6))
    role = mapped_column(String(12))

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='employees')
    appointment: Mapped[List['Appointment']] = relationship('Appointment', uselist=True, back_populates='employee')
    emp_avail: Mapped[List['EmpAvail']] = relationship('EmpAvail', uselist=True, back_populates='employee')
    message: Mapped[List['Message']] = relationship('Message', uselist=True, back_populates='employees')
    time_block: Mapped[List['TimeBlock']] = relationship('TimeBlock', uselist=True, back_populates='employee')


class LoyaltyAccount(Base):
    __tablename__ = 'loyalty_account'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_la_salon'),
        ForeignKeyConstraint(['user_id'], ['customers.id'], ondelete='CASCADE', name='fk_la_user'),
        Index('fk_la_salon', 'salon_id'),
        Index('uq_la', 'user_id', 'salon_id', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    user_id = mapped_column(Integer)
    salon_id = mapped_column(Integer)
    points = mapped_column(Integer)

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='loyalty_account')
    user: Mapped[Optional['Customers']] = relationship('Customers', back_populates='loyalty_account')


class LoyaltyProgram(Base):
    __tablename__ = 'loyalty_program'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_lp_salon'),
        Index('fk_lp_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    active = mapped_column(String(50))
    visits_for_reward = mapped_column(Integer)
    reward_type = mapped_column(String(12))
    reward_value = mapped_column(DECIMAL(5, 2))

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='loyalty_program')


class NoshowPolicy(Base):
    __tablename__ = 'noshow_policy'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_np_salon'),
        Index('fk_np_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    grace_min = mapped_column(Integer)
    fee = mapped_column(DECIMAL(4, 2))

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='noshow_policy')


class Product(Base):
    __tablename__ = 'product'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_prod_salon'),
        Index('salon_id', 'salon_id', 'is_active')
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    name = mapped_column(String(120), nullable=False)
    price = mapped_column(DECIMAL(10, 2), nullable=False)
    stock_qty = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    is_active = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    description = mapped_column(String(400))
    sku = mapped_column(String(64))

    salon: Mapped['Salon'] = relationship('Salon', back_populates='product')
    cart_item: Mapped[List['CartItem']] = relationship('CartItem', uselist=True, back_populates='product')
    order_item: Mapped[List['OrderItem']] = relationship('OrderItem', uselist=True, back_populates='product')


class Review(Base):
    __tablename__ = 'review'
    __table_args__ = (
        ForeignKeyConstraint(['customers_id'], ['customers.id'], ondelete='CASCADE', name='fk_rv_user'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_rv_salon'),
        Index('fk_rv_user', 'customers_id'),
        Index('salon_id', 'salon_id', 'created_at')
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    customers_id = mapped_column(Integer, nullable=False)
    rating = mapped_column(TINYINT, nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    comment = mapped_column(String(500))

    customers: Mapped['Customers'] = relationship('Customers', back_populates='review')
    salon: Mapped['Salon'] = relationship('Salon', back_populates='review')
    review_reply: Mapped[List['ReviewReply']] = relationship('ReviewReply', uselist=True, back_populates='review')


class SalonHours(Base):
    __tablename__ = 'salon_hours'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_sh_salon'),
        Index('uq_salon_day', 'salon_id', 'weekday', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    weekday = mapped_column(Integer)
    hours = mapped_column(String(8))

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='salon_hours')


class SalonImage(Base):
    __tablename__ = 'salon_image'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_si_salon'),
        Index('fk_si_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    salon_id = mapped_column(Integer, nullable=False)
    url = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    salon: Mapped['Salon'] = relationship('Salon', back_populates='salon_image')


t_salon_type_assignments = Table(
    'salon_type_assignments', metadata,
    Column('salon_id', Integer, primary_key=True, nullable=False),
    Column('type_id', Integer, primary_key=True, nullable=False),
    ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='salon_type_assignments_ibfk_1'),
    ForeignKeyConstraint(['type_id'], ['types.id'], ondelete='CASCADE', name='salon_type_assignments_ibfk_2'),
    Index('type_id', 'type_id')
)


class SalonVerify(Base):
    __tablename__ = 'salon_verify'
    __table_args__ = (
        ForeignKeyConstraint(['admin_id'], ['admins._id'], name='fk_sv_admin'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_sv_salon'),
        Index('fk_sv_admin', 'admin_id'),
        Index('salon_id', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    admin_id = mapped_column(Integer)
    status = mapped_column(String(9))

    admin: Mapped[Optional['Admins']] = relationship('Admins', back_populates='salon_verify')
    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='salon_verify')


class Service(Base):
    __tablename__ = 'service'
    __table_args__ = (
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_serv_salon'),
        Index('fk_serv_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    name = mapped_column(String(50))
    price = mapped_column(Integer)
    duration = mapped_column(Integer)
    is_active = mapped_column(String(50))

    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='service')
    order_item: Mapped[List['OrderItem']] = relationship('OrderItem', uselist=True, back_populates='service')


class Appointment(Base):
    __tablename__ = 'appointment'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_ap_customer'),
        ForeignKeyConstraint(['employee_id'], ['employees.id'], name='fk_ap_employee'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], name='fk_ap_salon'),
        Index('customer_id', 'customer_id', 'start_at'),
        Index('employee_id', 'employee_id', 'start_at'),
        Index('salon_id', 'salon_id', 'start_at')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    customer_id = mapped_column(Integer)
    employee_id = mapped_column(Integer)
    service_id = mapped_column(Integer)
    start_at = mapped_column(String(20))
    end_at = mapped_column(String(20))
    status = mapped_column(String(9))
    price_at_book = mapped_column(DECIMAL(5, 2))
    notes = mapped_column(Text)

    customer: Mapped[Optional['Customers']] = relationship('Customers', back_populates='appointment')
    employee: Mapped[Optional['Employees']] = relationship('Employees', back_populates='appointment')
    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='appointment')
    booking: Mapped[List['Booking']] = relationship('Booking', uselist=True, back_populates='appointment')


class CartItem(Base):
    __tablename__ = 'cart_item'
    __table_args__ = (
        ForeignKeyConstraint(['cart_id'], ['cart.id'], ondelete='CASCADE', name='fk_ci_cart'),
        ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='SET NULL', name='fk_ci_prod'),
        Index('cart_id', 'cart_id'),
        Index('fk_ci_prod', 'product_id')
    )

    id = mapped_column(Integer, primary_key=True)
    added_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    cart_id = mapped_column(Integer)
    kind = mapped_column(String(7))
    service_id = mapped_column(Integer)
    product_id = mapped_column(Integer)
    qty = mapped_column(Integer)
    price = mapped_column(DECIMAL(5, 2))

    cart: Mapped[Optional['Cart']] = relationship('Cart', back_populates='cart_item')
    product: Mapped[Optional['Product']] = relationship('Product', back_populates='cart_item')


class EmpAvail(Base):
    __tablename__ = 'emp_avail'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE', name='fk_av_emp'),
        Index('uq_avail', 'employee_id', 'weekday', 'effective_from', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    employee_id = mapped_column(Integer)
    weekday = mapped_column(Integer)
    start_time = mapped_column(String(50))
    end_time = mapped_column(String(50))
    effective_from = mapped_column(String(10))
    effective_to = mapped_column(String(10))

    employee: Mapped[Optional['Employees']] = relationship('Employees', back_populates='emp_avail')


class Message(Base):
    __tablename__ = 'message'
    __table_args__ = (
        ForeignKeyConstraint(['employees_id'], ['employees.id'], ondelete='CASCADE', name='fk_msg_receiver'),
        ForeignKeyConstraint(['sender_id'], ['customers.id'], ondelete='CASCADE', name='fk_msg_sender'),
        Index('employees_id', 'employees_id', 'sent_at'),
        Index('fk_msg_sender', 'sender_id')
    )

    id = mapped_column(Integer, primary_key=True)
    sender_id = mapped_column(Integer, nullable=False)
    employees_id = mapped_column(Integer, nullable=False)
    body = mapped_column(String(200), nullable=False)
    sent_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    employees: Mapped['Employees'] = relationship('Employees', back_populates='message')
    sender: Mapped['Customers'] = relationship('Customers', back_populates='message')


class OrderItem(Base):
    __tablename__ = 'order_item'
    __table_args__ = (
        ForeignKeyConstraint(['order_id'], ['_order.id'], ondelete='CASCADE', name='fk_oi_ord'),
        ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='SET NULL', name='fk_oi_prod'),
        ForeignKeyConstraint(['service_id'], ['service.id'], ondelete='SET NULL', name='fk_oi_srv'),
        Index('fk_oi_prod', 'product_id'),
        Index('fk_oi_srv', 'service_id'),
        Index('order_id', 'order_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    order_id = mapped_column(Integer)
    kind = mapped_column(String(7))
    service_id = mapped_column(Integer)
    product_id = mapped_column(Integer)
    qty = mapped_column(Integer)
    unit_price = mapped_column(DECIMAL(4, 2))
    line_total = mapped_column(DECIMAL(9, 2))

    order: Mapped[Optional['Order']] = relationship('Order', back_populates='order_item')
    product: Mapped[Optional['Product']] = relationship('Product', back_populates='order_item')
    service: Mapped[Optional['Service']] = relationship('Service', back_populates='order_item')
    booking: Mapped[List['Booking']] = relationship('Booking', uselist=True, back_populates='order_item')


class ReviewReply(Base):
    __tablename__ = 'review_reply'
    __table_args__ = (
        ForeignKeyConstraint(['replier_id'], ['customers.id'], name='fk_rr_user'),
        ForeignKeyConstraint(['review_id'], ['review.id'], ondelete='CASCADE', name='fk_rr_review'),
        Index('fk_rr_review', 'review_id'),
        Index('fk_rr_user', 'replier_id')
    )

    id = mapped_column(Integer, primary_key=True)
    review_id = mapped_column(Integer, nullable=False)
    replier_id = mapped_column(Integer, nullable=False)
    text_body = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    replier: Mapped['Customers'] = relationship('Customers', back_populates='review_reply')
    review: Mapped['Review'] = relationship('Review', back_populates='review_reply')


class ReviewToken(Base):
    __tablename__ = 'review_token'
    __table_args__ = (
        ForeignKeyConstraint(['customers_id'], ['customers.id'], ondelete='CASCADE', name='fk_rt_user'),
        ForeignKeyConstraint(['order_id'], ['_order.id'], ondelete='SET NULL', name='fk_rt_order'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_rt_salon'),
        Index('customers_id', 'customers_id', 'salon_id', 'expires_at'),
        Index('fk_rt_order', 'order_id'),
        Index('fk_rt_salon', 'salon_id')
    )

    id = mapped_column(Integer, primary_key=True)
    customers_id = mapped_column(Integer, nullable=False)
    salon_id = mapped_column(Integer, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    order_id = mapped_column(Integer)
    used_at = mapped_column(DateTime)

    customers: Mapped['Customers'] = relationship('Customers', back_populates='review_token')
    order: Mapped[Optional['Order']] = relationship('Order', back_populates='review_token')
    salon: Mapped['Salon'] = relationship('Salon', back_populates='review_token')


class TimeBlock(Base):
    __tablename__ = 'time_block'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE', name='fk_tb_emp'),
        ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE', name='fk_tb_salon'),
        Index('employee_id', 'employee_id', 'start_at'),
        Index('salon_id', 'salon_id', 'start_at')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    salon_id = mapped_column(Integer)
    employee_id = mapped_column(Integer)
    start_at = mapped_column(String(10))
    end_at = mapped_column(String(10))
    reason = mapped_column(Text)

    employee: Mapped[Optional['Employees']] = relationship('Employees', back_populates='time_block')
    salon: Mapped[Optional['Salon']] = relationship('Salon', back_populates='time_block')


class Booking(Base):
    __tablename__ = 'booking'
    __table_args__ = (
        ForeignKeyConstraint(['appointment_id'], ['appointment.id'], ondelete='CASCADE', name='fk_bk_appt'),
        ForeignKeyConstraint(['order_item_id'], ['order_item.id'], ondelete='CASCADE', name='fk_bk_item'),
        Index('fk_bk_appt', 'appointment_id'),
        Index('order_item_id', 'order_item_id')
    )

    id = mapped_column(Integer, primary_key=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    order_item_id = mapped_column(Integer)
    appointment_id = mapped_column(Integer)

    appointment: Mapped[Optional['Appointment']] = relationship('Appointment', back_populates='booking')
    order_item: Mapped[Optional['OrderItem']] = relationship('OrderItem', back_populates='booking')