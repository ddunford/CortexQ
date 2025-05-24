"""
Intent Classification Service
Classifies user queries into intent categories for intelligent routing
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import logging

from config import Settings
from database import get_db
from intent_classifier import IntentClassifier
from models import ClassificationResult, IntentCategory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Intent Classification Service",
    description="Intelligent query classification for routing to specialized agents",
    version="1.0.0"
)

# Initialize settings
settings = Settings()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize classifier
classifier = IntentClassifier(settings)

# Request/Response Models
class ClassifyRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ClassifyResponse(BaseModel):
    intent: str
    confidence: float
    reasoning: str
    suggested_workflow: str
    metadata: Dict[str, Any]
    classification_id: str

class IntentDefinition(BaseModel):
    intent: str
    description: str
    keywords: List[str]
    patterns: List[str]
    examples: List[str]

# Health Check
@app.get("/health")
async def health_check():
    """Service health check"""
    return {
        "status": "healthy",
        "service": "intent-classification",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# Classification Endpoints
@app.post("/classify", response_model=ClassifyResponse)
async def classify_intent(
    request: ClassifyRequest,
    db = Depends(get_db)
):
    """Classify the intent of a user query"""
    try:
        # Validate input
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if len(request.query) > settings.MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=400, 
                detail=f"Query too long. Maximum length: {settings.MAX_QUERY_LENGTH}"
            )
        
        # Perform classification
        result = await classifier.classify(
            query=request.query,
            context=request.context,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        # Store classification result
        classification_id = str(uuid.uuid4())
        await store_classification_result(
            db, classification_id, request, result
        )
        
        # Determine suggested workflow
        workflow = get_suggested_workflow(result.intent, result.confidence)
        
        return ClassifyResponse(
            intent=result.intent,
            confidence=result.confidence,
            reasoning=result.reasoning,
            suggested_workflow=workflow,
            metadata=result.metadata,
            classification_id=classification_id
        )
        
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/classify/batch")
async def classify_batch(
    queries: List[str],
    context: Optional[Dict[str, Any]] = None,
    db = Depends(get_db)
):
    """Classify multiple queries at once"""
    try:
        if len(queries) > settings.MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size too large. Maximum: {settings.MAX_BATCH_SIZE}"
            )
        
        results = []
        for query in queries:
            if query.strip():
                result = await classifier.classify(
                    query=query,
                    context=context
                )
                
                workflow = get_suggested_workflow(result.intent, result.confidence)
                
                results.append({
                    "query": query,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "suggested_workflow": workflow,
                    "metadata": result.metadata
                })
        
        return {"results": results, "total": len(results)}
        
    except Exception as e:
        logger.error(f"Batch classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {str(e)}")

# Intent Management
@app.get("/intents", response_model=List[IntentDefinition])
async def get_intent_definitions():
    """Get all available intent definitions"""
    return await classifier.get_intent_definitions()

@app.get("/intents/{intent}/examples")
async def get_intent_examples(intent: str):
    """Get examples for a specific intent"""
    try:
        examples = await classifier.get_intent_examples(intent)
        return {"intent": intent, "examples": examples}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Analytics and Monitoring
@app.get("/analytics/classification-stats")
async def get_classification_stats(
    days: int = 7,
    db = Depends(get_db)
):
    """Get classification statistics"""
    try:
        stats = await get_classification_analytics(db, days)
        return stats
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")

@app.get("/analytics/intent-distribution")
async def get_intent_distribution(
    days: int = 7,
    db = Depends(get_db)
):
    """Get intent distribution statistics"""
    try:
        distribution = await get_intent_distribution(db, days)
        return distribution
    except Exception as e:
        logger.error(f"Distribution analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Distribution analytics failed: {str(e)}")

# Feedback and Learning
@app.post("/feedback")
async def submit_feedback(
    classification_id: str,
    correct_intent: str,
    confidence_rating: float,
    user_feedback: Optional[str] = None,
    db = Depends(get_db)
):
    """Submit feedback on classification results for model improvement"""
    try:
        await store_classification_feedback(
            db, classification_id, correct_intent, 
            confidence_rating, user_feedback
        )
        
        # Trigger model retraining if needed
        await classifier.process_feedback(
            classification_id, correct_intent, confidence_rating
        )
        
        return {"status": "feedback_received", "classification_id": classification_id}
        
    except Exception as e:
        logger.error(f"Feedback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Feedback processing failed: {str(e)}")

# Utility Functions
def get_suggested_workflow(intent: str, confidence: float) -> str:
    """Determine suggested workflow based on intent and confidence"""
    if confidence < settings.MIN_CONFIDENCE_THRESHOLD:
        return "human_review"
    
    workflow_mapping = {
        "bug_report": "bug_detection_workflow",
        "feature_request": "feature_request_workflow", 
        "training": "documentation_workflow",
        "general": "general_rag_workflow"
    }
    
    return workflow_mapping.get(intent, "general_rag_workflow")

async def store_classification_result(
    db, classification_id: str, request: ClassifyRequest, result: ClassificationResult
):
    """Store classification result in database"""
    # Implementation would store in classifications table
    # For now, just log
    logger.info(f"Classification {classification_id}: {result.intent} ({result.confidence:.2f})")

async def get_classification_analytics(db, days: int) -> Dict[str, Any]:
    """Get classification analytics from database"""
    # Mock implementation - would query actual database
    return {
        "total_classifications": 150,
        "period_days": days,
        "average_confidence": 0.78,
        "most_common_intent": "training",
        "low_confidence_rate": 0.12
    }

async def get_intent_distribution(db, days: int) -> Dict[str, Any]:
    """Get intent distribution statistics"""
    # Mock implementation
    return {
        "distribution": {
            "bug_report": 25,
            "feature_request": 18,
            "training": 45,
            "general": 62
        },
        "period_days": days,
        "total": 150
    }

async def store_classification_feedback(
    db, classification_id: str, correct_intent: str, 
    confidence_rating: float, user_feedback: Optional[str]
):
    """Store user feedback for model improvement"""
    logger.info(f"Feedback for {classification_id}: {correct_intent} (rating: {confidence_rating})")

# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting Intent Classification Service...")
    await classifier.initialize()
    logger.info("Intent Classification Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Intent Classification Service...")
    await classifier.cleanup()
    logger.info("Intent Classification Service stopped")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=settings.CLASSIFICATION_SERVICE_PORT
    ) 