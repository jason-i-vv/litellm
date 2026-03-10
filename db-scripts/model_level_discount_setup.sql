-- ============================================================================
-- Model 级别折扣功能 - 数据库设置脚本
-- ============================================================================

-- 这个脚本提供了设置和管理 model 级别折扣的 SQL 语句

-- ----------------------------------------------------------------------------
-- 1. 设置 Model 折扣
-- ----------------------------------------------------------------------------

-- 示例 1：为单个 Model 设置折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{
    "discount": 0.20,
    "description": "20% discount for Claude Sonnet 4.5"
}'
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- 示例 2：为多个 Model 设置相同折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.20}'
WHERE model_name IN (
    'claude-sonnet-4-5-20250929',
    'claude-opus-4-20250514'
);

-- 示例 3：为特定前缀的 Model 设置折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.20}'
WHERE model_name LIKE 'claude-%';

-- 示例 4：为所有 Anthropic 模型设置折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.20}'
WHERE model_name LIKE 'claude-%';

-- 示例 5：为所有 Gemini 模型设置折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.50}'
WHERE model_name LIKE 'gemini-%';

-- 示例 6：为所有 OpenAI 模型设置折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.10}'
WHERE model_name LIKE 'gpt-%';

-- ----------------------------------------------------------------------------
-- 2. 查询折扣配置
-- ----------------------------------------------------------------------------

-- 查询所有设置了折扣的 Model
SELECT
    model_id,
    model_name,
    model_info->>'discount' as discount_percent,
    model_info->>'description' as description,
    created_at,
    updated_at
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL
ORDER BY model_name;

-- 查询特定 Model 的折扣配置
SELECT
    model_id,
    model_name,
    model_info->>'discount' as discount_percent,
    model_info
FROM "LiteLLM_ProxyModelTable"
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- ----------------------------------------------------------------------------
-- 3. 清除折扣
-- ----------------------------------------------------------------------------

-- 清除单个 Model 的折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = model_info - 'discount'
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- 清除所有 Model 的折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = model_info - 'discount'
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL;

-- 完全清空 model_info
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = NULL
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- ----------------------------------------------------------------------------
-- 4. 性能优化 - 添加索引
-- ----------------------------------------------------------------------------

-- 为 model_name 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_proxy_model_table_model_name
ON "LiteLLM_ProxyModelTable"(model_name);

-- 为 model_info 添加 GIN 索引（如果使用 JSONB）
CREATE INDEX IF NOT EXISTS idx_proxy_model_table_model_info
ON "LiteLLM_ProxyModelTable" USING GIN (model_info);

-- ----------------------------------------------------------------------------
-- 5. 批量操作示例
-- ----------------------------------------------------------------------------

-- 批量设置不同 Model 的不同折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = CASE
    WHEN model_name = 'claude-sonnet-4-5-20250929' THEN '{"discount": 0.20}'
    WHEN model_name = 'claude-opus-4-20250514' THEN '{"discount": 0.10}'
    WHEN model_name = 'gemini-2.0-flash-exp' THEN '{"discount": 0.50}'
    WHEN model_name = 'gpt-4' THEN '{"discount": 0.15}'
    ELSE model_info
END
WHERE model_name IN (
    'claude-sonnet-4-5-20250929',
    'claude-opus-4-20250514',
    'gemini-2.0-flash-exp',
    'gpt-4'
);

-- ----------------------------------------------------------------------------
-- 6. 统计和报告
-- ----------------------------------------------------------------------------

-- 统计设置了折扣的 Model 数量
SELECT
    COUNT(*) as total_models_with_discount
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL;

-- 按折扣分组统计
SELECT
    model_info->>'discount' as discount_percent,
    COUNT(*) as model_count,
    array_agg(model_name) as models
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL
GROUP BY model_info->>'discount'
ORDER BY model_info->>'discount';

-- ----------------------------------------------------------------------------
-- 7. 验证和测试
-- ----------------------------------------------------------------------------

-- 验证折扣值是否在有效范围内（0.0 - 1.0）
SELECT
    model_name,
    model_info->>'discount' as discount_percent,
    CASE
        WHEN (model_info->>'discount')::float < 0 OR (model_info->>'discount')::float > 1 THEN 'INVALID'
        ELSE 'VALID'
    END as validation_status
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 8. 实用查询
-- ----------------------------------------------------------------------------

-- 查找没有设置折扣的 Model
SELECT
    model_id,
    model_name,
    created_at
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NULL
   OR model_info->>'discount' IS NULL
ORDER BY model_name;

-- 查找折扣高于 50% 的 Model
SELECT
    model_name,
    model_info->>'discount' as discount_percent
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND (model_info->>'discount')::float > 0.5
ORDER BY (model_info->>'discount')::float DESC;

-- ----------------------------------------------------------------------------
-- 9. 维护操作
-- ----------------------------------------------------------------------------

-- 删除无效的折扣配置
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = model_info - 'discount'
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL
  AND (
    (model_info->>'discount')::float < 0
    OR (model_info->>'discount')::float > 1
  );

-- ----------------------------------------------------------------------------
-- 10. 备份和恢复
-- ----------------------------------------------------------------------------

-- 备份当前所有折扣配置
CREATE TABLE IF NOT EXISTS model_discount_backup AS
SELECT
    model_id,
    model_name,
    model_info->>'discount' as discount,
    model_info,
    NOW() as backup_time
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL;

-- 从备份恢复折扣配置（如果需要）
-- UPDATE "LiteLLM_ProxyModelTable"
-- SET model_info = jsonb_build_object('discount', discount)
-- FROM model_discount_backup
-- WHERE "LiteLLM_ProxyModelTable".model_id = model_discount_backup.model_id;
