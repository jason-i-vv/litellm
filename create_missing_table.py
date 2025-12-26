#!/usr/bin/env python3
"""手动创建缺失的数据库表"""
import asyncio
import sys
import os

# 设置数据库连接
os.environ['DATABASE_URL'] = 'postgresql://llmproxy:dbpassword9090@10.202.40.29:5433/litellm?sslmode=disable&connect_timeout=10'

async def create_missing_table():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    try:
        # 创建 LiteLLM_ManagedVectorStoreIndexTable 表
        sql = """
        CREATE TABLE IF NOT EXISTS "LiteLLM_ManagedVectorStoreIndexTable" (
            "id" TEXT NOT NULL PRIMARY KEY,
            "index_name" TEXT NOT NULL UNIQUE,
            "litellm_params" JSONB NOT NULL,
            "index_info" JSONB,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "created_by" TEXT,
            "updated_at" TIMESTAMP(3) NOT NULL,
            "updated_by" TEXT
        );
        """

        print("正在创建表 LiteLLM_ManagedVectorStoreIndexTable...")
        await db.execute_raw(sql)
        print("✅ 表创建成功!")

        # 验证表是否创建成功
        result = await db.query_raw("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'LiteLLM_ManagedVectorStoreIndexTable';
        """)

        if result:
            print(f"✅ 验证成功: 表 LiteLLM_ManagedVectorStoreIndexTable 已存在于数据库中")
        else:
            print("❌ 验证失败: 表未能创建")

    except Exception as e:
        print(f"❌ 创建表时出错: {e}")
        sys.exit(1)
    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(create_missing_table())
