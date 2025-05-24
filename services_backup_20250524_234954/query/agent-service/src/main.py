"""
Agent Workflow Service - Main Application
Orchestrates specialized agent workflows for intelligent query routing
"""

import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import get_db, init_database, check_database_health
from models import (
    WorkflowRequest, WorkflowResponse, WorkflowType, WorkflowStatus, 
    WorkflowExecution, HealthResponse, WorkflowStats
)
from workflows.bug_detection import BugDetectionWorkflow
from workflows.feature_request import FeatureRequestWorkflow
from workflows.training import TrainingWorkflow

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Agent Workflow Service",
    description="Intelligent agent workflows for specialized query routing and processing",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global workflow instances
bug_workflow = BugDetectionWorkflow()
feature_workflow = FeatureRequestWorkflow()
training_workflow = TrainingWorkflow()

# Workflow routing map
WORKFLOW_MAP = {
    "bug_report": (WorkflowType.BUG_DETECTION, bug_workflow),
    "feature_request": (WorkflowType.FEATURE_REQUEST, feature_workflow),
    "training": (WorkflowType.TRAINING, training_workflow),
    "general": (WorkflowType.GENERAL, None)  # Fallback to general processing
}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting Agent Workflow Service...")
    
    try:
        # Initialize database
        init_database()
        logger.info("Database initialized successfully")
        
        # Test external service connections
        await test_external_services()
        
        logger.info(f"Agent Workflow Service v{settings.SERVICE_VERSION} started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down Agent Workflow Service...")
    
    # Close workflow HTTP clients
    await bug_workflow.close()
    await feature_workflow.close()
    await training_workflow.close()
    
    logger.info("Agent Workflow Service shutdown complete")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check"""
    
    # Check database health
    db_healthy = check_database_health()
    
    # Check external service connections
    external_services = await check_external_services()
    
    # Get basic workflow stats
    try:
        db = next(get_db())
        total_executions = db.query(WorkflowExecution).count()
        successful = db.query(WorkflowExecution).filter(
            WorkflowExecution.status == WorkflowStatus.COMPLETED
        ).count()
        
        stats = {
            "total_executions": total_executions,
            "success_rate": (successful / total_executions * 100) if total_executions > 0 else 0,
            "database_health": "healthy" if db_healthy else "unhealthy"
        }
    except Exception as e:
        logger.error(f"Error getting workflow stats: {e}")
        stats = {"error": str(e)}
    
    status = "healthy" if db_healthy and all(external_services.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        dependencies=external_services,
        workflow_stats=stats
    )


@app.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Execute a workflow based on intent classification"""
    
    logger.info(f"Executing workflow for intent: {request.intent}")
    
    # Create workflow execution record
    workflow_execution = WorkflowExecution(
        workflow_type=request.intent,
        status=WorkflowStatus.PENDING,
        original_query=request.query,
        classification_data=request.classification_metadata,
        user_context=request.user_context,
        user_id=request.user_id,
        session_id=request.session_id
    )
    
    db.add(workflow_execution)
    db.commit()
    db.refresh(workflow_execution)
    
    try:
        # Route to appropriate workflow
        workflow_type, workflow_engine = WORKFLOW_MAP.get(
            request.intent, 
            (WorkflowType.GENERAL, None)
        )
        
        # Update status to processing
        workflow_execution.status = WorkflowStatus.PROCESSING
        workflow_execution.started_at = datetime.utcnow()
        db.commit()
        
        if workflow_engine is None:
            # Handle general queries with fallback logic
            response_data = await handle_general_workflow(request, db)
        else:
            # Execute specialized workflow
            start_time = datetime.utcnow()
            
            result = await workflow_engine.execute(
                query=request.query,
                context=request.user_context,
                db=db
            )
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Format response using workflow result
            response_data = format_workflow_response(
                workflow_type, result, processing_time, request
            )
        
        # Update workflow execution with results
        workflow_execution.status = WorkflowStatus.COMPLETED
        workflow_execution.completed_at = datetime.utcnow()
        workflow_execution.generated_response = response_data["response"]
        workflow_execution.confidence_score = response_data["confidence"]
        workflow_execution.processing_time_ms = response_data["processing_time_ms"]
        workflow_execution.analysis_results = response_data["metadata"]
        
        db.commit()
        
        # Schedule background tasks if needed
        background_tasks.add_task(
            post_process_workflow, 
            str(workflow_execution.id), 
            request.intent, 
            response_data
        )
        
        return WorkflowResponse(
            workflow_id=str(workflow_execution.id),
            workflow_type=workflow_type,
            status=WorkflowStatus.COMPLETED,
            **response_data
        )
        
    except Exception as e:
        logger.error(f"Workflow execution error: {e}")
        
        # Update workflow execution with error
        workflow_execution.status = WorkflowStatus.FAILED
        workflow_execution.error_message = str(e)
        workflow_execution.completed_at = datetime.utcnow()
        db.commit()
        
        # Check if escalation is needed
        should_escalate = determine_escalation_needed(request, str(e))
        
        if should_escalate:
            workflow_execution.status = WorkflowStatus.ESCALATED
            workflow_execution.escalation_reason = f"Workflow failed: {str(e)}"
            db.commit()
        
        return WorkflowResponse(
            workflow_id=str(workflow_execution.id),
            workflow_type=WorkflowType.GENERAL,
            status=WorkflowStatus.FAILED if not should_escalate else WorkflowStatus.ESCALATED,
            response=f"Workflow execution failed: {str(e)}",
            confidence=0.1,
            metadata={"error": str(e)},
            processing_time_ms=0,
            escalated=should_escalate,
            escalation_reason=f"Workflow failed: {str(e)}" if should_escalate else None
        )


