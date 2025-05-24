-- Intent Classification Service Database Schema

-- Classification results table
CREATE TABLE IF NOT EXISTS classification_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning TEXT,
    classification_metadata JSONB,
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER
);

-- Intent categories table
CREATE TABLE IF NOT EXISTS intent_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    keywords JSONB,
    patterns JSONB,
    examples JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classification feedback table
CREATE TABLE IF NOT EXISTS classification_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification_id UUID NOT NULL,
    correct_intent VARCHAR(50) NOT NULL,
    confidence_rating FLOAT NOT NULL,
    user_feedback TEXT,
    submitted_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_classification_results_created_at ON classification_results(created_at);
CREATE INDEX IF NOT EXISTS idx_classification_results_user_id ON classification_results(user_id);
CREATE INDEX IF NOT EXISTS idx_classification_results_session_id ON classification_results(session_id);
CREATE INDEX IF NOT EXISTS idx_classification_results_intent ON classification_results(intent);
CREATE INDEX IF NOT EXISTS idx_classification_feedback_classification_id ON classification_feedback(classification_id);
CREATE INDEX IF NOT EXISTS idx_classification_feedback_created_at ON classification_feedback(created_at);

-- Insert default intent categories
INSERT INTO intent_categories (name, display_name, description, keywords, patterns, examples) VALUES
(
    'bug_report',
    'Bug Report',
    'User is reporting a bug, error, or issue with the system',
    '["error", "bug", "crash", "issue", "problem", "broken", "fail", "exception", "not working", "doesnt work", "stopped working", "freezing", "hanging", "timeout", "500", "404", "403", "401", "stack trace", "traceback", "glitch", "malfunction", "defect", "fault"]',
    '["getting.*error", "fails.*to.*work", "not.*working.*properly", "throws.*exception", "returns.*\\\\d{3}.*error", "crashes.*when", "stopped.*working.*after", "breaking.*functionality", "causing.*issues"]',
    '["The app crashes when I upload a large file", "Getting a 500 error when trying to save data", "The login button is not working properly", "File processing fails with timeout error", "Dashboard throws exception on page load"]'
),
(
    'feature_request',
    'Feature Request',
    'User is requesting a new feature or enhancement',
    '["feature", "enhancement", "improvement", "suggestion", "request", "add", "implement", "support", "ability", "option", "setting", "configuration", "can we", "could we", "would be nice", "wish", "want", "need", "capability", "functionality", "integrate", "extend"]',
    '["can.*we.*add", "would.*like.*to.*see", "feature.*request", "enhancement.*for", "ability.*to.*do", "option.*to.*configure", "support.*for.*\\\\w+", "implement.*\\\\w+.*feature", "add.*functionality.*for"]',
    '["Can we add bulk edit functionality to the admin panel?", "Would like to see dark mode support", "Feature request: export data to CSV", "Need ability to configure custom fields", "Can you implement SSO integration?"]'
),
(
    'training',
    'Training/Documentation',
    'User is asking for help, documentation, or training materials',
    '["how", "tutorial", "guide", "documentation", "learn", "training", "help", "explain", "show", "teach", "understand", "configure", "setup", "install", "integrate", "example", "sample", "best practice", "workflow", "instructions", "manual", "handbook", "procedure"]',
    '["how.*do.*i", "how.*to.*\\\\w+", "what.*is.*the.*way", "best.*practice.*for", "tutorial.*on.*\\\\w+", "guide.*for.*\\\\w+", "how.*can.*i.*configure", "step.*by.*step.*\\\\w+", "instructions.*for.*\\\\w+"]',
    '["How do I configure multi-region deployments?", "Tutorial on setting up API authentication", "What are the best practices for data backup?", "How to integrate with external services?", "Step-by-step guide for user management"]'
),
(
    'general',
    'General Query',
    'General questions or queries that do not fit other categories',
    '["what", "when", "where", "who", "why", "information", "details", "about", "regarding", "concerning", "status", "update", "news", "announcement", "pricing", "cost", "license", "terms", "policy"]',
    '["what.*is.*\\\\w+", "tell.*me.*about", "information.*about", "details.*regarding", "status.*of.*\\\\w+", "when.*will.*\\\\w+", "where.*can.*i.*find"]',
    '["What is the pricing model for enterprise?", "Tell me about your security policies", "When will the next release be available?", "What are the system requirements?", "Information about data retention policies"]'
)
ON CONFLICT (name) DO NOTHING; 