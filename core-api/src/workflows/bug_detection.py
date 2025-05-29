"""
Bug Detection Workflow Engine
Implements specialized workflow for bug report processing
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from models.workflow_models import BugAnalysisResult, Priority
from models import KnownIssue, WorkflowExecution
from config import settings

logger = logging.getLogger(__name__)


class BugDetectionWorkflow:
    """Bug detection and analysis workflow"""
    
    def __init__(self):
        self.vector_client = httpx.AsyncClient(timeout=30.0)
        self.classification_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> BugAnalysisResult:
        """Execute bug detection workflow"""
        
        logger.info(f"Executing bug detection workflow for query: {query[:100]}...")
        
        try:
            # Step 1: Search known issues database
            known_issues = self._search_known_issues(query, db)
            
            # Step 2: Analyze error patterns
            error_analysis = self._analyze_error_patterns(query)
            
            # Step 3: Search vector database for similar issues
            vector_results = await self._search_vector_database(query, context)
            
            # Step 4: Generate analysis and recommendations
            analysis = await self._generate_analysis(
                query, known_issues, error_analysis, vector_results, context
            )
            
            # Step 5: Create development notes
            dev_notes = self._generate_dev_notes(query, analysis, context)
            
            return BugAnalysisResult(
                issue_summary=analysis["summary"],
                probable_cause=analysis["probable_cause"],
                known_solutions=analysis["solutions"],
                recommended_actions=analysis["actions"],
                dev_notes=dev_notes,
                related_issues=analysis["related_issues"],
                priority=analysis["priority"],
                resolution_estimate=analysis.get("resolution_estimate")
            )
            
        except Exception as e:
            logger.error(f"Error in bug detection workflow: {e}")
            # Return fallback analysis
            return BugAnalysisResult(
                issue_summary="Error occurred during bug analysis",
                probable_cause="Unable to determine cause due to analysis error",
                known_solutions=["Please contact support for manual investigation"],
                recommended_actions=["Submit detailed error logs", "Provide reproduction steps"],
                dev_notes=f"Automated analysis failed: {str(e)}",
                related_issues=[],
                priority=Priority.MEDIUM,
                resolution_estimate="Unknown"
            )
    
    def _search_known_issues(self, query: str, db: Session) -> List[Dict[str, Any]]:
        """Search known issues database for matching problems"""
        if not db:
            return []
        
        try:
            # Get all active known issues
            known_issues = db.query(KnownIssue).filter(KnownIssue.is_active == True).all()
            
            matches = []
            query_lower = query.lower()
            
            for issue in known_issues:
                match_score = 0.0
                
                # Check keyword matches
                if issue.keywords:
                    for keyword in issue.keywords:
                        if keyword.lower() in query_lower:
                            match_score += 0.3
                
                # Check error pattern matches
                if issue.error_patterns:
                    for pattern in issue.error_patterns:
                        try:
                            if re.search(pattern, query, re.IGNORECASE):
                                match_score += 0.5
                        except re.error:
                            continue
                
                # Check title/description similarity (basic)
                title_words = set(issue.title.lower().split())
                query_words = set(query_lower.split())
                common_words = title_words.intersection(query_words)
                if common_words:
                    match_score += len(common_words) * 0.1
                
                if match_score >= settings.BUG_KNOWN_ISSUES_THRESHOLD:
                    matches.append({
                        "issue": issue,
                        "score": match_score,
                        "title": issue.title,
                        "solution": issue.solution,
                        "priority": issue.priority,
                        "occurrence_count": issue.occurrence_count,
                        "documentation_url": issue.documentation_url
                    })
            
            # Sort by match score
            matches.sort(key=lambda x: x["score"], reverse=True)
            return matches[:5]  # Return top 5 matches
            
        except Exception as e:
            logger.error(f"Error searching known issues: {e}")
            return []
    
    def _analyze_error_patterns(self, query: str) -> Dict[str, Any]:
        """Analyze query for common error patterns"""
        patterns = {
            "http_errors": [
                (r"404|not found", "Resource not found - check URL or endpoint"),
                (r"500|internal server error", "Server-side error - check logs and database"),
                (r"403|forbidden", "Permission denied - check authentication/authorization"),
                (r"401|unauthorized", "Authentication required - check credentials"),
                (r"429|too many requests", "Rate limiting - implement backoff strategy")
            ],
            "database_errors": [
                (r"connection.*timeout|timeout.*connection", "Database connection timeout"),
                (r"duplicate.*key|unique.*constraint", "Data integrity violation"),
                (r"foreign.*key.*constraint", "Referential integrity issue"),
                (r"deadlock|lock.*timeout", "Database concurrency issue")
            ],
            "application_errors": [
                (r"null.*pointer|nullpointerexception", "Null reference error"),
                (r"out.*of.*memory|memory.*leak", "Memory management issue"),
                (r"stack.*overflow", "Infinite recursion or deep call stack"),
                (r"class.*not.*found|module.*not.*found", "Missing dependency or import")
            ],
            "network_errors": [
                (r"connection.*refused", "Service unavailable or port blocked"),
                (r"dns.*resolution|host.*not.*found", "DNS or hostname issue"),
                (r"ssl.*certificate|tls.*handshake", "Certificate or encryption issue")
            ]
        }
        
        detected_patterns = []
        query_lower = query.lower()
        
        for category, category_patterns in patterns.items():
            for pattern, description in category_patterns:
                if re.search(pattern, query_lower):
                    detected_patterns.append({
                        "category": category,
                        "pattern": pattern,
                        "description": description,
                        "severity": self._get_pattern_severity(pattern)
                    })
        
        return {
            "detected_patterns": detected_patterns,
            "pattern_count": len(detected_patterns),
            "severity": max([p["severity"] for p in detected_patterns], default="low")
        }
    
    def _get_pattern_severity(self, pattern: str) -> str:
        """Determine severity level of detected pattern"""
        critical_patterns = ["500", "memory.*leak", "deadlock", "out.*of.*memory"]
        high_patterns = ["404", "timeout", "null.*pointer", "connection.*refused"]
        
        pattern_lower = pattern.lower()
        
        for critical in critical_patterns:
            if re.search(critical, pattern_lower):
                return "critical"
        
        for high in high_patterns:
            if re.search(high, pattern_lower):
                return "high"
        
        return "medium"
    
    async def _search_vector_database(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search vector database for similar issues"""
        try:
            # Search in support domain for bug-related content
            search_url = f"{settings.VECTOR_SERVICE_URL}/search/support"
            search_payload = {
                "query": query,
                "top_k": 5
            }
            
            response = await self.vector_client.post(search_url, json=search_payload)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("results", [])
            else:
                logger.warning(f"Vector search failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching vector database: {e}")
            return []
    
    async def _generate_analysis(
        self,
        query: str,
        known_issues: List[Dict[str, Any]],
        error_analysis: Dict[str, Any],
        vector_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive bug analysis"""
        
        # Determine priority based on error patterns and known issues
        priority = self._determine_priority(error_analysis, known_issues)
        
        # Generate issue summary
        summary = self._generate_issue_summary(query, error_analysis)
        
        # Determine probable cause
        probable_cause = self._determine_probable_cause(error_analysis, known_issues, vector_results)
        
        # Collect solutions from known issues and vector results
        solutions = self._collect_solutions(known_issues, vector_results)
        
        # Generate recommended actions
        actions = self._generate_recommended_actions(error_analysis, known_issues, priority)
        
        # Collect related issues
        related_issues = self._collect_related_issues(known_issues, vector_results)
        
        # Estimate resolution time
        resolution_estimate = self._estimate_resolution_time(priority, known_issues)
        
        return {
            "summary": summary,
            "probable_cause": probable_cause,
            "solutions": solutions,
            "actions": actions,
            "related_issues": related_issues,
            "priority": priority,
            "resolution_estimate": resolution_estimate
        }
    
    def _determine_priority(
        self, 
        error_analysis: Dict[str, Any], 
        known_issues: List[Dict[str, Any]]
    ) -> Priority:
        """Determine issue priority based on analysis"""
        
        # Check error pattern severity
        if error_analysis.get("severity") == "critical":
            return Priority.CRITICAL
        
        # Check known issues priority
        for issue in known_issues:
            if issue.get("priority") == Priority.CRITICAL:
                return Priority.CRITICAL
            elif issue.get("priority") == Priority.HIGH:
                return Priority.HIGH
        
        # Check occurrence frequency
        high_frequency_threshold = 10
        for issue in known_issues:
            if issue.get("occurrence_count", 0) > high_frequency_threshold:
                return Priority.HIGH
        
        # Default based on error pattern severity
        severity = error_analysis.get("severity", "low")
        if severity == "high":
            return Priority.HIGH
        elif severity == "medium":
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _generate_issue_summary(self, query: str, error_analysis: Dict[str, Any]) -> str:
        """Generate concise issue summary"""
        patterns = error_analysis.get("detected_patterns", [])
        
        if patterns:
            main_pattern = patterns[0]
            return f"Detected {main_pattern['category']} issue: {main_pattern['description']}"
        else:
            # Extract key terms from query
            key_terms = [word for word in query.split() if len(word) > 3][:5]
            return f"Issue reported involving: {', '.join(key_terms)}"
    
    def _determine_probable_cause(
        self,
        error_analysis: Dict[str, Any],
        known_issues: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]]
    ) -> str:
        """Determine most likely cause of the issue"""
        
        # If we have matching known issues, use their analysis
        if known_issues:
            best_match = known_issues[0]
            return f"Based on known issue '{best_match['title']}': {best_match['issue'].description}"
        
        # If we have error patterns, use those
        patterns = error_analysis.get("detected_patterns", [])
        if patterns:
            main_pattern = patterns[0]
            return f"Error pattern suggests: {main_pattern['description']}"
        
        # Fallback to generic analysis
        return "Issue requires further investigation to determine root cause"
    
    def _collect_solutions(
        self, 
        known_issues: List[Dict[str, Any]], 
        vector_results: List[Dict[str, Any]]
    ) -> List[str]:
        """Collect potential solutions from various sources"""
        solutions = []
        
        # Add solutions from known issues
        for issue in known_issues:
            if issue.get("solution"):
                solutions.append(f"Known solution: {issue['solution']}")
        
        # Add relevant information from vector results
        for result in vector_results[:3]:  # Top 3 results
            content = result.get("content", "")
            if "solution" in content.lower() or "fix" in content.lower():
                # Extract relevant portion (simplified)
                solutions.append(f"Related solution: {content[:200]}...")
        
        # Add generic troubleshooting steps if no specific solutions
        if not solutions:
            solutions = [
                "Check application logs for detailed error information",
                "Verify system configuration and dependencies",
                "Test in a controlled environment to reproduce the issue",
                "Contact support team with detailed error logs"
            ]
        
        return solutions[:5]  # Limit to 5 solutions
    
    def _generate_recommended_actions(
        self,
        error_analysis: Dict[str, Any],
        known_issues: List[Dict[str, Any]],
        priority: Priority
    ) -> List[str]:
        """Generate specific recommended actions"""
        actions = []
        
        # Priority-based actions
        if priority == Priority.CRITICAL:
            actions.extend([
                "Escalate to development team immediately",
                "Create incident ticket with high priority",
                "Monitor system for similar occurrences"
            ])
        elif priority == Priority.HIGH:
            actions.extend([
                "Schedule fix for next maintenance window",
                "Document workaround for users"
            ])
        
        # Pattern-based actions
        patterns = error_analysis.get("detected_patterns", [])
        for pattern in patterns:
            if "database" in pattern["category"]:
                actions.append("Check database connection and query performance")
            elif "network" in pattern["category"]:
                actions.append("Verify network connectivity and firewall settings")
            elif "application" in pattern["category"]:
                actions.append("Review application code and dependencies")
        
        # Generic actions
        actions.extend([
            "Collect detailed logs and system information",
            "Test reproduction steps in development environment",
            "Update documentation if new issue discovered"
        ])
        
        return list(set(actions))  # Remove duplicates
    
    def _collect_related_issues(
        self, 
        known_issues: List[Dict[str, Any]], 
        vector_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Collect related issues and resources"""
        related = []
        
        # Add known issues as related
        for issue in known_issues:
            related.append({
                "type": "known_issue",
                "title": issue["title"],
                "url": issue.get("documentation_url"),
                "relevance": issue["score"]
            })
        
        # Add vector search results
        for result in vector_results:
            related.append({
                "type": "documentation",
                "title": result.get("metadata", {}).get("title", "Related Content"),
                "content": result.get("content", "")[:200] + "...",
                "relevance": result.get("similarity", 0.0)
            })
        
        return related[:10]  # Limit to 10 related items
    
    def _estimate_resolution_time(
        self, 
        priority: Priority, 
        known_issues: List[Dict[str, Any]]
    ) -> str:
        """Estimate resolution time based on priority and historical data"""
        
        # Use historical data from known issues if available
        if known_issues:
            avg_time = sum(issue.get("issue").resolution_time_avg or 60 
                          for issue in known_issues) / len(known_issues)
            return f"Estimated {int(avg_time)} minutes based on similar issues"
        
        # Default estimates by priority
        if priority == Priority.CRITICAL:
            return "1-4 hours (immediate attention required)"
        elif priority == Priority.HIGH:
            return "4-24 hours (next business day)"
        elif priority == Priority.MEDIUM:
            return "1-3 business days"
        else:
            return "3-7 business days (low priority)"
    
    def _generate_dev_notes(
        self, 
        query: str, 
        analysis: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate internal development notes"""
        
        notes = []
        notes.append(f"**Original Query**: {query}")
        notes.append(f"**Priority**: {analysis['priority']}")
        notes.append(f"**Analysis Date**: {datetime.utcnow().isoformat()}")
        
        if context:
            notes.append(f"**User Context**: {context}")
        
        notes.append(f"**Probable Cause**: {analysis['probable_cause']}")
        
        if analysis.get("resolution_estimate"):
            notes.append(f"**Resolution Estimate**: {analysis['resolution_estimate']}")
        
        notes.append("**Next Steps for Development Team**:")
        for action in analysis["actions"]:
            notes.append(f"- {action}")
        
        return "\n".join(notes)
    
    async def close(self):
        """Close HTTP clients"""
        await self.vector_client.aclose()
        await self.classification_client.aclose() 