import os
from litellm import Router

# 设置环境变量 - 禁用 Anthropic URL 后缀自动添加
# os.environ["LITELLM_ANTHROPIC_DISABLE_URL_SUFFIX"] = "true"
# os.environ['LITELLM_LOG'] = 'DEBUG'

# import litellm
#
# litellm._turn_on_debug()

# 定义路由配置
model_list = [
    {
        "model_name": "anyrouter",
        "litellm_params": {
            "model": "anthropic/glm-4.6",
            "api_base": "https://open.bigmodel.cn/api/anthropic",
            "timeout": 10,
            "stream_timeout": 0.01,
            "max_retries": 5,
            "extra_headers": {
                "Authorization": "Bearer 4a795e3c00534209be668f2c875589be.BYWPk4PeUBrLPTIh"
            }
        }
    }
]

# 创建路由器实例
router = Router(
    model_list=model_list,
    routing_strategy="latency-based-routing",  # 基于延迟的路由策略
    num_retries=3,  # 重试次数
    timeout=10,  # 总超时时间
    fallbacks=[],  # 失败时的备用方案
)

# 测试消息
messages = [{"role": "user", "content": "Hey! how's it going?"}]

print("=" * 60)
print("Testing LiteLLM Router with Anthropic API")
print("=" * 60)
print(f"Model: anyrouter (anthropic/glm-4.6)")
print(f"Number of endpoints: {len(model_list)}")
print(f"Routing strategy: latency-based-routing")
print("=" * 60)
print()

try:
    # 发起请求
    response = router.completion(
        model="anyrouter",
        messages=messages
    )

    print("✓ Request successful!")
    print()
    print("Response:")
    print("-" * 60)
    print(response)
    print("-" * 60)
    print()

    # 打印响应详情
    if hasattr(response, 'choices') and len(response.choices) > 0:
        print("Response content:")
        print(response.choices[0].message.content)
        print()

    # 打印使用的 API base
    if hasattr(response, '_hidden_params'):
        api_base_used = response._hidden_params.get('api_base', 'Unknown')
        print(f"API base used: {api_base_used}")
        print()

except Exception as e:
    print("✗ Request failed!")
    print()
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print()
    import traceback
    print("Full traceback:")
    print(traceback.format_exc())
