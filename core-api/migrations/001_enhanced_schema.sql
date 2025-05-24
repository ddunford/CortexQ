-- Enhanced Schema Migration: Integrate All Microservice Functionality
-- Version: 001
-- Description: Migrate from basic core-api schema to enterprise-ready unified schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- USERS & AUTHENTICATION (Enhanced from auth-service)
-- ============================================================================

-- Drop existing basic users table and recreate with enhanced schema
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS embeddings CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Enhanced Users table with RBAC support
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    login_count INTEGER DEFAULT 0,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles table for RBAC
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '[]',
    domain_access JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-Role association table
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by UUID REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);

-- User sessions for enhanced auth tracking
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_info JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- FILE MANAGEMENT (Enhanced from file-service)
-- ============================================================================

-- Enhanced Files table with domain support and processing pipeline
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    file_hash VARCHAR(64) UNIQUE,
    file_path VARCHAR(500),
    processed BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_error TEXT,
    domain VARCHAR(50) DEFAULT 'general',
    metadata JSONB DEFAULT '{}',
    tags TEXT[],
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- File processing jobs queue
CREATE TABLE file_processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- VECTOR STORAGE & SEARCH (Enhanced from vector-service)
-- ============================================================================

-- Multi-Domain Vector embeddings
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES files(id) ON DELETE CASCADE,
    source_type VARCHAR(50) DEFAULT 'file',
    domain VARCHAR(50) NOT NULL,
    chunk_index INTEGER DEFAULT 0,
    content_text TEXT NOT NULL,
    content_hash VARCHAR(64),
    embedding vector(384), -- MiniLM dimension
    embedding_model VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector index metadata for multi-domain support
CREATE TABLE vector_indices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(50) UNIQUE NOT NULL,
    index_type VARCHAR(50) DEFAULT 'faiss_flat',
    dimension INTEGER DEFAULT 384,
    total_vectors INTEGER DEFAULT 0,
    index_metadata JSONB DEFAULT '{}',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- QUERY PROCESSING (Enhanced from classification & rag services)
-- ============================================================================

-- Intent Classification results
CREATE TABLE classification_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    domain VARCHAR(50),
    classification_method VARCHAR(50),
    reasoning TEXT,
    metadata JSONB DEFAULT '{}',
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER
);

-- Intent categories configuration
CREATE TABLE intent_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    keywords JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '[]',
    examples JSONB DEFAULT '[]',
    domains JSONB DEFAULT '["general"]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RAG execution tracking
CREATE TABLE rag_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    domain VARCHAR(50),
    intent VARCHAR(50),
    retrieval_results JSONB,
    response TEXT,
    confidence FLOAT,
    sources_count INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    model_used VARCHAR(100),
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AGENT WORKFLOWS (Enhanced from agent-service)
-- ============================================================================

-- Workflow execution tracking
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_type VARCHAR(50) NOT NULL,
    workflow_name VARCHAR(100),
    input_data JSONB NOT NULL,
    output_data JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    confidence FLOAT,
    steps_completed INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 1,
    error_message TEXT,
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Workflow steps for detailed tracking
CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    step_name VARCHAR(100) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================================
-- CHAT & CONVERSATIONS (Enhanced from chat-api)
-- ============================================================================

-- Chat sessions with domain support
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    domain VARCHAR(50) DEFAULT 'general',
    title VARCHAR(255),
    context JSONB DEFAULT '{}',
    message_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

-- Chat messages with enhanced metadata
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent VARCHAR(50),
    confidence FLOAT,
    sources JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AUDIT & COMPLIANCE (Enhanced from audit-service)
-- ============================================================================

-- Comprehensive audit logging
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50),
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    resource VARCHAR(100),
    action VARCHAR(50),
    description TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_id VARCHAR(100),
    event_data JSONB DEFAULT '{}',
    severity VARCHAR(20) DEFAULT 'info',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data retention policies
CREATE TABLE data_retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_type VARCHAR(100) NOT NULL,
    retention_period_days INTEGER NOT NULL,
    archive_enabled BOOLEAN DEFAULT FALSE,
    archive_location VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

-- User indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Role indexes
CREATE INDEX idx_roles_name ON roles(name);
CREATE INDEX idx_roles_active ON roles(is_active);

-- File indexes
CREATE INDEX idx_files_uploaded_by ON files(uploaded_by);
CREATE INDEX idx_files_domain ON files(domain);
CREATE INDEX idx_files_processed ON files(processed);
CREATE INDEX idx_files_created_at ON files(created_at);
CREATE INDEX idx_files_hash ON files(file_hash);

-- Embedding indexes
CREATE INDEX idx_embeddings_source_id ON embeddings(source_id);
CREATE INDEX idx_embeddings_domain ON embeddings(domain);
CREATE INDEX idx_embeddings_content_hash ON embeddings(content_hash);

-- Classification indexes
CREATE INDEX idx_classification_results_user_id ON classification_results(user_id);
CREATE INDEX idx_classification_results_intent ON classification_results(intent);
CREATE INDEX idx_classification_results_domain ON classification_results(domain);
CREATE INDEX idx_classification_results_created_at ON classification_results(created_at);

