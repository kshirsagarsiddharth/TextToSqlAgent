import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import anthropic
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text, exc as sqlalchemy_exc, create_engine
from anthropic import AnthropicError


logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent

PROMPT_DIR = BASE_DIR.parent / "prompt_generation"

SYSTEM_PROMPT_PATH = PROMPT_DIR / "system_prompt.md"
USER_PROMPT_PATH = PROMPT_DIR / "user_prompt.md"
TABLE_METADATA_PATH = PROMPT_DIR / "table_metadata.md"
DATABASE_SCHEMA_PATH = PROMPT_DIR / "database_schema.md"


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"

MAX_TOKENS = 4096
TEMPERATURE = 0.3


DATABASE_URL = os.getenv("DATABASE_URL")


SQL_QUERY_PATTERN = re.compile(
    r"<sql_query>(.*?)</sql_query>", re.DOTALL | re.IGNORECASE
)

EXPLANATION_PATTERN = re.compile(
    r"<explanation>(.*?)</explanation>", re.DOTALL | re.IGNORECASE
)


def load_text_file(path: Path) -> Optional[str]:
    """Loads text content from a file.

    Args:
        path: The Path object pointing to the file.

    Returns:
        The content of the file as a string, or None if an error occurs.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Prompt file not found: {path}")
    except IOError as e:
        logging.error(f"Error reading file {path}: {e}")
    return None


def prepare_prompts() -> Tuple[Optional[str], Optional[str]]:
    """Loads and prepares the system and user prompts."""
    system_prompt_template = load_text_file(SYSTEM_PROMPT_PATH)
    user_prompt_template = load_text_file(USER_PROMPT_PATH)
    table_metadata = load_text_file(TABLE_METADATA_PATH)
    database_schema = load_text_file(DATABASE_SCHEMA_PATH)

    if not all(
        [system_prompt_template, user_prompt_template, table_metadata, database_schema]
    ):
        logging.error("One or more prompt/schema files failed to load.")
        return None, None

    system_prompt = system_prompt_template.replace(r"{{TABLE_SCHEMA}}", database_schema)
    system_prompt = system_prompt.replace(r"{{UNIQUE_VALUES}}", table_metadata)

    return system_prompt, user_prompt_template


def prompt_anthropic(
    client: anthropic.Anthropic,
    question: str,
    system_prompt: str,
    user_prompt_template: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = MAX_TOKENS,
    temperature: float = TEMPERATURE,
) -> Optional[Dict[str, str]]:
    """
    Sends a prompt to the Anthropic API and extracts SQL query and explanation.

    Args:
        client: Initialized Anthropic client.
        question: The user's natural language question.
        system_prompt: The prepared system prompt.
        user_prompt_template: The user prompt template with "{{USER_QUERY}}" placeholder.
        model: The Anthropic model to use.
        max_tokens: The maximum number of tokens to generate.
        temperature: The sampling temperature.

    Returns:
        A dictionary containing the raw text, extracted SQL query, and explanation,
        or None if an error occurs or parsing fails.
    """

    try:
        user_content = user_prompt_template.replace("{{USER_QUERY}}", question)
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": [{"type": "text", "text": user_content}]}
            ],
        )

        raw_text = message.content[0].text
        logging.debug(f"Anthropic raw response: \n{raw_text}")

        sql_match = SQL_QUERY_PATTERN.search(raw_text)
        explanation_match = EXPLANATION_PATTERN.search(raw_text)

        if not sql_match:
            logging.warning("Could not extract SL query from the response.")
        if not explanation_match:
            logging.warning("Could not extract explanation from the response.")

        sql_query = sql_match.group(1).strip()
        explanation = explanation_match.group(1).strip()
        logging.info("Successfully extracted SQL query and explanation.")

        return {"text": raw_text, "sql_query": sql_query, "explanation": explanation}
    except AnthropicError as e:
        logging.error(f"Anthropic API error: {e}")

    except Exception as e:
        logging.error(f"An unexpected error occurred during Anthropic interaction: {e}")

    return None


def create_db_engine():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            pass
        logging.info("Database engine created and connection tested successfully.")
        return engine
    except sqlalchemy_exc.SQLAlchemyError as e:
        logging.error(f"Failed to create database engine or connect: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during engine creation: {e}")
        return None


def execute_sql_query(sql_query: str, engine) -> Optional[pd.DataFrame]:
    """
    Executes a SQL query against the database and returns results as a DataFrame.

    Args:
        sql_query: The SQL query string to execute.
        engine: SQLAlchemy engine instance.

    Returns:
        A pandas DataFrame containing the query results, or None if an error occurs.
    """
    logging.info(f"Executing SQL query: \n{sql_query}")

    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            if result:
                rows = result.fetchall()
                df = pd.DataFrame(rows)
                logging.info(f"Query executed successfully. Fetched {len(df)} rows.")
                return df
    except sqlalchemy_exc.SQLAlchemyError as e:
        logging.error(f"Database error executing query: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during database execution: {e}")

    return None
