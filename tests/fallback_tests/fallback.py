"""
测试从 vLLM 模型 fallback 到 Anthropic 模型
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("../.."))

import litellm
from litellm import Router


@pytest.mark.asyncio
async def test_vllm_to_anthropic_fallback_async():
    """
    测试从 vLLM 模型异步 fallback 到 Anthropic 模型

    测试场景:
    - 主模型: hosted_vllm (使用错误的 API key,会失败)
    - Fallback 模型: Anthropic Claude
    """
    model_list = [
        {
            "model_name": "my-vllm-model",
            "litellm_params": {
                "model": "hosted_vllm/llama-3.1-8b-instruct",
                "api_key": "bad-vllm-key",  # 故意使用错误的 key
                "api_base": "http://0.0.0.0:8000",  # 假设的 vLLM 服务地址
            },
            "tpm": 240000,
            "rpm": 1800,
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "anthropic/claude-3-5-haiku-20241022",
                "api_base": "https://anyrouter.top",
                "timeout": 10,
                "stream_timeout": 0.01,
                "max_retries": 5,
                "extra_headers": {
                    "Authorization": "Bearer sk-wU1Us0b94erBgOsHCtqersHQEWEjRPgb5uJa09FUBJF2RD5A"
                }
            }
        }
    ]

    router = Router(
        model_list=model_list,
        fallbacks=[{"my-vllm-model": ["claude-fallback"]}],
        set_verbose=True,
        num_retries=0,  # 不重试,直接 fallback
    )

    messages = [{"role": "user", "content": "你好,请介绍一下自己"}]

    try:
        response = await router.acompletion(
            model="my-vllm-model",
            messages=messages,
        )

        print(f"Response: {response}")
        print(f"Model used: {response.model}")

        # 验证确实使用了 fallback 模型
        assert response is not None
        assert "claude" in response.model.lower()
        print("✓ 测试通过: vLLM 失败后成功 fallback 到 Anthropic")

    except Exception as e:
        pytest.fail(f"Fallback 测试失败: {e}")
    finally:
        router.reset()


def test_vllm_to_anthropic_fallback_sync():
    """
    测试从 vLLM 模型同步 fallback 到 Anthropic 模型

    测试场景:
    - 主模型: hosted_vllm (使用错误的 API key,会失败)
    - Fallback 模型: Anthropic Claude
    """
    model_list = [
        {
            "model_name": "my-vllm-model",
            "litellm_params": {
                "model": "hosted_vllm/llama-3.1-8b-instruct",
                "api_key": "bad-vllm-key",  # 故意使用错误的 key
                "api_base": "http://0.0.0.0:8000",  # 假设的 vLLM 服务地址
            },
            "tpm": 240000,
            "rpm": 1800,
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "claude-3-5-haiku-20241022",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            },
            "tpm": 1000000,
            "rpm": 9000,
        },
    ]

    litellm.set_verbose = True
    router = Router(
        model_list=model_list,
        fallbacks=[{"my-vllm-model": ["claude-fallback"]}],
        set_verbose=True,
        num_retries=0,  # 不重试,直接 fallback
    )

    messages = [{"role": "user", "content": "你好,请介绍一下自己"}]

    try:
        response = router.completion(
            model="my-vllm-model",
            messages=messages,
        )

        print(f"Response: {response}")
        print(f"Model used: {response.model}")

        # 验证确实使用了 fallback 模型
        assert response is not None
        assert "claude" in response.model.lower()
        print("✓ 测试通过: vLLM 失败后成功 fallback 到 Anthropic")

    except Exception as e:
        pytest.fail(f"Fallback 测试失败: {e}")
    finally:
        router.reset()


@pytest.mark.asyncio
async def test_vllm_to_anthropic_streaming_fallback():
    """
    测试从 vLLM 模型流式 fallback 到 Anthropic 模型

    测试场景:
    - 主模型: hosted_vllm (使用错误的 API 地址,会失败)
    - Fallback 模型: Anthropic Claude (流式响应)
    """
    model_list = [
        {
            "model_name": "my-vllm-model",
            "litellm_params": {
                "model": "hosted_vllm/llama-3.1-8b-instruct",
                "api_key": "any-key",
                "api_base": "http://invalid-vllm-endpoint.local:8000",  # 无效的地址
            },
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "claude-3-5-haiku-20241022",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            },
        },
    ]

    router = Router(
        model_list=model_list,
        fallbacks=[{"my-vllm-model": ["claude-fallback"]}],
        set_verbose=False,
        num_retries=0,
    )

    messages = [{"role": "user", "content": "写一首关于天空的短诗"}]

    try:
        response = await router.acompletion(
            model="my-vllm-model",
            messages=messages,
            stream=True,
        )

        chunks = []
        async for chunk in response:
            print(chunk)
            chunks.append(chunk)

        # 验证收到了流式响应
        assert len(chunks) > 0
        print(f"✓ 测试通过: 收到 {len(chunks)} 个流式响应块")

    except Exception as e:
        pytest.fail(f"流式 Fallback 测试失败: {e}")
    finally:
        router.reset()


@pytest.mark.parametrize("sync_mode", [True, False])
@pytest.mark.asyncio
async def test_vllm_to_anthropic_fallback_with_mock(sync_mode):
    """
    使用 mock 测试 vLLM 到 Anthropic 的 fallback (不需要实际的 API keys)

    测试场景:
    - 主模型: hosted_vllm (mock 失败)
    - Fallback 模型: Anthropic Claude (mock 成功)
    """
    model_list = [
        {
            "model_name": "my-vllm-model",
            "litellm_params": {
                "model": "hosted_vllm/llama-3.1-8b-instruct",
                "api_key": "bad-key",
                "api_base": "http://0.0.0.0:8000",
            },
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "claude-3-5-haiku-20241022",
                "api_key": os.getenv("ANTHROPIC_API_KEY", "mock-key"),
                "mock_response": "你好!我是 Claude,一个由 Anthropic 开发的 AI 助手。",
            },
        },
    ]

    router = Router(
        model_list=model_list,
        fallbacks=[{"my-vllm-model": ["claude-fallback"]}],
        set_verbose=False,
        num_retries=0,
    )

    messages = [{"role": "user", "content": "你好"}]

    try:
        if sync_mode:
            response = router.completion(
                model="my-vllm-model",
                messages=messages,
            )
        else:
            response = await router.acompletion(
                model="my-vllm-model",
                messages=messages,
            )

        print(f"Response: {response}")
        assert response is not None
        assert response.choices[0].message.content is not None
        print(f"✓ 测试通过 ({'同步' if sync_mode else '异步'}模式)")

    except Exception as e:
        pytest.fail(f"Mock Fallback 测试失败 ({'同步' if sync_mode else '异步'}模式): {e}")
    finally:
        router.reset()


if __name__ == "__main__":
    import asyncio

    print("运行同步测试...")
    test_vllm_to_anthropic_fallback_sync()

    print("\n运行异步测试...")
    asyncio.run(test_vllm_to_anthropic_fallback_async())

    print("\n运行流式测试...")
    asyncio.run(test_vllm_to_anthropic_streaming_fallback())

    print("\n运行 Mock 测试...")
    asyncio.run(test_vllm_to_anthropic_fallback_with_mock(sync_mode=True))
    asyncio.run(test_vllm_to_anthropic_fallback_with_mock(sync_mode=False))

    print("\n所有测试完成!")
