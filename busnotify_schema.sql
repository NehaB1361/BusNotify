-- ============================================================================
-- BusNotify - Smart Bus Delay Prediction and Passenger Information System
-- Complete MySQL 8+ Database Creation & Schema DDL Script
-- ============================================================================
-- Compatible with MySQL 8.0+ / 8.4+ / 9.x
-- Default Database Name: busnotify (or mysql94)
-- Character Set: utf8mb4 (Full Unicode support including Marathi names)
-- Collation: utf8mb4_0900_ai_ci
-- ============================================================================

-- 1. Initialize Database
CREATE DATABASE IF NOT EXISTS `busnotify` 
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_0900_ai_ci;

USE `busnotify`;

-- 2. Session Configuration
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';

-- ============================================================================
-- 3. DROP TABLES (Reverse Dependency Order for Clean Setup)
-- ============================================================================
DROP TABLE IF EXISTS `audit_logs`;
DROP TABLE IF EXISTS `notifications`;
DROP TABLE IF EXISTS `passenger_transfers`;
DROP TABLE IF EXISTS `replacement_buses`;
DROP TABLE IF EXISTS `depot_requests`;
DROP TABLE IF EXISTS `alternative_recommendations`;
DROP TABLE IF EXISTS `incidents`;
DROP TABLE IF EXISTS `historical_delays`;
DROP TABLE IF EXISTS `passenger_counts`;
DROP TABLE IF EXISTS `live_gps`;
DROP TABLE IF EXISTS `trips`;
DROP TABLE IF EXISTS `drivers`;
DROP TABLE IF EXISTS `bus_capacity`;
DROP TABLE IF EXISTS `buses`;
DROP TABLE IF EXISTS `route_connectivity`;
DROP TABLE IF EXISTS `route_stops`;
DROP TABLE IF EXISTS `routes`;
DROP TABLE IF EXISTS `stops`;
DROP TABLE IF EXISTS `users`;

-- ============================================================================
-- 4. TABLE CREATION DDL (Forward Dependency Order)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table 1: users (Authentication & Role-Based Access Control)
-- Roles: 'passenger', 'driver', 'admin', 'depot_operator'
-- ----------------------------------------------------------------------------
CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `email` VARCHAR(120) NOT NULL,
  `mobile` VARCHAR(20) DEFAULT NULL,
  `password_hash` VARCHAR(256) NOT NULL,
  `role` ENUM('passenger', 'driver', 'admin', 'depot_operator') NOT NULL DEFAULT 'passenger',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `preferred_language` VARCHAR(10) NOT NULL DEFAULT 'en',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_username` (`username`),
  UNIQUE KEY `ix_users_email` (`email`),
  UNIQUE KEY `mobile` (`mobile`),
  KEY `ix_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 2: stops (Transit Stops & Landmarks with GPS Coordinates)
-- Supports English and Marathi (name_mr) stop names
-- ----------------------------------------------------------------------------
CREATE TABLE `stops` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `stop_code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `name_mr` VARCHAR(128) DEFAULT NULL,
  `landmark` VARCHAR(256) DEFAULT NULL,
  `latitude` FLOAT NOT NULL,
  `longitude` FLOAT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_stops_stop_code` (`stop_code`),
  KEY `ix_stops_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 3: routes (Transit Lines & Routes)
-- City and intercity routes with source, destination, distance, and duration
-- ----------------------------------------------------------------------------
CREATE TABLE `routes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `route_number` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `name_mr` VARCHAR(128) DEFAULT NULL,
  `source` VARCHAR(128) NOT NULL,
  `destination` VARCHAR(128) NOT NULL,
  `total_distance_km` FLOAT DEFAULT 0.0,
  `estimated_duration_min` INT DEFAULT 45,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_routes_route_number` (`route_number`),
  KEY `ix_routes_source` (`source`),
  KEY `ix_routes_destination` (`destination`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 4: route_stops (Sequential Stops along each Route)
-- Enforces sequence ordering and unique stop placement
-- ----------------------------------------------------------------------------
CREATE TABLE `route_stops` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `route_id` INT NOT NULL,
  `stop_id` INT NOT NULL,
  `sequence_order` INT NOT NULL,
  `distance_from_prev_km` FLOAT DEFAULT 0.0,
  `avg_travel_time_min` INT DEFAULT 5,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_route_sequence` (`route_id`, `sequence_order`),
  UNIQUE KEY `uq_route_stop` (`route_id`, `stop_id`),
  KEY `ix_route_stops_route_id` (`route_id`),
  KEY `ix_route_stops_stop_id` (`stop_id`),
  CONSTRAINT `route_stops_ibfk_1` FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `route_stops_ibfk_2` FOREIGN KEY (`stop_id`) REFERENCES `stops` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 5: route_connectivity (Graph Network Transfer Links between Routes)
