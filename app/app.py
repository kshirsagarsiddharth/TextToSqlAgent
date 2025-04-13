
from utils import return_engine, prepare_prompts , prompt_anthropic, execute_sql_query
import anthropic 
engine = return_engine() 
client = anthropic.Anthropic()

system_prompt, user_prompt_template = prepare_prompts()

user_question = "Give me all parts of FIG - 22 of VXI."

llm_response = prompt_anthropic(
    client = client, 
    question=user_question, 
    system_prompt=system_prompt, 
    user_prompt_template=user_prompt_template
)


sql_query = llm_response['sql_query'] 
explanation = llm_response['explanation']

data_frame = execute_sql_query(sql_query)

print(data_frame)