-- ============================================================================
-- AI Finance 数据库初始化
-- 容器首次启动时由 docker-entrypoint-initdb.d 自动执行
-- ============================================================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 收票相关表（示例，可按需扩展）
-- CREATE TABLE IF NOT EXISTS receiving.invoices (
--     id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     invoice_no  VARCHAR(64)  NOT NULL,
--     amount      NUMERIC(18,2) NOT NULL,
--     created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
-- );

-- 稽核相关表（示例）
-- CREATE TABLE IF NOT EXISTS auditing.audit_cases (
--     id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     invoice_id  UUID NOT NULL,
--     status      VARCHAR(32) NOT NULL DEFAULT 'pending',
--     created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
-- );