-- RAG execution indexes
CREATE INDEX idx_rag_executions_user_id ON rag_executions(user_id);
CREATE INDEX idx_rag_executions_domain ON rag_executions(domain);
CREATE INDEX idx_rag_executions_created_at ON rag_executions(created_at);

-- Workflow indexes
CREATE INDEX idx_workflow_executions_type ON workflow_executions(workflow_type);
CREATE INDEX idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_created_at ON workflow_executions(started_at);

-- Chat indexes
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX idx_chat_sessions_domain ON chat_sessions(domain);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);

-- Audit indexes
CREATE INDEX idx_audit_events_user_id ON audit_events(user_id);
CREATE INDEX idx_audit_events_event_type ON audit_events(event_type);
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);
CREATE INDEX idx_audit_events_resource ON audit_events(resource);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Function to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables with updated_at columns
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_roles_updated_at 
    BEFORE UPDATE ON roles 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_files_updated_at 
    BEFORE UPDATE ON files 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update chat session activity
CREATE OR REPLACE FUNCTION update_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat_sessions 
    SET last_activity = CURRENT_TIMESTAMP, 
        message_count = message_count + 1
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_session_activity
    AFTER INSERT ON chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_session_activity();

-- ============================================================================
-- DEFAULT DATA SETUP
-- ============================================================================

-- Insert default roles
INSERT INTO roles (name, description, permissions, domain_access) VALUES
('admin', 'System Administrator', 
 '["*:*"]', 
 '["general", "support", "sales", "engineering", "product"]'),
('support', 'Support Team Member', 
 '["chat:read", "chat:write", "files:read", "search:read", "workflows:execute"]', 
 '["general", "support"]'),
('sales', 'Sales Team Member', 
 '["chat:read", "chat:write", "files:read", "search:read"]', 
 '["general", "sales"]'),
('engineering', 'Engineering Team Member', 
 '["chat:read", "chat:write", "files:read", "files:write", "search:read", "workflows:execute"]', 
 '["general", "engineering"]'),
('product', 'Product Team Member', 
 '["chat:read", "chat:write", "files:read", "search:read", "workflows:execute"]', 
 '["general", "product"]'),
('user', 'Regular User', 
 '["chat:read", "search:read"]', 
 '["general"]');

-- Insert default intent categories
INSERT INTO intent_categories (name, display_name, description, keywords, patterns, examples, domains) VALUES
('bug_report', 'Bug Report', 'User reporting a software bug or issue', 
 '["error", "bug", "crash", "broken", "issue", "problem", "not working"]',
 '[".*error.*", ".*crash.*", ".*not working.*", ".*broken.*"]',
 '["The app crashes when I click save", "I get an error message", "This feature is not working"]',
 '["general", "support", "engineering"]'),
('feature_request', 'Feature Request', 'User requesting new functionality', 
 '["feature", "request", "add", "new", "enhancement", "improvement", "want", "need"]',
 '[".*feature.*", ".*request.*", "can you add.*", ".*enhancement.*"]',
 '["Can you add bulk editing?", "I need a new export feature", "Enhancement request for dashboard"]',
 '["general", "product", "engineering"]'),
('training', 'Training/Documentation', 'User asking for help or documentation', 
 '["how", "tutorial", "guide", "help", "documentation", "learn", "explain"]',
 '["how to.*", ".*tutorial.*", ".*guide.*", "help me.*"]',
 '["How do I configure deployments?", "Where is the user guide?", "Tutorial for new features"]',
 '["general", "support", "sales"]'),
('general_query', 'General Query', 'General questions and information requests', 
 '["what", "when", "where", "who", "why", "information", "details"]',
 '["what is.*", "when does.*", "where can.*"]',
 '["What is the latest version?", "When will this be available?", "Where can I find pricing?"]',
 '["general", "support", "sales", "engineering", "product"]');

-- Insert default vector indices for each domain
INSERT INTO vector_indices (domain, index_type, dimension) VALUES
('general', 'faiss_flat', 384),
('support', 'faiss_flat', 384),
('sales', 'faiss_flat', 384),
('engineering', 'faiss_flat', 384),
('product', 'faiss_flat', 384);

-- Insert default admin user (password: admin123)
INSERT INTO users (username, email, full_name, password_hash, is_superuser, is_verified) 
VALUES ('admin', 'admin@example.com', 'System Administrator', 
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8xqUx3QJlC', 
        true, true)
ON CONFLICT (username) DO NOTHING;

-- Assign admin role to admin user
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id 
FROM users u, roles r 
WHERE u.username = 'admin' AND r.name = 'admin'
ON CONFLICT DO NOTHING;

-- Insert default data retention policies
INSERT INTO data_retention_policies (resource_type, retention_period_days, archive_enabled) VALUES
('audit_events', 2555, true),  -- 7 years for compliance
('chat_messages', 365, true),   -- 1 year
('rag_executions', 90, false),  -- 3 months
('classification_results', 90, false); -- 3 months

COMMIT; 