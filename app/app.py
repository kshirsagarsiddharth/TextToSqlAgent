import streamlit as st
import anthropic
from dotenv import load_dotenv
import logging
import os
import pandas as pd

from utils import prepare_prompts, prompt_anthropic, execute_sql_query, create_db_engine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
import time

load_dotenv()


@st.cache_resource(ttl=3600)
def get_anthropic_client():
    """Initializes and caches the Anthropic client."""
    client = anthropic.Anthropic()
    return client


@st.cache_resource(ttl=3600)
def get_database_engine():
    """Initializes and caches the SQLAlchemy database engine."""
    engine = create_db_engine()
    return engine


@st.cache_data(ttl=3600)
def load_prompt_cached():
    system_prompt, user_prompt_template = prepare_prompts()
    return system_prompt, user_prompt_template


client = get_anthropic_client()
engine = get_database_engine()
system_prompt, user_prompt_template = load_prompt_cached()


# st.set_page_config(page_title="Chat with Your Database", layout="centered", initial_sidebar_state="collapsed")
st.title("Chat with Intelli Catalog")
st.caption("Ask questions about your data in natural language.")

AVATAR_PATH = r"C:\Work\TextToSqlAgent\app\avatar_assistant.jpg"
USER = r"C:\Work\TextToSqlAgent\app\user.png"

with st.sidebar: 

    st.image(r'https://cdn.prod.website-files.com/65ba231f3fc718d503140556/65ba231f3fc718d5031405ca_footer-logo.webp', clamp=True)

    st.divider()

    if st.button("Reset Chat"):
        st.session_state.messages = [] 
        st.success('Chat History Cleared')
        time.sleep(1) 
        st.caption('App Info')



if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if "dataframe" in message and isinstance(message["dataframe"], pd.DataFrame):
            st.dataframe(
                message["dataframe"], use_container_width=True, hide_index=True
            )

if prompt := st.chat_input("Ask about your data...", ): 
    st.session_state.messages.append({"role":"user", "content": prompt})

    with st.chat_message("user", avatar=USER): 
        st.markdown(prompt)
    
    with st.chat_message("assistant", avatar=AVATAR_PATH): 
        status = st.status("Assistant is Thinking...", expanded=False)
        assistant_response_content = "" 
        assistant_dataframe = None 

        try: 
            status.update(label='Generating SQL query...', state='running', expanded=False)
            llm_response = prompt_anthropic(
                client=client, 
                question=prompt, 
                system_prompt=system_prompt, 
                user_prompt_template=user_prompt_template
            )

            sql_query = llm_response.get('sql_query') 
            explanation = llm_response.get('explanation')

            exp_md = f"**Explanation:**\n{explanation}\n"
            st.markdown(exp_md)
            assistant_response_content += exp_md + "\n" 

            if sql_query: 
                status.update(label="Executing SQL query...", state='running', expanded=False)
                data_frame = execute_sql_query(sql_query, engine) 
                st.dataframe(data_frame, use_container_width=True, hide_index=True)
            status.update(label="Processing complete!", state='complete', expanded=False)
            msg = f"Query executed successfully. Found {len(data_frame)} rows:"
            st.markdown(msg)
            time.sleep(0.5)
            status.empty()
        except Exception as e: 
            error_msg = f"An unexpected error occurred: {e}"
            st.error(error_msg)
        
        assistant_message = {'role':'assistant','content': assistant_response_content} 
        assistant_message['dataframe'] = assistant_dataframe 
        st.session_state.messages.append(assistant_message)

st.divider()
st.caption('App Authored by Siddharth Kshirsagar')
