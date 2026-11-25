-- =====================================================================
-- SMART CIVIC COMPLAINT MANAGEMENT AND TRACKING SYSTEM
-- Database Schema (MySQL 8.0+ / MariaDB 10.4+)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `smart_civic_complaints`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `smart_civic_complaints`;

-- Additive-only schema definitions (existing tables & data are always preserved)

-- 1. SYSTEM SETTINGS
CREATE TABLE IF NOT EXISTS `system_settings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `setting_key` VARCHAR(100) NOT NULL UNIQUE,
  `setting_value` TEXT NOT NULL,
  `description` VARCHAR(255) NULL,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. DEPARTMENTS
CREATE TABLE IF NOT EXISTS `departments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL UNIQUE,
  `code` VARCHAR(20) NOT NULL UNIQUE,
  `description` TEXT NULL,
  `is_active` TINYINT(1) DEFAULT 1,
  `contact_email` VARCHAR(150) NULL,
  `contact_phone` VARCHAR(50) NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. USERS
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role` ENUM('citizen', 'admin', 'officer', 'worker') NOT NULL DEFAULT 'citizen',
  `full_name` VARCHAR(150) NOT NULL,
  `email` VARCHAR(191) NOT NULL UNIQUE,
  `mobile_number` VARCHAR(20) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `address` VARCHAR(255) NULL,
  `city` VARCHAR(100) NULL,
  `ward_number` VARCHAR(50) NULL,
  `department_id` INT NULL,
  `is_active` TINYINT(1) DEFAULT 1,
  `is_password_reset_required` TINYINT(1) NOT NULL DEFAULT 0,
  `password_changed_at` DATETIME NULL,
  `last_login_at` DATETIME NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_user_role` (`role`),
  INDEX `idx_user_email` (`email`),
  INDEX `idx_user_mobile` (`mobile_number`),
  CONSTRAINT `fk_user_department` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. COMPLAINT CATEGORIES
CREATE TABLE IF NOT EXISTS `complaint_categories` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL UNIQUE,
  `department_id` INT NOT NULL,
  `default_priority` ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',
  `sla_hours` INT DEFAULT 48,
  `description` TEXT NULL,
  `is_active` TINYINT(1) DEFAULT 1,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_cat_dept` (`department_id`),
  CONSTRAINT `fk_category_dept` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. WORKERS PROFILE
CREATE TABLE IF NOT EXISTS `workers` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL UNIQUE,
  `department_id` INT NOT NULL,
  `employee_id` VARCHAR(50) NULL UNIQUE,
  `designation` VARCHAR(100) DEFAULT 'Field Technician',
  `is_available` TINYINT(1) DEFAULT 1,
  `active_task_count` INT DEFAULT 0,
  `completed_task_count` INT DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_worker_dept` (`department_id`),
  CONSTRAINT `fk_worker_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_worker_dept` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. COMPLAINTS
CREATE TABLE IF NOT EXISTS `complaints` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_ref` VARCHAR(50) NOT NULL UNIQUE,
  `citizen_id` INT NOT NULL,
  `department_id` INT NULL,
  `category_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NOT NULL,
  `priority` ENUM('low', 'medium', 'high', 'urgent') NOT NULL DEFAULT 'medium',
  `status` VARCHAR(60) NOT NULL DEFAULT 'Submitted',
  `assigned_officer_id` INT NULL,
  `assigned_worker_id` INT NULL,
  `officer_assigned_at` DATETIME NULL,
  `worker_assigned_at` DATETIME NULL,
  `admin_remarks` TEXT NULL,
  `officer_remarks` TEXT NULL,
  `verification_remarks` TEXT NULL,
  `verified_at` DATETIME NULL,
  `address` VARCHAR(255) NULL,
  `city` VARCHAR(100) NULL,
  `ward_number` VARCHAR(50) NULL,
  `state` VARCHAR(100) DEFAULT 'Tamil Nadu',
  `district` VARCHAR(100) DEFAULT 'Chennai',
  `street_name` VARCHAR(255) NULL,
  `locality` VARCHAR(150) NULL,
  `landmark` VARCHAR(150) NULL,
  `pincode` VARCHAR(20) NULL,
  `latitude` DECIMAL(10, 8) NULL,
  `longitude` DECIMAL(11, 8) NULL,
  `is_escalated` TINYINT(1) DEFAULT 0,
  `escalated_at` DATETIME NULL,
  `escalation_reason` TEXT NULL,
  `sla_due_date` DATETIME NULL,
  `resolved_at` DATETIME NULL,
  `rejection_reason` TEXT NULL,
  `reopen_reason` TEXT NULL,
  `reopened_count` INT DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_complaint_ref` (`complaint_ref`),
  INDEX `idx_complaint_citizen` (`citizen_id`),
  INDEX `idx_complaint_dept` (`department_id`),
  INDEX `idx_complaint_cat` (`category_id`),
  INDEX `idx_complaint_status` (`status`),
  INDEX `idx_complaint_priority` (`priority`),
  INDEX `idx_complaint_created` (`created_at`),
  INDEX `idx_complaint_coords` (`latitude`, `longitude`),
  CONSTRAINT `fk_complaint_citizen` FOREIGN KEY (`citizen_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_complaint_department` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_complaint_category` FOREIGN KEY (`category_id`) REFERENCES `complaint_categories` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. COMPLAINT ASSIGNMENTS
