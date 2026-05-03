# Redis Setup Guide

## Overview

The RAG AI Decision Assistant now supports Redis for session storage, providing:
- Persistent session storage across server restarts
- Better scalability for multiple server instances
- Automatic session expiration (24 hours TTL)
- Fallback to in-memory storage if Redis is unavailable

## Installation

### Option 1: Local Redis (Development)

**Windows:**
1. Download Redis from: https://github.com/microsoftarchive/redis/releases
2. Or use WSL: `wsl sudo apt-get install redis-server`
3. Or use Docker: `docker run -d -p 6379:6379 redis:alpine`

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server
```

### Option 2: Docker (Recommended)

```bash
# Run Redis in Docker
docker run -d \
  --name redis-rag-assistant \
  -p 6379:6379 \
  redis:7-alpine

# Or use docker-compose (see docker-compose.yml)
```

### Option 3: Cloud Redis (Production)

- **Redis Cloud**: https://redis.com/cloud/
- **AWS ElastiCache**: https://aws.amazon.com/elasticache/
- **Azure Cache for Redis**: https://azure.microsoft.com/services/cache/
- **Google Cloud Memorystore**: https://cloud.google.com/memorystore

## Configuration

Add Redis settings to your `.env` file:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=          # Optional, leave empty if no password
REDIS_SSL=false          # Set to true for cloud Redis with SSL
```

### Example Configurations

**Local Redis (default):**
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

**Redis Cloud:**
```bash
REDIS_HOST=your-redis-cloud-host.redis.cloud
REDIS_PORT=12345
REDIS_PASSWORD=your_password_here
REDIS_SSL=true
```

**Docker Redis:**
```bash
REDIS_HOST=redis  # Use service name in docker-compose
REDIS_PORT=6379
```

## Verification

### Check Redis Connection

```bash
# Test Redis connection
python -c "from app import get_redis_client; client = get_redis_client(); print('Connected!' if client else 'Using fallback')"
```

### Health Check

```bash
curl http://localhost:8000/health
```

Response will show Redis status:
```json
{
  "status": "healthy",
  "message": "System is operational. Knowledge base loaded. Redis: connected",
  "timestamp": "..."
}
```

## Fallback Behavior

If Redis is unavailable, the system automatically falls back to in-memory storage:
- No errors or crashes
- Sessions work but are lost on server restart
- Health check shows "using fallback" status
- Logs show warning messages

## Session Management

### Session TTL

Sessions expire after 24 hours (86400 seconds) automatically.

### Session Structure

```json
{
  "created_at": "2024-01-13T20:00:00",
  "updated_at": "2024-01-13T20:05:00",
  "messages": [
    {
      "question": "Your question",
      "answer": "AI answer",
      "timestamp": "2024-01-13T20:05:00"
    }
  ]
}
```

## Troubleshooting

### Redis Connection Failed

**Check if Redis is running:**
```bash
# Linux/Mac
redis-cli ping
# Should return: PONG

# Docker
docker ps | grep redis
```

**Check connection settings:**
- Verify `REDIS_HOST` and `REDIS_PORT` in `.env`
- Check firewall rules
- Verify password if required

**Common Issues:**

1. **Connection refused:**
   - Redis not running
   - Wrong port number
   - Firewall blocking connection

2. **Authentication failed:**
   - Wrong password
   - Password required but not set

3. **Timeout:**
   - Network issues
   - Redis overloaded
   - Wrong host address

### Using Fallback Storage

If Redis fails, the system uses in-memory storage:
- ✅ No errors
- ✅ System continues working
- ⚠️ Sessions lost on restart
- ⚠️ Not shared across multiple instances

## Production Recommendations

1. **Use Redis Cloud or managed service** for reliability
2. **Enable SSL** for secure connections
3. **Set strong passwords**
4. **Monitor Redis memory usage**
5. **Configure Redis persistence** (RDB or AOF)
6. **Set up Redis replication** for high availability
7. **Monitor connection pool** size

## Docker Compose Integration

Update `docker-compose.yml` to include Redis:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: rag_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  api:
    # ... existing config ...
    depends_on:
      - redis
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379

volumes:
  redis_data:
```

## Performance

- **Session read/write**: < 1ms typically
- **Concurrent sessions**: Supports thousands
- **Memory usage**: ~1KB per session
- **TTL**: Automatic cleanup after 24 hours

## Security

- Use strong passwords
- Enable SSL for remote connections
- Restrict network access (firewall)
- Use Redis ACLs for fine-grained access control
- Regularly update Redis version
