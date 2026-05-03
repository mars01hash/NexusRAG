# Deployment Guide

## Prerequisites

- Python 3.11+ or Docker
- OpenAI API key
- Knowledge base documents (PDF, DOCX, TXT, MD)

## Local Development Setup

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd Rag_AI_Assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
# OpenAI API Configuration
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
```

### 3. Prepare Knowledge Base

```bash
# Create knowledge_data directory
mkdir knowledge_data

# Add your documents (PDF, DOCX, TXT, MD files)
# Supports both Russian and English documents
cp your_documents/* knowledge_data/
```

### 4. Ingest Knowledge Base

```bash
# Run ingestion to create vector index
python ingest.py
```

This will:
- Load all documents from `knowledge_data/`
- Chunk the text
- Create embeddings using OpenAI
- Save FAISS index to `faiss_index.pkl`

### 5. Start Services

**Option A: FastAPI only**
```bash
python app.py
# Or
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Docker Deployment

### 1. Build and Run with Docker Compose

```bash
# Create .env file (see above)

# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 2. Manual Docker Build

```bash
# Build image
docker build -t rag-ai-assistant .

# Run API
docker run -d \
  --name rag-api \
  -p 8000:8000 \
  -v $(pwd)/knowledge_data:/app/knowledge_data \
  -v $(pwd)/faiss_index.pkl:/app/faiss_index.pkl \
  --env-file .env \
  rag-ai-assistant

```

## Cloud Deployment

### VPS Deployment (Ubuntu/Debian)

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Install dependencies
sudo apt update
sudo apt install -y python3.11 python3-pip git

# Clone repository
git clone <your-repo-url>
cd Rag_AI_Assistant

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env file
nano .env  # Add your API keys

# Prepare knowledge base
mkdir knowledge_data
# Upload your documents to knowledge_data/

# Ingest knowledge base
python ingest.py

# Run with systemd (create service file)
sudo nano /etc/systemd/system/rag-api.service
```

**Systemd service file** (`/etc/systemd/system/rag-api.service`):
```ini
[Unit]
Description=RAG AI Assistant API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/Rag_AI_Assistant
Environment="PATH=/path/to/Rag_AI_Assistant/venv/bin"
ExecStart=/path/to/Rag_AI_Assistant/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable rag-api
sudo systemctl start rag-api
sudo systemctl status rag-api
```

### Using PM2 (Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start API
pm2 start app.py --name rag-api --interpreter python3

# Save PM2 configuration
pm2 save
pm2 startup
```

## Production Considerations

1. **Security**
   - Use environment variables for all secrets
   - Enable HTTPS (use nginx reverse proxy)
   - Restrict CORS origins in `app.py`
   - Use firewall rules

2. **Performance**
   - Use Redis for session storage (replace in-memory)
   - Add caching layer
   - Consider using GPU for FAISS (faiss-gpu)

3. **Monitoring**
   - Add logging to file
   - Set up health check monitoring
   - Monitor API response times

4. **Scaling**
   - Use load balancer for multiple API instances
   - Consider using managed vector database (Pinecone, Weaviate)

## Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Test question endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is volleyball?"}'
```

## Troubleshooting

### Index file not found
```bash
# Re-run ingestion
python ingest.py
```

### OpenAI API errors
- Check API key is correct
- Verify API quota/limits
- Check network connectivity

### Memory issues
- Reduce `CHUNK_SIZE` and `TOP_K_RESULTS`
- Use smaller embedding model
- Consider using FAISS-GPU for faster processing