CREATE TABLE IF NOT EXISTS `complaint_assignments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `assigned_by_user_id` INT NOT NULL,
  `assigned_to_user_id` INT NOT NULL,
  `status` ENUM('Assigned', 'Accepted', 'In Progress', 'Completed', 'Returned') NOT NULL DEFAULT 'Assigned',
  `instructions` TEXT NULL,
  `assigned_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `accepted_at` DATETIME NULL,
  `completed_at` DATETIME NULL,
  INDEX `idx_assign_complaint` (`complaint_id`),
  INDEX `idx_assign_worker` (`assigned_to_user_id`),
  CONSTRAINT `fk_assign_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_assign_by` FOREIGN KEY (`assigned_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_assign_to` FOREIGN KEY (`assigned_to_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. COMPLAINT STATUS HISTORY (Audit Lifecycle)
CREATE TABLE IF NOT EXISTS `complaint_status_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `changed_by_user_id` INT NULL,
  `previous_status` VARCHAR(60) NULL,
  `new_status` VARCHAR(60) NOT NULL,
  `remarks` TEXT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_hist_complaint` (`complaint_id`),
  CONSTRAINT `fk_hist_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_hist_user` FOREIGN KEY (`changed_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. COMPLAINT ATTACHMENTS
CREATE TABLE IF NOT EXISTS `complaint_attachments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL,
  `uploaded_by_user_id` INT NOT NULL,
  `attachment_type` ENUM('initial', 'before_work', 'after_work', 'verification') NOT NULL DEFAULT 'initial',
  `filename` VARCHAR(255) NOT NULL,
  `original_name` VARCHAR(255) NOT NULL,
  `file_path` VARCHAR(255) NOT NULL,
  `file_size` INT NULL,
  `mime_type` VARCHAR(100) NULL,
  `file_data` LONGBLOB NULL,
  `remarks` TEXT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_att_complaint` (`complaint_id`),
  CONSTRAINT `fk_att_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_att_user` FOREIGN KEY (`uploaded_by_user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. NOTIFICATIONS
CREATE TABLE IF NOT EXISTS `notifications` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `complaint_id` INT NULL,
  `title` VARCHAR(150) NOT NULL,
  `message` TEXT NOT NULL,
  `link` VARCHAR(255) NULL,
  `notification_type` VARCHAR(50) DEFAULT 'info',
  `is_read` TINYINT(1) DEFAULT 0,
  `read_at` DATETIME NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_notif_user` (`user_id`, `is_read`),
  INDEX `idx_notif_complaint` (`complaint_id`),
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_notif_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. FEEDBACK
CREATE TABLE IF NOT EXISTS `feedback` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `complaint_id` INT NOT NULL UNIQUE,
  `citizen_id` INT NOT NULL,
  `rating` INT NOT NULL CHECK (`rating` BETWEEN 1 AND 5),
  `comment` TEXT NULL,
  `response_speed_rating` INT NULL,
  `work_quality_rating` INT NULL,
  `is_satisfied` TINYINT(1) DEFAULT 1,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_feedback_complaint` (`complaint_id`),
  INDEX `idx_feedback_citizen` (`citizen_id`),
  CONSTRAINT `fk_feedback_complaint` FOREIGN KEY (`complaint_id`) REFERENCES `complaints` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_feedback_citizen` FOREIGN KEY (`citizen_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. AUDIT LOGS
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NULL,
  `action` VARCHAR(100) NOT NULL,
  `entity_type` VARCHAR(50) NOT NULL,
  `entity_id` VARCHAR(50) NULL,
  `ip_address` VARCHAR(50) NULL,
  `user_agent` VARCHAR(255) NULL,
  `details` TEXT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_audit_user` (`user_id`),
  INDEX `idx_audit_action` (`action`),
  INDEX `idx_audit_entity` (`entity_type`, `entity_id`),
  INDEX `idx_audit_created` (`created_at`),
  CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. CONTACT MESSAGES
CREATE TABLE IF NOT EXISTS `contact_messages` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL,
  `contact` VARCHAR(150) NOT NULL,
  `message` TEXT NOT NULL,
  `is_read` TINYINT(1) NOT NULL DEFAULT 0,
  `user_id` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_contact_read_created` (`is_read`, `created_at`),
  CONSTRAINT `fk_contact_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
