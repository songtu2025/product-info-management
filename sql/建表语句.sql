
CREATE TABLE amazon_store_site (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '技术主键',

    store_site VARCHAR(50) NOT NULL COMMENT '店铺/站点',
    store VARCHAR(50) NULL COMMENT '店铺',
    country VARCHAR(10) NULL COMMENT '国家',
    domain VARCHAR(50) NULL COMMENT '域名',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_store_site (store_site),
    KEY idx_store (store),
    KEY idx_country (country)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon店铺站点表';


### 5.2 创建 `amazon_product_info`


CREATE TABLE amazon_product_info (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '技术主键',

    asin VARCHAR(20) NULL COMMENT 'Asin',
    msku VARCHAR(100) NOT NULL COMMENT 'MSKU',
    store_site VARCHAR(50) NOT NULL COMMENT '店铺/站点',
    parent_asin VARCHAR(20) NULL COMMENT '父Asin',
    product_name VARCHAR(100) NULL COMMENT '产品名称',
    sku VARCHAR(100) NULL COMMENT 'SKU',
    brand VARCHAR(50) NULL COMMENT '品牌',
    fnsku VARCHAR(30) NULL COMMENT 'FNSKU',
    sales_status VARCHAR(20) NULL COMMENT '销售状态',
    storage_type VARCHAR(50) NULL COMMENT '仓储类型',
    category_level_1 VARCHAR(100) NULL COMMENT '一级品类',
    category_a VARCHAR(50) NULL COMMENT '品类A',
    category_b VARCHAR(100) NULL COMMENT '品类B',
    listing VARCHAR(100) NULL COMMENT 'Listing',
    label_name TEXT NULL COMMENT '标签名',
    msku_shipping_remark TEXT NULL COMMENT 'MSKU发货备注',
    transfer_remark VARCHAR(500) NULL COMMENT '借调备注',
    msku_lock_status VARCHAR(10) NULL COMMENT '锁仓MSKU',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_store_site_msku (store_site, msku),
    KEY idx_asin (asin),
    KEY idx_sku (sku),
    KEY idx_fnsku (fnsku),
    KEY idx_listing (listing)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon产品信息表';


### 5.3 创建 `amazon_listing_owner_config`


CREATE TABLE amazon_listing_owner_config (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '技术主键',

    store_site VARCHAR(50) NOT NULL COMMENT '店铺/站点',
    listing VARCHAR(100) NOT NULL COMMENT 'Listing',
    owner VARCHAR(50) NULL COMMENT '负责人',
    listing_status VARCHAR(50) NULL COMMENT 'Listing状态',
    listing_maintainer VARCHAR(50) NULL COMMENT 'Listing维护人',
    include_inventory_age_assessment VARCHAR(10) NULL COMMENT '是否纳入库龄考核',
    project_group VARCHAR(50) NULL COMMENT '项目组',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_store_site_listing (store_site, listing),
    KEY idx_owner (owner),
    KEY idx_listing_status (listing_status)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon Listing负责人配置表';


### 5.4 创建 `amazon_operation_log`


CREATE TABLE amazon_operation_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '技术主键',

    table_name VARCHAR(64) NOT NULL COMMENT '业务表名',
    record_id BIGINT UNSIGNED NOT NULL COMMENT '业务记录ID',
    operation_type VARCHAR(20) NOT NULL COMMENT '操作类型',
    changed_by VARCHAR(64) NOT NULL DEFAULT 'system' COMMENT '操作人',
    change_data JSON NOT NULL COMMENT '修改前后值',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (id),
    KEY idx_table_record (table_name, record_id),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon后台操作日志表';


### 5.5 创建 `amazon_admin_user`


CREATE TABLE amazon_admin_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '技术主键',

    username VARCHAR(64) NOT NULL COMMENT '登录账号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role VARCHAR(20) NOT NULL COMMENT '角色：admin 或 viewer',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username),
    KEY idx_role (role)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon后台登录用户表';


### 5.6 创建 `amazon_user_preference`


CREATE TABLE amazon_user_preference (
    username VARCHAR(64) NOT NULL COMMENT '登录账号',
    preference_key VARCHAR(128) NOT NULL COMMENT '偏好键',
    preference_value TEXT NOT NULL COMMENT '偏好值 JSON',

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (username, preference_key)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Amazon后台用户偏好表';
