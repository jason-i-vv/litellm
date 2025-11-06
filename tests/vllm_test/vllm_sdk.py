import litellm

litellm._turn_on_debug()

response = litellm.completion(
            model="hosted_vllm//data/models/DeepSeek-R1-Distill-Llama-8B", # pass the vllm model name
            messages=[
                        {
                            "role": "user",
                            "content": "what llm are you"
                        }
                    ],
            api_base="http://10.16.201.2:8000/v1",
            temperature=0.2,
            max_tokens=80)

print(response)