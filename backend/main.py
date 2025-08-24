import os
import json
import logging
import traceback
import requests
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Setup basic logging (fallback if structlog fails)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to setup structured logging, fallback to basic if it fails
try:
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger()
except ImportError:
    logger.warning("structlog not available, using basic logging")
    pass

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_KEY = os.getenv("API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Add this debugging block
print("=== ENVIRONMENT DEBUG ===")
print(f"ENVIRONMENT: '{ENVIRONMENT}'")
print(f"ENVIRONMENT == 'development': {ENVIRONMENT == 'development'}")
print(f"API_KEY: {API_KEY}")
print(f"ALLOWED_ORIGINS: {ALLOWED_ORIGINS}")
print("========================")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")
if not API_KEY and ENVIRONMENT == "production":
    raise ValueError("API_KEY environment variable is required for production")

app = FastAPI(
    title="AI Repo Generator",
    description="Professional AI-powered GitHub repository generator",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Add OPTIONS explicitly
    allow_headers=["*"],
)

# Try to setup rate limiter, skip if slowapi not available
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    RATE_LIMITING_ENABLED = True
except ImportError:
    logger.warning("slowapi not available, rate limiting disabled")
    RATE_LIMITING_ENABLED = False
    
    # Dummy limiter for when slowapi is not available
    class DummyLimiter:
        def limit(self, rate):
            def decorator(func):
                return func
            return decorator
    
    limiter = DummyLimiter()
    
    def get_remote_address(request):
        return request.client.host if request.client else "unknown"




# Input validation with length limits
class RepoRequest(BaseModel):
    prompt: str = Field(
        ..., 
        min_length=5, 
        max_length=500,
        description="Project description (5-500 characters)"
    )

# API Key authentication middleware


@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    print(f"=== MIDDLEWARE DEBUG ===")
    print(f"Method: {request.method}")
    print(f"Path: {request.url.path}")
    print(f"Environment: '{ENVIRONMENT}'")
    print(f"Should skip: {request.url.path == '/' or request.method == 'OPTIONS' or ENVIRONMENT == 'development'}")
    print("========================")
    
    # Skip auth for root endpoint, OPTIONS requests, and in development
    if (request.url.path == "/" or 
        request.method == "OPTIONS" or
        ENVIRONMENT == "development"):
        response = await call_next(request)
        return response
    
    # Check API key for all other endpoints
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != API_KEY:
        logger.warning("unauthorized_access_attempt", 
                      client_ip=get_remote_address(request), 
                      path=request.url.path,
                      method=request.method)
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"}
        )
    
    response = await call_next(request)
    return response




def extract_json_from_response(text):
    """Extract JSON from model response, handling various formats"""
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith('```json'):
        text = text.replace('```json', '').replace('```', '')
    elif text.startswith('```'):
        text = text.replace('```', '')
    
    # Try to find JSON block - more robust regex
    import re
    json_match = re.search(r'\{.*\}', text, re.DOTALL | re.MULTILINE)
    if json_match:
        json_str = json_match.group().strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, trying to fix common issues")
            # Try to fix common JSON issues
            json_str = json_str.replace('\n', '\\n').replace('\t', '\\t')
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    # Try direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    return None

def query_groq_complete(prompt, model="llama-3.1-8b-instant", temperature=0.1, max_tokens=8000):
    """Query Groq API without streaming for better JSON handling"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False  # Disable streaming for cleaner JSON
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    return response.json()

def query_groq_stream(prompt, model="llama-3.1-8b-instant", temperature=0.1, max_tokens=8000):
    """Query Groq API with streaming - collect full response then parse"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True
    }
    
    response = requests.post(url, headers=headers, json=payload, stream=True, timeout=30)
    response.raise_for_status()
    
    full_content = ""
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                if line.strip() == 'data: [DONE]':
                    break
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    if 'choices' in data and len(data['choices']) > 0:
                        delta = data['choices'][0].get('delta', {})
                        if 'content' in delta:
                            full_content += delta['content']
                except json.JSONDecodeError:
                    continue
    
    return full_content

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "message": "AI Repo Generator is live! 🚀",
        "version": "1.0.0",
        "environment": ENVIRONMENT
    }

