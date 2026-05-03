"""
RAG retrieval module for AI Decision Assistant
Implements strict anti-hallucination controls to ensure answers only from knowledge base
"""
import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Try to import Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for lazy loading
_vector_store: Optional[FAISS] = None
_qa_chain: Optional[object] = None


def load_vector_store(embeddings=None) -> FAISS:
    """
    Load the FAISS vector store from disk
    
    Args:
        embeddings: Embedding model instance required for FAISS.load_local
        
    Returns:
        FAISS vector store instance
    """
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store
    
    index_path = Path(settings.index_path)
    
    if not index_path.exists():
        raise FileNotFoundError(
            f"Index directory '{settings.index_path}' not found. "
            "Please run ingest.py first to create the knowledge base index."
        )
    
    try:
        logger.info(f"Loading vector store from {settings.index_path}...")
        # We need embeddings to load the FAISS store
        if embeddings is None:
            embeddings = get_embeddings()
            
        _vector_store = FAISS.load_local(
            settings.index_path, 
            embeddings,
            allow_dangerous_deserialization=True
        )
        logger.info("Vector store loaded successfully")
        return _vector_store
    except Exception as e:
        logger.error(f"Error loading vector store: {str(e)}")
        raise


def get_embeddings():
    """Initialize and return the embedding model based on configuration"""
    embeddings = None
    
    # Try OpenAI embeddings first
    if settings.openai_api_key and settings.openai_api_key != "your_openai_api_key_here":
        try:
            logger.info("Initializing OpenAI embeddings for retrieval...")
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key
            )
            # Test it
            embeddings.embed_query("test")
            return embeddings
        except Exception as e:
            logger.warning(f"OpenAI embeddings initialization failed: {e}. Falling back to local.")
    
    # Fallback to local
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        logger.info("Initializing local HuggingFace embeddings for retrieval...")
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    except Exception as e:
        logger.error(f"Failed to initialize any embedding model: {e}")
        raise ValueError("No embedding method available for retrieval.")


def get_qa_chain():
    """
    Initialize and return the QA chain with anti-hallucination prompt
    
    Returns:
        RetrievalQA chain instance
    """
    global _qa_chain
    
    if _qa_chain is not None:
        return _qa_chain
    
    try:
        vector_store = load_vector_store()
        
        # Create retriever
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.top_k_results}
        )
        
        # Anti-hallucination prompt with optional conversation history
        prompt_template = """You are a specialized AI decision assistant for volleyball athletes.
Your role is to provide accurate, evidence-based answers ONLY from the provided knowledge base.

CRITICAL RULES:
1. Answer ONLY based on the context provided below
2. If the context does not contain enough information to answer the question, say: "I don't have enough information in my knowledge base to answer this question accurately."
3. Do NOT make up information, statistics, or facts
4. Do NOT provide general knowledge that is not in the context
5. If asked about something not in the knowledge base, politely decline and suggest consulting the knowledge base
6. Support your answers with specific details from the context when available
7. You can answer in both Russian and English, matching the language of the question

{history}Context from knowledge base:
{context}

Question: {question}

Answer (based ONLY on the context above):"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question", "history"]
        )

        # Initialize LLM based on provider
        if settings.provider.lower() == "gemini":
            if not GEMINI_AVAILABLE:
                raise ValueError("Gemini support not available. Install: pip install langchain-google-genai")
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key required. Set GEMINI_API_KEY in .env file")
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                temperature=settings.temperature,
                google_api_key=settings.gemini_api_key
            )
        elif settings.provider.lower() == "deepseek":
            if not settings.deepseek_api_key:
                raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY in .env file")
            llm = ChatOpenAI(
                model=settings.deepseek_model,
                temperature=settings.temperature,
                openai_api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url
            )
        else:
            # Use OpenAI
            if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env file")
            llm = ChatOpenAI(
                model_name=settings.openai_model,
                temperature=settings.temperature,
                openai_api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Chain accepts a dict {"question": ..., "history": ...}
        rag_chain = (
            {
                "context": (lambda x: x["question"]) | retriever | format_docs,
                "question": lambda x: x["question"],
                "history": lambda x: x.get("history", ""),
            }
            | PROMPT
            | llm
            | StrOutputParser()
        )
        
        _qa_chain = {
            "chain": rag_chain,
            "retriever": retriever
        }
        
        logger.info("QA chain initialized successfully")
        return _qa_chain
        
    except Exception as e:
        logger.error(f"Error initializing QA chain: {str(e)}")
        raise


def get_answer(
    question: str,
    chat_history: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Dict[str, any]:
    """
    Get answer to a question using RAG pipeline.

    Args:
        question: User's question
        chat_history: List of prior {"question", "answer"} dicts for the session
        user_id: Optional user ID for logging/tracking

    Returns:
        Dictionary with 'answer', 'sources', and 'confidence' fields
    """
    if not question or not question.strip():
        return {"answer": "Please provide a valid question.", "sources": [], "confidence": 0.0}

    try:
        logger.info(f"Processing question from user {user_id}: {question[:100]}...")

        qa_chain_dict = get_qa_chain()
        rag_chain = qa_chain_dict["chain"]
        retriever = qa_chain_dict["retriever"]

        # Format the last 5 conversation turns into the prompt
        history_text = ""
        if chat_history:
            for msg in chat_history[-5:]:
                history_text += f"Human: {msg['question']}\nAssistant: {msg['answer']}\n\n"
        history = f"Previous conversation:\n{history_text}\n" if history_text else ""

        # Retrieve documents
        source_documents = retriever.invoke(question)

        # Run the QA chain
        answer = rag_chain.invoke({"question": question, "history": history})
        
        # Extract source information
        sources = []
        for doc in source_documents[:3]:  # Limit to top 3 sources
            source_name = doc.metadata.get("source", "Unknown")
            sources.append({
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "metadata": doc.metadata,
                "source_name": source_name
            })
        
        # Simple confidence metric based on number of sources
        confidence = min(1.0, len(source_documents) / settings.top_k_results)
        
        logger.info(f"Answer generated successfully (confidence: {confidence:.2f})")
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }
        
    except FileNotFoundError as e:
        logger.error(f"Index not found: {str(e)}")
        return {
            "answer": "Knowledge base not initialized. Please run the ingestion process first.",
            "sources": [],
            "confidence": 0.0
        }
    except Exception as e:
        logger.error(f"Error generating answer: {str(e)}")
        return {
            "answer": f"I encountered an error while processing your question: {str(e)}. Please try again.",
            "sources": [],
            "confidence": 0.0
        }


# Initialize on module import (lazy loading is handled by the functions themselves)
# No longer calling load_vector_store() here to avoid file locks on Windows during startup/rebuild
