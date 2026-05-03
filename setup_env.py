"""
Helper script to create .env file from template
"""
import os
from pathlib import Path

ENV_TEMPLATE = """# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# RAG Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
TOP_K_RESULTS=3
TEMPERATURE=0.0

# Model Configuration
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Data Configuration
DATA_DIR=knowledge_data
INDEX_FILE=faiss_index.pkl

# Logging
LOG_LEVEL=INFO
"""

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_path = Path(".env")
    
    if env_path.exists():
        print("⚠️  .env file already exists. Skipping creation.")
        print(f"   Location: {env_path.absolute()}")
        return
    
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE)
        print("✅ Created .env file successfully!")
        print(f"   Location: {env_path.absolute()}")
        print("\n📝 Next steps:")
        print("   1. Edit .env file and add your OPENAI_API_KEY")
        print("   2. Add your documents to knowledge_data/ directory")
        print("   3. Run: python ingest.py")
    except Exception as e:
        print(f"❌ Error creating .env file: {str(e)}")


def create_data_dir():
    """Create knowledge_data directory if it doesn't exist"""
    data_dir = Path("knowledge_data")
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
        print("✅ Created knowledge_data/ directory")
        print("   Add your documents (PDF, DOCX, TXT, MD) here")
    else:
        print("✅ knowledge_data/ directory already exists")


if __name__ == "__main__":
    print("🚀 Setting up RAG AI Assistant...\n")
    create_env_file()
    print()
    create_data_dir()
    print("\n✨ Setup complete!")