-- Enables multi-route transfer and alternative bus algorithms
-- ----------------------------------------------------------------------------
CREATE TABLE `route_connectivity` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `from_route_id` INT NOT NULL,
  `to_route_id` INT NOT NULL,
  `transfer_stop_id` INT NOT NULL,
  `is_connected` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `ix_route_connectivity_from_route_id` (`from_route_id`),
  KEY `ix_route_connectivity_to_route_id` (`to_route_id`),
  KEY `ix_route_connectivity_transfer_stop_id` (`transfer_stop_id`),
  CONSTRAINT `route_connectivity_ibfk_1` FOREIGN KEY (`from_route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `route_connectivity_ibfk_2` FOREIGN KEY (`to_route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `route_connectivity_ibfk_3` FOREIGN KEY (`transfer_stop_id`) REFERENCES `stops` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 6: buses (Vehicle Fleet Registry)
-- Statuses: 'RUNNING', 'DELAYED', 'CANCELLED', 'PUNCTURED', 'BREAKDOWN', 'COMPLETED', 'AVAILABLE', 'DISPATCHED', 'MAINTENANCE'
-- ----------------------------------------------------------------------------
CREATE TABLE `buses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `bus_number` VARCHAR(64) NOT NULL,
  `registration_number` VARCHAR(64) NOT NULL,
  `depot_name` VARCHAR(64) NOT NULL DEFAULT 'Pune Central Depot',
  `capacity` INT NOT NULL DEFAULT 40,
  `current_status` VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
  `assigned_route_id` INT DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_buses_bus_number` (`bus_number`),
  UNIQUE KEY `registration_number` (`registration_number`),
  KEY `assigned_route_id` (`assigned_route_id`),
  KEY `ix_buses_current_status` (`current_status`),
  CONSTRAINT `buses_ibfk_1` FOREIGN KEY (`assigned_route_id`) REFERENCES `routes` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 7: bus_capacity (Vehicle Seated & Standing Capacity Breakdown)
-- ----------------------------------------------------------------------------
CREATE TABLE `bus_capacity` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `bus_id` INT NOT NULL,
  `total_capacity` INT NOT NULL DEFAULT 40,
  `seated_capacity` INT NOT NULL DEFAULT 32,
  `standing_capacity` INT NOT NULL DEFAULT 8,
  PRIMARY KEY (`id`),
  UNIQUE KEY `bus_id` (`bus_id`),
  CONSTRAINT `bus_capacity_ibfk_1` FOREIGN KEY (`bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 8: drivers (Transit Driver Profiles & Assignments)
-- Statuses: 'AVAILABLE', 'ON_TRIP', 'OFF_DUTY', 'LEAVE'
-- ----------------------------------------------------------------------------
CREATE TABLE `drivers` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `driver_code` VARCHAR(64) NOT NULL,
  `full_name` VARCHAR(128) NOT NULL,
  `mobile_number` VARCHAR(20) NOT NULL,
  `license_number` VARCHAR(64) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
  `assigned_bus_id` INT DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  UNIQUE KEY `ix_drivers_driver_code` (`driver_code`),
  UNIQUE KEY `license_number` (`license_number`),
  KEY `assigned_bus_id` (`assigned_bus_id`),
  KEY `ix_drivers_status` (`status`),
  CONSTRAINT `drivers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `drivers_ibfk_2` FOREIGN KEY (`assigned_bus_id`) REFERENCES `buses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 9: trips (Scheduled & Active Bus Trips)
-- Statuses: 'SCHEDULED', 'RUNNING', 'DELAYED', 'PUNCTURED', 'BREAKDOWN', 'COMPLETED', 'CANCELLED', 'DISPATCHED'
-- ----------------------------------------------------------------------------
CREATE TABLE `trips` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `trip_code` VARCHAR(128) NOT NULL,
  `bus_id` INT NOT NULL,
  `driver_id` INT DEFAULT NULL,
  `route_id` INT NOT NULL,
  `scheduled_start_time` DATETIME NOT NULL,
  `actual_start_time` DATETIME DEFAULT NULL,
  `actual_end_time` DATETIME DEFAULT NULL,
  `current_stop_id` INT DEFAULT NULL,
  `next_stop_id` INT DEFAULT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'SCHEDULED',
  `passenger_count` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_trips_trip_code` (`trip_code`),
  KEY `ix_trips_bus_id` (`bus_id`),
  KEY `ix_trips_driver_id` (`driver_id`),
  KEY `ix_trips_route_id` (`route_id`),
  KEY `current_stop_id` (`current_stop_id`),
  KEY `next_stop_id` (`next_stop_id`),
  KEY `ix_trips_status` (`status`),
  CONSTRAINT `trips_ibfk_1` FOREIGN KEY (`bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `trips_ibfk_2` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `trips_ibfk_3` FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `trips_ibfk_4` FOREIGN KEY (`current_stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL,
  CONSTRAINT `trips_ibfk_5` FOREIGN KEY (`next_stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 10: live_gps (Real-Time Vehicle Telemetry & Coordinate Logs)
-- Sources: 'DEVICE', 'DRIVER_APP', 'SIMULATION'
-- ----------------------------------------------------------------------------
CREATE TABLE `live_gps` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `trip_id` INT NOT NULL,
  `bus_id` INT NOT NULL,
  `latitude` FLOAT NOT NULL,
  `longitude` FLOAT NOT NULL,
  `speed_kmh` FLOAT DEFAULT 0.0,
  `source` VARCHAR(32) NOT NULL DEFAULT 'DRIVER_APP',
  `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_live_gps_trip_id` (`trip_id`),
  KEY `ix_live_gps_bus_id` (`bus_id`),
  KEY `ix_live_gps_timestamp` (`timestamp`),
  CONSTRAINT `live_gps_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`id`) ON DELETE CASCADE,
  CONSTRAINT `live_gps_ibfk_2` FOREIGN KEY (`bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 11: passenger_counts (Stop-by-Stop Passenger Boarding & Alighting)
-- ----------------------------------------------------------------------------
CREATE TABLE `passenger_counts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `trip_id` INT NOT NULL,
  `stop_id` INT NOT NULL,
  `boarding_count` INT NOT NULL DEFAULT 0,
  `alighting_count` INT NOT NULL DEFAULT 0,
  `current_passenger_count` INT NOT NULL DEFAULT 0,
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_passenger_counts_trip_id` (`trip_id`),
  KEY `stop_id` (`stop_id`),
  CONSTRAINT `passenger_counts_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`id`) ON DELETE CASCADE,
  CONSTRAINT `passenger_counts_ibfk_2` FOREIGN KEY (`stop_id`) REFERENCES `stops` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 12: historical_delays (Descriptive Statistical Delay Logs)
-- Pure statistical observations (mean, median, P50, P90) - NO AI/ML
-- ----------------------------------------------------------------------------
CREATE TABLE `historical_delays` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `route_id` INT NOT NULL,
  `stop_id` INT NOT NULL,
  `weekday` INT NOT NULL,
  `hour_of_day` INT NOT NULL,
  `delay_minutes` FLOAT NOT NULL,
  `delay_reason` VARCHAR(64) NOT NULL,
  `recorded_date` DATE NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_historical_delays_route_id` (`route_id`),
  KEY `ix_historical_delays_stop_id` (`stop_id`),
  KEY `ix_historical_delays_weekday` (`weekday`),
  KEY `ix_historical_delays_hour_of_day` (`hour_of_day`),
  KEY `ix_historical_delays_recorded_date` (`recorded_date`),
  CONSTRAINT `historical_delays_ibfk_1` FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `historical_delays_ibfk_2` FOREIGN KEY (`stop_id`) REFERENCES `stops` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 13: incidents (Emergency Incident Reports)
-- Types: 'TYRE_PUNCTURE', 'ENGINE_FAILURE', 'ACCIDENT', 'TRAFFIC_JAM', 'ROAD_BLOCK', 'OTHER'
-- Statuses: 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'
-- ----------------------------------------------------------------------------
CREATE TABLE `incidents` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `incident_number` VARCHAR(64) NOT NULL,
  `trip_id` INT NOT NULL,
  `bus_id` INT NOT NULL,
  `route_id` INT NOT NULL,
  `stop_id` INT DEFAULT NULL,
  `incident_type` VARCHAR(64) NOT NULL DEFAULT 'TYRE_PUNCTURE',
  `severity` VARCHAR(16) NOT NULL DEFAULT 'HIGH',
  `description` TEXT,
  `affected_passengers` INT NOT NULL DEFAULT 0,
  `status` VARCHAR(32) NOT NULL DEFAULT 'OPEN',
  `reported_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `resolved_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_incidents_incident_number` (`incident_number`),
  KEY `trip_id` (`trip_id`),
  KEY `bus_id` (`bus_id`),
  KEY `route_id` (`route_id`),
  KEY `stop_id` (`stop_id`),
  KEY `ix_incidents_status` (`status`),
  KEY `ix_incidents_reported_at` (`reported_at`),
  CONSTRAINT `incidents_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`id`) ON DELETE CASCADE,
  CONSTRAINT `incidents_ibfk_2` FOREIGN KEY (`bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `incidents_ibfk_3` FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `incidents_ibfk_4` FOREIGN KEY (`stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 14: alternative_recommendations (Ranked Alternative Bus Options)
-- Computed via greedy algorithm & priority queue for affected passengers
-- ----------------------------------------------------------------------------
CREATE TABLE `alternative_recommendations` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `incident_id` INT NOT NULL,
  `recommended_bus_id` INT NOT NULL,
  `direct_route` TINYINT(1) NOT NULL DEFAULT 1,
  `recommended_stop_id` INT DEFAULT NULL,
  `walking_distance_m` INT DEFAULT 0,
  `eta_minutes` INT NOT NULL,
  `available_seats` INT NOT NULL,
  `historical_delay_min` FLOAT DEFAULT 0.0,
  `rank_order` INT NOT NULL,
  `is_recommended` TINYINT(1) NOT NULL DEFAULT 1,
  `allocated_passengers` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_alternative_recommendations_incident_id` (`incident_id`),
  KEY `recommended_bus_id` (`recommended_bus_id`),
  KEY `recommended_stop_id` (`recommended_stop_id`),
  CONSTRAINT `alternative_recommendations_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incidents` (`id`) ON DELETE CASCADE,
  CONSTRAINT `alternative_recommendations_ibfk_2` FOREIGN KEY (`recommended_bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `alternative_recommendations_ibfk_3` FOREIGN KEY (`recommended_stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 15: depot_requests (Depot Replacement Bus Requests & State Machine)
-- 6-Stage Stepper: PENDING -> ASSIGNED -> DISPATCHED -> ARRIVED -> PASSENGER_TRANSFER -> RESOLVED
-- ----------------------------------------------------------------------------
CREATE TABLE `depot_requests` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `request_code` VARCHAR(64) NOT NULL,
  `incident_id` INT NOT NULL,
  `failed_bus_id` INT NOT NULL,
  `route_id` INT NOT NULL,
  `stop_id` INT DEFAULT NULL,
  `replacement_bus_id` INT DEFAULT NULL,
  `replacement_driver_id` INT DEFAULT NULL,
  `operator_id` INT DEFAULT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  `affected_passengers` INT NOT NULL DEFAULT 0,
  `transferred_passengers` INT NOT NULL DEFAULT 0,
  `priority` VARCHAR(16) NOT NULL DEFAULT 'HIGH',
  `eta_minutes` INT DEFAULT 12,
  `resolution_notes` TEXT,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `assigned_at` DATETIME DEFAULT NULL,
  `dispatched_at` DATETIME DEFAULT NULL,
  `arrived_at` DATETIME DEFAULT NULL,
  `resolved_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `incident_id` (`incident_id`),
  UNIQUE KEY `ix_depot_requests_request_code` (`request_code`),
  KEY `ix_depot_requests_failed_bus_id` (`failed_bus_id`),
  KEY `route_id` (`route_id`),
  KEY `stop_id` (`stop_id`),
  KEY `replacement_bus_id` (`replacement_bus_id`),
  KEY `replacement_driver_id` (`replacement_driver_id`),
  KEY `operator_id` (`operator_id`),
  KEY `ix_depot_requests_status` (`status`),
  KEY `ix_depot_requests_created_at` (`created_at`),
  CONSTRAINT `depot_requests_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incidents` (`id`) ON DELETE CASCADE,
  CONSTRAINT `depot_requests_ibfk_2` FOREIGN KEY (`failed_bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `depot_requests_ibfk_3` FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `depot_requests_ibfk_4` FOREIGN KEY (`stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL,
  CONSTRAINT `depot_requests_ibfk_5` FOREIGN KEY (`replacement_bus_id`) REFERENCES `buses` (`id`) ON DELETE SET NULL,
  CONSTRAINT `depot_requests_ibfk_6` FOREIGN KEY (`replacement_driver_id`) REFERENCES `drivers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `depot_requests_ibfk_7` FOREIGN KEY (`operator_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 16: replacement_buses (Replacement Bus Assignment History)
-- ----------------------------------------------------------------------------
CREATE TABLE `replacement_buses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `depot_request_id` INT NOT NULL,
  `bus_id` INT NOT NULL,
  `driver_id` INT DEFAULT NULL,
  `eta_minutes` INT DEFAULT 12,
  `assigned_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `depot_request_id` (`depot_request_id`),
  KEY `bus_id` (`bus_id`),
  KEY `driver_id` (`driver_id`),
  CONSTRAINT `replacement_buses_ibfk_1` FOREIGN KEY (`depot_request_id`) REFERENCES `depot_requests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `replacement_buses_ibfk_2` FOREIGN KEY (`bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `replacement_buses_ibfk_3` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 17: passenger_transfers (Transfer Audit Trail for Evacuated Buses)
-- ----------------------------------------------------------------------------
CREATE TABLE `passenger_transfers` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `depot_request_id` INT NOT NULL,
  `failed_bus_id` INT NOT NULL,
  `target_bus_id` INT NOT NULL,
  `passengers_transferred` INT NOT NULL,
  `transfer_stop_id` INT DEFAULT NULL,
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `depot_request_id` (`depot_request_id`),
  KEY `failed_bus_id` (`failed_bus_id`),
  KEY `target_bus_id` (`target_bus_id`),
  KEY `transfer_stop_id` (`transfer_stop_id`),
  CONSTRAINT `passenger_transfers_ibfk_1` FOREIGN KEY (`depot_request_id`) REFERENCES `depot_requests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `passenger_transfers_ibfk_2` FOREIGN KEY (`failed_bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `passenger_transfers_ibfk_3` FOREIGN KEY (`target_bus_id`) REFERENCES `buses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `passenger_transfers_ibfk_4` FOREIGN KEY (`transfer_stop_id`) REFERENCES `stops` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 18: notifications (System & Passenger Transit Alerts)
-- Types: 'INCIDENT', 'DELAY', 'REPLACEMENT', 'SYSTEM'
-- ----------------------------------------------------------------------------
CREATE TABLE `notifications` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT DEFAULT NULL,
  `target_role` VARCHAR(32) NOT NULL DEFAULT 'all',
  `title` VARCHAR(128) NOT NULL,
  `message` TEXT NOT NULL,
  `type` VARCHAR(32) NOT NULL DEFAULT 'SYSTEM',
  `priority` VARCHAR(16) DEFAULT 'NORMAL',
  `related_entity_type` VARCHAR(32) DEFAULT NULL,
  `related_entity_id` INT DEFAULT NULL,
  `is_read` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_notifications_user_id` (`user_id`),
  KEY `ix_notifications_target_role` (`target_role`),
  KEY `ix_notifications_is_read` (`is_read`),
  KEY `ix_notifications_created_at` (`created_at`),
  KEY `ix_notifications_related_entity_id` (`related_entity_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- Table 19: audit_logs (Administrative & Security Event Audit Trail)
-- ----------------------------------------------------------------------------
CREATE TABLE `audit_logs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT DEFAULT NULL,
  `action` VARCHAR(64) NOT NULL,
  `entity_type` VARCHAR(64) NOT NULL,
  `entity_id` VARCHAR(64) DEFAULT NULL,
  `details` TEXT,
  `ip_address` VARCHAR(45) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_audit_logs_user_id` (`user_id`),
  KEY `ix_audit_logs_action` (`action`),
  KEY `ix_audit_logs_created_at` (`created_at`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================================
-- 5. BASELINE SEED DATA (Default Accounts & Acceptance Test Scenarios)
-- Password for all seed accounts: Password123!
-- ============================================================================

-- 5.1 Default System Users & Driver Logins (Password for all: Password123!)
INSERT INTO `users` (`id`, `username`, `email`, `mobile`, `password_hash`, `role`, `is_active`, `preferred_language`, `created_at`, `updated_at`) VALUES
(1, 'admin', 'admin@busnotify.com', '9800000001', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'admin', 1, 'en', NOW(), NOW()),
(2, 'depot', 'depot@busnotify.com', '9800000002', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'depot_operator', 1, 'en', NOW(), NOW()),
(3, 'driver', 'driver@busnotify.com', '9800000003', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'mr', NOW(), NOW()),
(4, 'passenger', 'passenger@busnotify.com', '9800000004', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'passenger', 1, 'en', NOW(), NOW()),
(1000, 'drv_1', 'driver_1@busnotify.com', '9876543201', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1001, 'drv_2', 'driver_2@busnotify.com', '9876543202', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1002, 'drv_3', 'driver_3@busnotify.com', '9876543203', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1003, 'drv_4', 'driver_4@busnotify.com', '9876543204', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1004, 'drv_5', 'driver_5@busnotify.com', '9876543205', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1005, 'drv_6', 'driver_6@busnotify.com', '9876543206', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1006, 'drv_7', 'driver_7@busnotify.com', '9876543207', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1007, 'drv_8', 'driver_8@busnotify.com', '9876543208', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1008, 'drv_9', 'driver_9@busnotify.com', '9876543209', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1009, 'drv_10', 'driver_10@busnotify.com', '9876543210', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1010, 'drv_11', 'driver_11@busnotify.com', '9876543211', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1011, 'drv_12', 'driver_12@busnotify.com', '9876543212', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1012, 'drv_13', 'driver_13@busnotify.com', '9876543213', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1013, 'drv_14', 'driver_14@busnotify.com', '9876543214', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1014, 'drv_15', 'driver_15@busnotify.com', '9876543215', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1015, 'drv_16', 'driver_16@busnotify.com', '9876543216', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1016, 'drv_17', 'driver_17@busnotify.com', '9876543217', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1017, 'drv_18', 'driver_18@busnotify.com', '9876543218', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1018, 'drv_19', 'driver_19@busnotify.com', '9876543219', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1019, 'drv_20', 'driver_20@busnotify.com', '9876543220', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1020, 'drv_21', 'driver_21@busnotify.com', '9876543221', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1021, 'drv_22', 'driver_22@busnotify.com', '9876543222', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1022, 'drv_23', 'driver_23@busnotify.com', '9876543223', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1023, 'drv_24', 'driver_24@busnotify.com', '9876543224', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW()),
(1024, 'drv_25', 'driver_25@busnotify.com', '9876543225', 'scrypt:32768:8:1$DlYtG4ToYn8jkaC7$d6d76901599508703b025a01e0541c586d1e24e604a03a717d2b07da94d93b405e7f039ddcea547bc9068537ae16cfdc041906bffda88f1a0d145f2b4914db0a', 'driver', 1, 'en', NOW(), NOW());

-- 5.2 Core Pune Transit Stops
INSERT INTO `stops` (`id`, `stop_code`, `name`, `name_mr`, `landmark`, `latitude`, `longitude`, `created_at`) VALUES
(1, 'STP-PUN', 'Pune Station', 'पुणे स्टेशन', 'Railway Station Main Gate', 18.5284, 73.8744, NOW()),
(2, 'STP-RUB', 'Ruby Hall', 'रुबी हॉल', 'Ruby Hall Clinic', 18.5325, 73.8812, NOW()),
(3, 'STP-BND', 'Bund Garden', 'बंड गार्डन', 'Yerawada Bridge', 18.5368, 73.8865, NOW()),
(4, 'STP-KOR', 'Koregaon Park', 'कोरेगाव पार्क', 'North Main Road', 18.5362, 73.8940, NOW()),
(5, 'STP-KAL', 'Kalyani Nagar', 'कल्याणी नगर', 'Bishops School', 18.5463, 73.9034, NOW()),
(6, 'STP-MAG', 'Magarpatta', 'मगरपट्टा', 'Cybercity Main Gate', 18.5134, 73.9242, NOW()),
(7, 'STP-HAD', 'Hadapsar', 'हडपसर', 'Gadital Bus Stand', 18.5089, 73.9260, NOW()),
(8, 'STP-SWA', 'Swargate', 'स्वारगेट', 'Swargate ST Stand', 18.5018, 73.8586, NOW()),
(9, 'STP-KAT', 'Katraj', 'कात्रज', 'Katraj Snake Park', 18.4575, 73.8677, NOW()),
(10, 'STP-SHI', 'Shivajinagar', 'शिवाजीनगर', 'Shimla Office', 18.5314, 73.8446, NOW());

-- 5.3 Core Routes
INSERT INTO `routes` (`id`, `route_number`, `name`, `name_mr`, `source`, `destination`, `total_distance_km`, `estimated_duration_min`, `is_active`, `created_at`) VALUES
(1, '123', 'Pune Station to Hadapsar', 'पुणे स्टेशन ते हडपसर', 'Pune Station', 'Hadapsar', 11.2, 45, 1, NOW()),
(2, '156', 'Hadapsar to Swargate', 'हडपसर ते स्वारगेट', 'Hadapsar', 'Swargate', 8.5, 35, 1, NOW()),
(3, '178', 'Swargate to Katraj', 'स्वारगेट ते कात्रज', 'Swargate', 'Katraj', 7.1, 28, 1, NOW()),
(4, 'PUNE_MUM', '123 - Pune to Mumbai', 'पुणे ते मुंबई', 'Pune Station', 'Mumbai CST', 152.0, 210, 1, NOW());

-- 5.4 Route Stops Mapping (Route 123)
INSERT INTO `route_stops` (`route_id`, `stop_id`, `sequence_order`, `distance_from_prev_km`, `avg_travel_time_min`) VALUES
(1, 1, 1, 0.0, 0),
(1, 2, 2, 1.2, 5),
(1, 3, 3, 1.5, 6),
(1, 4, 4, 1.8, 7),
(1, 5, 5, 2.1, 8),
(1, 6, 6, 2.6, 10),
(1, 7, 7, 2.0, 9);

-- 5.5 Core Buses
INSERT INTO `buses` (`id`, `bus_number`, `registration_number`, `depot_name`, `capacity`, `current_status`, `assigned_route_id`, `is_active`, `created_at`) VALUES
(1, '123', 'MH-12-RN-1234', 'Pune Central Depot', 40, 'RUNNING', 1, 1, NOW()),
(2, '156', 'MH-12-RN-5678', 'Pune Central Depot', 40, 'RUNNING', 2, 1, NOW()),
(3, '178', 'MH-12-RN-9012', 'Pune Central Depot', 40, 'RUNNING', 3, 1, NOW()),
(4, '189', 'MH-12-RN-3456', 'Pune Central Depot', 40, 'AVAILABLE', NULL, 1, NOW()),
(5, 'SHIVNERI_101', 'MH-12-SN-1001', 'Pune Central Depot', 45, 'RUNNING', 4, 1, NOW());

-- 5.6 Bus Capacities
INSERT INTO `bus_capacity` (`bus_id`, `total_capacity`, `seated_capacity`, `standing_capacity`) VALUES
(1, 40, 32, 8),
(2, 40, 32, 8),
(3, 40, 32, 8),
(4, 40, 32, 8),
(5, 45, 37, 8);

-- 5.7 Drivers (Assigned & Available Drivers)
INSERT INTO `drivers` (`id`, `user_id`, `driver_code`, `full_name`, `mobile_number`, `license_number`, `status`, `assigned_bus_id`) VALUES
(1, 3, 'D104', 'Rajesh Patil', '9876543210', 'MH-12-2018-0004321', 'ON_TRIP', 1),
(2, 1000, 'DRV-0001', 'Driver 1', '9876543201', 'MH1220260001', 'AVAILABLE', NULL),
(3, 1001, 'DRV-0002', 'Driver 2', '9876543202', 'MH1220260002', 'AVAILABLE', NULL),
(4, 1002, 'DRV-0003', 'Driver 3', '9876543203', 'MH1220260003', 'AVAILABLE', NULL),
(5, 1003, 'DRV-0004', 'Driver 4', '9876543204', 'MH1220260004', 'AVAILABLE', NULL),
(6, 1004, 'DRV-0005', 'Driver 5', '9876543205', 'MH1220260005', 'AVAILABLE', NULL),
(7, 1005, 'DRV-0006', 'Driver 6', '9876543206', 'MH1220260006', 'AVAILABLE', NULL),
(8, 1006, 'DRV-0007', 'Driver 7', '9876543207', 'MH1220260007', 'AVAILABLE', NULL),
(9, 1007, 'DRV-0008', 'Driver 8', '9876543208', 'MH1220260008', 'AVAILABLE', NULL),
(10, 1008, 'DRV-0009', 'Driver 9', '9876543209', 'MH1220260009', 'AVAILABLE', NULL),
(11, 1009, 'DRV-0010', 'Driver 10', '9876543210', 'MH1220260010', 'AVAILABLE', NULL),
(12, 1010, 'DRV-0011', 'Driver 11', '9876543211', 'MH1220260011', 'AVAILABLE', NULL),
(13, 1011, 'DRV-0012', 'Driver 12', '9876543212', 'MH1220260012', 'AVAILABLE', NULL),
(14, 1012, 'DRV-0013', 'Driver 13', '9876543213', 'MH1220260013', 'AVAILABLE', NULL),
(15, 1013, 'DRV-0014', 'Driver 14', '9876543214', 'MH1220260014', 'AVAILABLE', NULL),
(16, 1014, 'DRV-0015', 'Driver 15', '9876543215', 'MH1220260015', 'AVAILABLE', NULL),
(17, 1015, 'DRV-0016', 'Driver 16', '9876543216', 'MH1220260016', 'AVAILABLE', NULL),
(18, 1016, 'DRV-0017', 'Driver 17', '9876543217', 'MH1220260017', 'AVAILABLE', NULL),
(19, 1017, 'DRV-0018', 'Driver 18', '9876543218', 'MH1220260018', 'AVAILABLE', NULL),
(20, 1018, 'DRV-0019', 'Driver 19', '9876543219', 'MH1220260019', 'AVAILABLE', NULL),
(21, 1019, 'DRV-0020', 'Driver 20', '9876543220', 'MH1220260020', 'AVAILABLE', NULL),
(22, 1020, 'DRV-0021', 'Sachin Pramod Kale', '9876543221', 'MH1220177687', 'AVAILABLE', NULL),
(23, 1021, 'DRV-0022', 'Pravin Sagar Nalawade', '9876543222', 'MH1220123895', 'AVAILABLE', NULL),
(24, 1022, 'DRV-0023', 'Ravindra Sanjay Sawant', '9876543223', 'MH1220125509', 'AVAILABLE', NULL),
(25, 1023, 'DRV-0024', 'Harish Rajendra Salunkhe', '9876543224', 'MH1420131291', 'AVAILABLE', NULL),
(26, 1024, 'DRV-0025', 'Deepak Prakash Chavan', '9876543225', 'MH1220091664', 'AVAILABLE', NULL);

-- 5.8 Baseline Active Trip (Bus 123 on Route 123)
INSERT INTO `trips` (`id`, `trip_code`, `bus_id`, `driver_id`, `route_id`, `scheduled_start_time`, `actual_start_time`, `current_stop_id`, `next_stop_id`, `status`, `passenger_count`, `created_at`) VALUES
(1, 'TRIP-123-01', 1, 1, 1, NOW(), NOW(), 6, 7, 'RUNNING', 38, NOW());

-- 5.9 Initial Live GPS for Bus 123 at Magarpatta
INSERT INTO `live_gps` (`trip_id`, `bus_id`, `latitude`, `longitude`, `speed_kmh`, `source`, `timestamp`) VALUES
(1, 1, 18.5134, 73.9242, 22.5, 'DRIVER_APP', NOW());

-- 5.10 Historical Delays Sample (Descriptive Statistics)
INSERT INTO `historical_delays` (`route_id`, `stop_id`, `weekday`, `hour_of_day`, `delay_minutes`, `delay_reason`, `recorded_date`, `created_at`) VALUES
(1, 6, 0, 17, 14.0, 'TRAFFIC', CURDATE() - INTERVAL 7 DAY, NOW()),
(1, 6, 1, 17, 13.5, 'TYRE_PUNCTURE', CURDATE() - INTERVAL 6 DAY, NOW()),
(1, 6, 2, 17, 15.0, 'TRAFFIC', CURDATE() - INTERVAL 5 DAY, NOW()),
(1, 6, 3, 17, 14.0, 'PASSENGER_SURGE', CURDATE() - INTERVAL 4 DAY, NOW()),
(1, 6, 4, 17, 14.5, 'TRAFFIC', CURDATE() - INTERVAL 3 DAY, NOW()),
(1, 6, 5, 17, 13.0, 'TRAFFIC', CURDATE() - INTERVAL 2 DAY, NOW()),
(1, 6, 6, 17, 12.5, 'TRAFFIC', CURDATE() - INTERVAL 1 DAY, NOW()),
(1, 7, 0, 18, 15.0, 'TRAFFIC', CURDATE() - INTERVAL 7 DAY, NOW()),
(1, 7, 1, 18, 16.0, 'TRAFFIC', CURDATE() - INTERVAL 6 DAY, NOW()),
(1, 7, 2, 18, 14.0, 'TRAFFIC', CURDATE() - INTERVAL 5 DAY, NOW());

-- Re-enable Foreign Key Checks
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- Verification Notice:
-- Database 'busnotify' schema successfully created with all 19 relational tables,
-- foreign keys, cascade rules, composite indexes, and demo credentials.
-- ============================================================================
