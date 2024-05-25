import gradio as gr
from chatbot.guiderobi import GPTAgent
import autogen
from autogen.agentchat import Agent, UserProxyAgent

# Open the file in read mode
with open('ExModel.py', 'r', encoding="utf8") as file:
    # Read the content of the file
    code = file.read()

config_list = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
    filter_dict={
        "model": {
            "gpt-4",
            "gpt4",
            "gpt-4-32k",
            "gpt-4-32k-0314",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-3.5-turbo-0301",
            "chatgpt-35-turbo-0301",
            "gpt-35-turbo-v0301",
            "gpt-3.5-turbo-0125"
        }
    }
)


# Define the function to handle interaction with the chatbot
def chat_with_bot(user_input):
    # Initialize the chatbot
    agent = GPTAgent(
        name="Demo",
        source_code=code,
        debug_times=1,
        example_qa="",
        llm_config={
            "seed": 42,
            "config_list": config_list,
        }
    )

    user = UserProxyAgent(
        "user", max_consecutive_auto_reply=0,
        human_input_mode="NEVER", code_execution_config=False
    )

    # Get the chatbot's response
    response = user.initiate_chat(agent, message=user_input).chat_history[-1]['content']

    # Return the chatbot's response
    return response


# Custom CSS for styling the Gradio interface
custom_css = """
.gradio-container {
    border-radius: 10px;
    border: 1px solid #ccc;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    background-color: white;
    padding: 20px;
}

.gr-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 10px 20px;
    font-size: 16px;
    border-radius: 5px;
    cursor: pointer;
}

.gr-button:hover {
    background-color: #45a049;
}

textarea {
    border: 1px solid #ccc !important;
    border-radius: 5px !important;
    padding: 10px !important;
    font-size: 16px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
"""

iface = gr.Interface(
    fn=chat_with_bot,
    inputs=gr.Textbox(lines=7, placeholder="Type your message here...", label="User Input"),
    outputs=gr.Textbox(lines=10, label="Chatbot Response"),
    title="Chatbot cho bài toán Phân phối sản phẩm",
    description="Vui lòng đưa ra câu hỏi hoặc nhập lệnh để tương tác với chatbot.",
)

# Launch the interface
iface.launch(share=True)
