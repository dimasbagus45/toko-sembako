CREATE DATABASE IF NOT EXISTS sembako_nusa
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE sembako_nusa;

CREATE TABLE IF NOT EXISTS products (
  id VARCHAR(100) NOT NULL,
  name VARCHAR(70) NOT NULL,
  category VARCHAR(40) NOT NULL,
  unit VARCHAR(25) NOT NULL,
  price BIGINT UNSIGNED NOT NULL,
  stock BIGINT UNSIGNED NOT NULL DEFAULT 0,
  icon VARCHAR(32) NULL,
  color CHAR(7) NULL,
  tag VARCHAR(24) NOT NULL DEFAULT '',
  photo MEDIUMTEXT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS settings (
  `key` VARCHAR(80) NOT NULL,
  value VARCHAR(255) NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
  id VARCHAR(100) NOT NULL,
  created_at VARCHAR(40) NOT NULL,
  status VARCHAR(60) NOT NULL,
  whatsapp VARCHAR(15) NOT NULL,
  total BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  KEY idx_orders_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_items (
  order_id VARCHAR(100) NOT NULL,
  product_id VARCHAR(100) NOT NULL,
  name VARCHAR(255) NOT NULL,
  unit VARCHAR(100) NOT NULL,
  price BIGINT UNSIGNED NOT NULL,
  quantity BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (order_id, product_id),
  CONSTRAINT fk_order_items_order
    FOREIGN KEY (order_id) REFERENCES orders (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS accounts (
  username VARCHAR(30) NOT NULL,
  password_salt CHAR(32) NOT NULL,
  password_hash CHAR(64) NOT NULL,
  role VARCHAR(16) NOT NULL DEFAULT 'admin',
  PRIMARY KEY (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_meta (
  `key` VARCHAR(100) NOT NULL,
  value VARCHAR(255) NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