@app.post("/generate_repo/")
@limiter.limit("5/minute")  # Rate limiting
async def generate_repo(request: Request, data: RepoRequest):
    user_prompt = data.prompt.strip()
    client_ip = get_remote_address(request)

    logger.info("repo_generation_started", 
                prompt_length=len(user_prompt),
                client_ip=client_ip)

    # Improved prompt with better JSON formatting instructions
    system_prompt = f"""You are a senior software engineer creating a professional GitHub repository. Respond with ONLY valid JSON - no explanations, no markdown, no other text.

Generate a complete GitHub repository for: "{user_prompt}"

Requirements:
- Repository name: under 20 characters, kebab-case, creative
- Description: under 100 characters
- README: comprehensive but concise, use \\n for line breaks

Respond with this EXACT JSON structure:
{{
  "repository_name": "short-kebab-name",
  "description": "Brief professional description",
  "readme_content": "# Project Title 🚀\\n\\nBrief description of what this project does and why it's useful.\\n\\n## ✨ Features\\n\\n- Feature 1\\n- Feature 2\\n- Feature 3\\n\\n## 🛠️ Tech Stack\\n\\n- Frontend: React.js\\n- Backend: Node.js\\n- Database: MongoDB\\n\\n## 🚀 Quick Start\\n\\n```bash\\ngit clone https://github.com/username/repo-name.git\\ncd repo-name\\nnpm install\\nnpm start\\n```\\n\\n## 📝 Usage\\n\\n```javascript\\n// Example usage\\nconsole.log('Hello World!');\\n```\\n\\n## 🤝 Contributing\\n\\nContributions are welcome! Please feel free to submit a Pull Request.\\n\\n## 📄 License\\n\\nMIT License - see LICENSE file for details."
}}

RESPOND ONLY WITH VALID JSON. NO OTHER TEXT."""

    def event_stream():
        try:
            # Send progress update
            yield f"data: {{\"status\": \"generating\", \"message\": \"🤖 Generating repository...\"}}\n\n"
            
            # Use non-streaming for better JSON reliability
            try:
                response = query_groq_complete(system_prompt, temperature=0.1, max_tokens=8000)
                full_response = response['choices'][0]['message']['content']
            except:
                # Fallback to streaming if complete fails
                logger.info("Falling back to streaming API")
                yield f"data: {{\"status\": \"generating\", \"message\": \"📝 Processing response...\"}}\n\n"
                full_response = query_groq_stream(system_prompt, temperature=0.1, max_tokens=8000)
            
            logger.info("repo_generation_completed", 
                       response_length=len(full_response),
                       client_ip=client_ip,
                       prompt_preview=user_prompt[:50])
            
            # Extract and validate JSON
            parsed_json = extract_json_from_response(full_response)
            
            if parsed_json and all(key in parsed_json for key in ["repository_name", "description", "readme_content"]):
                logger.info("json_parsing_successful",
                           repo_name=parsed_json.get("repository_name"),
                           client_ip=client_ip)
                
                # Validate and clean the data
                clean_data = {
                    "repository_name": str(parsed_json.get("repository_name", "")).strip()[:50],
                    "description": str(parsed_json.get("description", "")).strip()[:200],
                    "readme_content": str(parsed_json.get("readme_content", "")).strip()
                }
                
                yield f"event: done\ndata: {json.dumps(clean_data, ensure_ascii=False)}\n\n"
            else:
                logger.error("json_parsing_failed", 
                           response_preview=full_response[:500],
                           client_ip=client_ip)
                
                # Create a fallback response
                fallback_response = {
                    "repository_name": "ai-generated-project",
                    "description": "AI-generated project based on user requirements",
                    "readme_content": f"# AI Generated Project 🚀\\n\\nThis project was generated based on: {user_prompt}\\n\\n## Features\\n\\n- AI-powered functionality\\n- Modern tech stack\\n- Easy to customize\\n\\n## Getting Started\\n\\n```bash\\ngit clone <repo-url>\\ncd project\\nnpm install\\nnpm start\\n```\\n\\n## License\\n\\nMIT License",
                    "raw_response": full_response[:500],
                    "note": "Fallback response due to JSON parsing issues"
                }
                yield f"event: done\ndata: {json.dumps(fallback_response)}\n\n"

        except requests.exceptions.Timeout:
            logger.error("groq_api_timeout", client_ip=client_ip)
            yield f'event: error\ndata: {{"error": "Request timeout - please try again", "code": "TIMEOUT"}}\n\n'
        except requests.exceptions.RequestException as req_error:
            logger.error("groq_api_error", error=str(req_error), client_ip=client_ip)
            yield f'event: error\ndata: {{"error": "AI service temporarily unavailable", "code": "API_ERROR"}}\n\n'
        except Exception as e:
            logger.error("unexpected_error", 
                        error=str(e),
                        traceback=traceback.format_exc(),
                        client_ip=client_ip)
            yield f'event: error\ndata: {{"error": "Internal server error", "code": "INTERNAL_ERROR"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/health/")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        # Test Groq API connectivity
        test_response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
                "temperature": 0.1
            },
            timeout=10
        )
        groq_status = "healthy" if test_response.status_code == 200 else f"unhealthy ({test_response.status_code})"
        logger.info("health_check", groq_status=groq_status, status_code=test_response.status_code)
    except Exception as e:
        groq_status = f"unhealthy ({str(e)[:50]})"
        logger.error("groq_health_check_failed", error=str(e))
    
    return {
        "status": "healthy",
        "environment": ENVIRONMENT,
        "groq_api": groq_status,
        "groq_key_set": bool(GROQ_API_KEY)
    }

# Graceful shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("application_shutting_down")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(ENVIRONMENT == "development"))
