"""
MODELS.PY - SQLAlchemy ORM Models
==================================
✅ All database tables as ORM models
✅ Multi-tenant with company_id on every table
✅ Relationships and indexes defined
✅ Type hints for better IDE support
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from db import Base

# ============================================================================
# COMPANIES TABLE
# ============================================================================

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    members = relationship("Member", back_populates="company", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="company", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="company", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_company_username', 'username'),
        Index('idx_company_active', 'is_active'),
    )


# ============================================================================
# USERS TABLE (Admin accounts)
# ============================================================================

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default='admin', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="users")
    
    __table_args__ = (
        Index('idx_user_company', 'company_id'),
        Index('idx_user_email', 'email'),
        Index('idx_user_active', 'is_active'),
    )


# ============================================================================
# MEMBERS TABLE (Employees being tracked)
# ============================================================================

class Member(Base):
    __tablename__ = 'members'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    position = Column(String(100))
    department = Column(String(100))
    status = Column(String(50), default='offline', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    tracker_token = Column(String(500), unique=True, index=True)  # For tracker authentication
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="members")
    activities = relationship("ActivityLog", back_populates="member", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="member", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('company_id', 'device_id', name='uq_company_device'),
        Index('idx_member_company', 'company_id'),
        Index('idx_member_device', 'device_id'),
        Index('idx_member_token', 'tracker_token'),
        Index('idx_member_status', 'status'),
    )


# ============================================================================
# ACTIVITY LOG TABLE (Raw tracking data)
# ============================================================================

class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    
    # Activity data
    timestamp = Column(DateTime, nullable=False, index=True)
    window_title = Column(Text)
    process_name = Column(String(500))
    app_name = Column(String(255), index=True)
    url = Column(Text)
    domain = Column(String(255), index=True)
    
    # State tracking
    is_idle = Column(Boolean, default=False, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Time tracking
    duration_seconds = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    company = relationship("Company", back_populates="activities")
    member = relationship("Member", back_populates="activities")
    
    __table_args__ = (
        Index('idx_activity_company_time', 'company_id', 'timestamp'),
        Index('idx_activity_member_time', 'member_id', 'timestamp'),
        Index('idx_activity_device_time', 'device_id', 'timestamp'),
        Index('idx_activity_app', 'app_name'),
        Index('idx_activity_domain', 'domain'),
    )


# ============================================================================
# SCREENSHOTS TABLE
# ============================================================================

class Screenshot(Base):
    __tablename__ = 'screenshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    
    # Screenshot data
    timestamp = Column(DateTime, nullable=False, index=True)
    file_path = Column(String(500))
    url = Column(Text)  # If using cloud storage
    thumbnail_url = Column(Text)
    
    # Metadata
    file_size = Column(Integer)  # in bytes
    width = Column(Integer)
    height = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    company = relationship("Company", back_populates="screenshots")
    member = relationship("Member", back_populates="screenshots")
    
    __table_args__ = (
        Index('idx_screenshot_company_time', 'company_id', 'timestamp'),
        Index('idx_screenshot_member_time', 'member_id', 'timestamp'),
        Index('idx_screenshot_device_time', 'device_id', 'timestamp'),
    )


# ============================================================================
# PRODUCTIVITY METRICS TABLE (Aggregated data)
# ============================================================================

class ProductivityMetric(Base):
    __tablename__ = 'productivity_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    
    # Time period
    date = Column(DateTime, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # 'hourly', 'daily', 'weekly', 'monthly'
    
    # Metrics
    screen_time_hours = Column(Float, default=0.0)
    active_time_hours = Column(Float, default=0.0)
    idle_time_hours = Column(Float, default=0.0)
    productivity_percentage = Column(Float, default=0.0)
    
    # Activity counts
    activity_count = Column(Integer, default=0)
    screenshot_count = Column(Integer, default=0)
    app_switches = Column(Integer, default=0)
    website_visits = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'member_id', 'date', 'period_type', name='uq_productivity_metric'),
        Index('idx_metric_company_date', 'company_id', 'date'),
        Index('idx_metric_member_date', 'member_id', 'date'),
        Index('idx_metric_period', 'period_type'),
    )


# ============================================================================
# APPLICATION USAGE TABLE (App-specific metrics)
# ============================================================================

class ApplicationUsage(Base):
    __tablename__ = 'application_usage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    
    # App info
    app_name = Column(String(255), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # Usage metrics
    total_hours = Column(Float, default=0.0)
    active_hours = Column(Float, default=0.0)
    idle_hours = Column(Float, default=0.0)
    window_count = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'member_id', 'app_name', 'date', name='uq_app_usage'),
        Index('idx_app_usage_company_date', 'company_id', 'date'),
        Index('idx_app_usage_member_app', 'member_id', 'app_name'),
    )


# ============================================================================
# WEBSITE VISITS TABLE
# ============================================================================

class WebsiteVisit(Base):
    __tablename__ = 'website_visits'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    
    # Website info
    domain = Column(String(255), nullable=False, index=True)
    url = Column(Text)
    title = Column(Text)
    date = Column(DateTime, nullable=False, index=True)
    
    # Visit metrics
    total_hours = Column(Float, default=0.0)
    visit_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'member_id', 'domain', 'date', name='uq_website_visit'),
        Index('idx_website_company_date', 'company_id', 'date'),
        Index('idx_website_member_domain', 'member_id', 'domain'),
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'Company',
    'User',
    'Member',
    'ActivityLog',
    'Screenshot',
    'ProductivityMetric',
    'ApplicationUsage',
    'WebsiteVisit'
]
