import openai

client = openai.OpenAI(
	api_key="sk-0OLqBSROrwCARioTQq02Ww",
	base_url="http://127.0.0.1:4000"
)

import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.chat.completions.create(
    model="deepseek",
    messages=[
    {
        "role": "user",
        "content": "hello"
    },
    {
        "role": "assistant",
        "content": "<think>\n\n</think>\n\nHello! How can I assist you today? 😊"
    },
    {
        "role": "user",
        "content": "今天天气怎么样"
    },
    {
        "role": "assistant",
        "content": "<think>\n\n</think>\n\n您好！请问您想了解哪个地区的天气情况？"
    }
]
)

print(response)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.chat.completions.create(
#     model="deepseek",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "Your prompt here"
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{base64_file}"  # or data:application/pdf;base64,{base64_file}
#                     }
#                 }
#             ]
#         }
#     ]
# )
# print(response_with_file)
