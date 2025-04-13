from dotenv import load_dotenv
import os 
import anthropic
import re 
from sqlalchemy import text , create_engine

import pandas as pd 

load_dotenv()
db_string = os.getenv('DATABASE_URL')


client = anthropic.Anthropic()


engine = create_engine(db_string)



system_prompt_path = "../prompt_generation/system_prompt.md"
user_prompt_path = "../prompt_generation/user_prompt.md" 
table_metadata_path = "../prompt_generation/table_metadata.md" 
database_schema_path= "../prompt_generation/database_schema.md"


def load_prompt(path):
    with open(path,'r') as f: 
        prompt = f.read() 
    return prompt  


system_prompt = load_prompt(system_prompt_path)
user_prompt = load_prompt(user_prompt_path)
table_metadata = load_prompt(table_metadata_path)
database_schema = load_prompt(database_schema_path)

SYSTEM_PROMPT = system_prompt.replace(r"{{TABLE_SCHEMA}}", database_schema).replace(
    r"{{UNIQUE_VALUES}}", table_metadata
)



def prompt_anthropic(question, system_prompt, user_prompt):
    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=20000,
        temperature=0.2,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt.replace("{{USER_QUERY}}", question),
                    }
                ],
            }
        ],
    )
    text = message.content[0].text
    sql_query = re.search("<sql_query>(.*)</sql_query>", text, re.DOTALL).group(1)
    explanation = re.search("<explanation>(.*)</explanation>", text, re.DOTALL).group(1)

    return {"text": text, "sql_query": sql_query, "explanation": explanation}

def extract_data(sql_query, engine): 
    with engine.connect() as connection: 
        result = connection.execute(text(sql_query))
        rows = result.fetchall() 
    return pd.DataFrame(rows)


if __name__ == "__main__": 

    question_answer = prompt_anthropic(
        question= "Give me all parts of FIG - 22 of VXI.",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    extract_data(question_answer['sql_query'], engine=engine)
