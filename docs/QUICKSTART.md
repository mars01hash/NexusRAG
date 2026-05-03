# Quick Start Guide

Get your RAG AI Decision Assistant running in 5 minutes!

## Step 1: Setup Environment

```bash
# Run setup script
python setup_env.py

# Or manually create .env file and add:
OPENAI_API_KEY=your_key_here
```

## Step 2: Add Knowledge Base

```bash
# Create directory (if not exists)
mkdir knowledge_data

# Add your documents (PDF, DOCX, TXT, MD)
# Copy files to knowledge_data/ directory
```

## Step 3: Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

## Step 4: Ingest Knowledge Base

```bash
# This creates the FAISS index
python ingest.py
```

Wait for: `✅ Knowledge base ingested and indexed successfully`

## Step 5: Start the Service

**Option A: FastAPI only**
```bash
python app.py
# Visit http://localhost:8000
```

## Step 6: Test It!

**API Test:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is volleyball?"}'
```

## Troubleshooting

**"Index file not found"**
→ Run `python ingest.py` again

**"OPENAI_API_KEY not set"**
→ Check your `.env` file

**"No documents found"**
→ Add files to `knowledge_data/` directory

**Import errors**
→ Make sure you activated virtual environment and installed requirements

## Next Steps

- Read [README.md](README.md) for full documentation
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Customize settings in `.env` file

Happy querying! 🏐