@app.get("/workflows/{workflow_id}")
async def get_workflow_execution(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get workflow execution details"""
    
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == uuid.UUID(workflow_id)
        ).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")
        
        return {
            "workflow_id": str(execution.id),
            "workflow_type": execution.workflow_type,
            "status": execution.status,
            "query": execution.original_query,
            "response": execution.generated_response,
            "confidence": execution.confidence_score,
            "processing_time_ms": execution.processing_time_ms,
            "created_at": execution.created_at,
            "completed_at": execution.completed_at,
            "metadata": execution.analysis_results
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format")
    except Exception as e:
        logger.error(f"Error retrieving workflow: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve workflow")


@app.get("/stats", response_model=WorkflowStats)
async def get_workflow_stats(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get workflow execution statistics"""
    
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get executions from the specified period
        executions = db.query(WorkflowExecution).filter(
            WorkflowExecution.created_at >= cutoff_date
        ).all()
        
        total_executions = len(executions)
        successful = len([e for e in executions if e.status == WorkflowStatus.COMPLETED])
        escalated = len([e for e in executions if e.status == WorkflowStatus.ESCALATED])
        
        # Calculate average processing time
        processing_times = [e.processing_time_ms for e in executions if e.processing_time_ms]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        # Workflow type breakdown
        workflow_breakdown = {}
        for execution in executions:
            workflow_type = execution.workflow_type
            workflow_breakdown[workflow_type] = workflow_breakdown.get(workflow_type, 0) + 1
        
        # Top issues (simplified)
        top_issues = []
        bug_executions = [e for e in executions if e.workflow_type == "bug_report"]
        if bug_executions:
            top_issues.append({
                "type": "bug_report",
                "count": len(bug_executions),
                "avg_processing_time": sum(e.processing_time_ms or 0 for e in bug_executions) / len(bug_executions)
            })
        
        return WorkflowStats(
            total_executions=total_executions,
            success_rate=(successful / total_executions * 100) if total_executions > 0 else 0,
            average_processing_time=avg_processing_time,
            workflow_breakdown=workflow_breakdown,
            top_issues=top_issues,
            escalation_rate=(escalated / total_executions * 100) if total_executions > 0 else 0
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


async def handle_general_workflow(request: WorkflowRequest, db: Session) -> Dict[str, Any]:
    """Handle general queries that don't fit specialized workflows"""
    
    return {
        "response": f"I understand you're asking about: {request.query}\n\nI've processed your general query, but for more specific assistance, please consider rephrasing your question to be more specific about whether this is a bug report, feature request, or help documentation request.",
        "confidence": 0.6,
        "metadata": {
            "workflow_type": "general",
            "fallback_reason": "No specialized workflow matched"
        },
        "suggested_actions": [
            "Rephrase question with more specific intent",
            "Contact support for personalized assistance",
            "Browse documentation for related topics"
        ],
        "related_resources": [],
        "processing_time_ms": 100
    }


def format_workflow_response(
    workflow_type: WorkflowType, 
    result: Any, 
    processing_time: int, 
    request: WorkflowRequest
) -> Dict[str, Any]:
    """Format workflow result into standardized response"""
    
    if workflow_type == WorkflowType.BUG_DETECTION:
        response = settings.BUG_RESPONSE_TEMPLATE.format(
            summary=result.issue_summary,
            probable_cause=result.probable_cause,
            known_solutions="\n".join(f"- {sol}" for sol in result.known_solutions),
            recommended_actions="\n".join(f"- {action}" for action in result.recommended_actions),
            dev_notes=result.dev_notes,
            related_issues=len(result.related_issues)
        )
        
        return {
            "response": response,
            "confidence": 0.8,
            "metadata": {
                "priority": result.priority,
                "resolution_estimate": result.resolution_estimate,
                "related_issues_count": len(result.related_issues)
            },
            "suggested_actions": result.recommended_actions,
            "related_resources": result.related_issues,
            "processing_time_ms": processing_time
        }
    
    elif workflow_type == WorkflowType.FEATURE_REQUEST:
        response = settings.FEATURE_RESPONSE_TEMPLATE.format(
            summary=result.request_summary,
            status=result.status,
            existing_features="\n".join(f"- {feat['title']}" for feat in result.existing_features),
            implementation_notes=result.implementation_notes,
            business_impact=result.business_impact,
            next_steps="\n".join(f"- {step}" for step in result.next_steps)
        )
        
        return {
            "response": response,
            "confidence": 0.75,
            "metadata": {
                "estimated_effort": result.estimated_effort,
                "similar_requests_count": len(result.similar_requests),
                "existing_features_count": len(result.existing_features)
            },
            "suggested_actions": result.next_steps,
            "related_resources": result.existing_features,
            "processing_time_ms": processing_time
        }
    
    elif workflow_type == WorkflowType.TRAINING:
        response = settings.TRAINING_RESPONSE_TEMPLATE.format(
            topic=result.topic,
            step_by_step="\n".join(f"{i+1}. {step}" for i, step in enumerate(result.step_by_step)),
            code_examples="\n".join(f"```{ex['language']}\n{ex['code']}\n```" for ex in result.code_examples),
            resources="\n".join(f"- [{res['title']}]({res['url']})" for res in result.resources),
            related_docs="\n".join(f"- [{doc['title']}]({doc['url']})" for doc in result.related_docs)
        )
        
        return {
            "response": response,
            "confidence": 0.85,
            "metadata": {
                "difficulty_level": result.difficulty_level,
                "code_examples_count": len(result.code_examples),
                "resources_count": len(result.resources)
            },
            "suggested_actions": ["Follow the step-by-step guide", "Try the code examples", "Explore additional resources"],
            "related_resources": result.resources + result.related_docs,
            "processing_time_ms": processing_time
        }
    
    else:
        # Fallback for unknown workflow types
        return {
            "response": "Workflow completed successfully",
            "confidence": 0.5,
            "metadata": {"workflow_type": str(workflow_type)},
            "suggested_actions": [],
            "related_resources": [],
            "processing_time_ms": processing_time
        }


def determine_escalation_needed(request: WorkflowRequest, error_message: str) -> bool:
    """Determine if a failed workflow should be escalated to humans"""
    
    # Escalate if confidence was high but workflow still failed
    if request.confidence > 0.8:
        return True
    
    # Escalate for certain types of errors
    escalation_triggers = [
        "database",
        "connection",
        "timeout",
        "critical",
        "urgent"
    ]
    
    error_lower = error_message.lower()
    query_lower = request.query.lower()
    
    return any(trigger in error_lower or trigger in query_lower 
              for trigger in escalation_triggers)


async def post_process_workflow(
    workflow_id: str, 
    intent: str, 
    response_data: Dict[str, Any]
):
    """Post-process workflow execution for analytics and learning"""
    
    logger.info(f"Post-processing workflow {workflow_id}")
    
    try:
        # Here you could add:
        # - Analytics tracking
        # - Machine learning model updates
        # - External system notifications
        # - Feedback collection triggers
        
        pass
        
    except Exception as e:
        logger.error(f"Error in post-processing: {e}")


async def test_external_services():
    """Test connections to external services"""
    
    logger.info("Testing external service connections...")
    
    # Test vector service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.VECTOR_SERVICE_URL}/health")
            if response.status_code == 200:
                logger.info("Vector service connection: OK")
            else:
                logger.warning(f"Vector service returned status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Vector service connection failed: {e}")


async def check_external_services() -> Dict[str, str]:
    """Check health of external services"""
    
    services = {}
    
    # Check vector service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.VECTOR_SERVICE_URL}/health")
            services["vector_service"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services["vector_service"] = "unhealthy"
    
    # Check classification service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.CLASSIFICATION_SERVICE_URL}/health")
            services["classification_service"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services["classification_service"] = "unhealthy"
    
    return services


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 