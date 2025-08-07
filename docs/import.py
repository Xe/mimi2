import os
import subprocess
import glob
import re
from openai import OpenAI
from dotenv import load_dotenv
import lancedb

from .schema import Docs

load_dotenv()

def clone_or_update_repo(repo_url, local_path):
    """
    Clones a repository if it doesn't exist locally, or pulls the latest changes if it does.
    """
    # Ensure the parent directory exists
    parent_dir = os.path.dirname(local_path)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    if os.path.exists(local_path):
        print(f"Repository found at {local_path}. Pulling latest changes...")
        try:
            # Use a list of arguments for subprocess.run for better security and handling of spaces
            subprocess.run(["git", "pull"], cwd=local_path, check=True, capture_output=True, text=True)
            print("Pull successful.")
        except subprocess.CalledProcessError as e:
            print(f"Error pulling repository: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
    else:
        print(f"Cloning repository from {repo_url} into {local_path}...")
        try:
            # Use a list of arguments for subprocess.run
            subprocess.run(["git", "clone", repo_url, local_path], check=True, capture_output=True, text=True)
            print("Clone successful.")
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")


def split_markdown_sections(text):
    """
    Split markdown text into sections by headings.
    Each section starts with a markdown heading (#).
    """
    pattern = r'(?m)(?=^#{1,6}\s)'
    return [sec.strip() for sec in re.split(pattern, text) if sec.strip()]


def index_markdown_files(db_path, embed_model):
    """
    Index all .md and .mdx files in var/lancedb table using Ollama embeddings.
    """
    load_dotenv()
    client = OpenAI(
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434") + "/v1",
        api_key=os.getenv("OPENAI_API_KEY", "ollama"),
    )
    db = lancedb.connect(db_path)
    table_name = "docs"
    
    table = db.create_table(table_name, schema=Docs, mode="overwrite")
    
    # collect records
    records = []
    for ext in ("md", "mdx"):
        for filepath in glob.glob(f"**/*.{ext}", recursive=True):
            # Omit files under './var/anubis/docs'
            # Remove './var/anubis/docs' from the file path for the table
            table_filepath = filepath
            for prefix in ("var/anubis/docs/", "./var/anubis/docs/"):
                if table_filepath.startswith(prefix):
                    table_filepath = table_filepath[len(prefix):]
                    break
            print(f"record count: {len(records)}")
            if len(records) >= 50:
                table.add(records)
                records = []
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            sections = split_markdown_sections(content)
            for idx, sec in enumerate(sections):
                # Skip sections that only contain a heading (e.g., '# Heading')
                lines = [line.strip() for line in sec.splitlines() if line.strip()]
                if len(lines) == 1 and re.match(r'^#{1,6}\s', lines[0]):
                    continue
                resp = client.embeddings.create(model=embed_model, input=sec)
                emb = resp.data[0].embedding  # type: ignore
                records.append({
                    "file_path": table_filepath,
                    "section": idx,
                    "text": sec,
                    "embedding": emb,
                })
    if not records:
        print("No markdown files found to index.")
        return
    # create table with proper vector schema if not exists
    # write records
    table.add(records)
    print(f"Indexed {len(records)} sections into '{table_name}' table.")

def main():
    """Main function to run the repo update."""
    repo_url = "https://github.com/TecharoHQ/anubis"
    # Assumes the script is run from the root of the mimi2 project
    local_path = os.path.join("var", "anubis")
    clone_or_update_repo(repo_url, local_path)
    # Index markdown files into lancedb
    db_path = os.path.join("var", "lancedb")
    index_markdown_files(db_path, embed_model="snowflake-arctic-embed2:latest")


if __name__ == "__main__":
    main()
