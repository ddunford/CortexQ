-- Create extension for UUID generation and vector support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Enhanced Users table with full RBAC support
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles table for RBAC
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    resource_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User roles mapping
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

-- Role permissions mapping
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

-- Domain access table
CREATE TABLE IF NOT EXISTS domain_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    domain VARCHAR(50) NOT NULL,
    access_level VARCHAR(20) DEFAULT 'read', -- read, write, admin
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, domain)
);

-- Enhanced Files table
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    uploaded_by UUID REFERENCES users(id),
    domain VARCHAR(50) DEFAULT 'general',
    file_hash VARCHAR(64),
    processing_status VARCHAR(20) DEFAULT 'pending',
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Enhanced Embeddings table with domain support
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES files(id) ON DELETE CASCADE,
    content_text TEXT,
    embedding vector(384), -- MiniLM embedding dimension
    domain VARCHAR(50) DEFAULT 'general',
    chunk_index INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id),
    domain VARCHAR(50) DEFAULT 'general',
    session_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_type VARCHAR(20) NOT NULL, -- user, assistant
    content TEXT NOT NULL,
    intent VARCHAR(50),
    confidence FLOAT,
    sources JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Classification results table
CREATE TABLE IF NOT EXISTS classification_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    domain VARCHAR(50) DEFAULT 'general',
    classification_method VARCHAR(50),
    reasoning TEXT,
    metadata JSONB DEFAULT '{}',
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RAG executions table
CREATE TABLE IF NOT EXISTS rag_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    domain VARCHAR(50) DEFAULT 'general',
    mode VARCHAR(20) DEFAULT 'simple', -- simple, cross_domain, agent_enhanced, hybrid
    intent VARCHAR(50),
    confidence FLOAT,
    response_type VARCHAR(20),
    source_count INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    cache_hit BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_type VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    response TEXT,
    analysis JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Known issues table for bug workflow
CREATE TABLE IF NOT EXISTS known_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    solution TEXT,
    severity VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'open',
    domain VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced Audit events table
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id),
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    action VARCHAR(50),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for enhanced performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_domain_access_user_id ON domain_access(user_id);
CREATE INDEX IF NOT EXISTS idx_domain_access_domain ON domain_access(domain);

CREATE INDEX IF NOT EXISTS idx_files_uploaded_by ON files(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_files_domain ON files(domain);
CREATE INDEX IF NOT EXISTS idx_files_upload_date ON files(upload_date);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status);

CREATE INDEX IF NOT EXISTS idx_embeddings_source_id ON embeddings(source_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_domain ON embeddings(domain);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_domain ON chat_sessions(domain);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

CREATE INDEX IF NOT EXISTS idx_classification_results_intent ON classification_results(intent);
CREATE INDEX IF NOT EXISTS idx_classification_results_domain ON classification_results(domain);
CREATE INDEX IF NOT EXISTS idx_classification_results_created_at ON classification_results(created_at);

CREATE INDEX IF NOT EXISTS idx_rag_executions_domain ON rag_executions(domain);
CREATE INDEX IF NOT EXISTS idx_rag_executions_mode ON rag_executions(mode);
CREATE INDEX IF NOT EXISTS idx_rag_executions_intent ON rag_executions(intent);
CREATE INDEX IF NOT EXISTS idx_rag_executions_created_at ON rag_executions(created_at);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_type ON workflow_executions(workflow_type);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_created_at ON workflow_executions(created_at);

CREATE INDEX IF NOT EXISTS idx_known_issues_domain ON known_issues(domain);
CREATE INDEX IF NOT EXISTS idx_known_issues_status ON known_issues(status);

CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

-- Insert default roles
INSERT INTO roles (name, description) VALUES 
    ('admin', 'System administrator with full access'),
    ('user', 'Standard user with limited access'),
    ('support', 'Support team member'),
    ('engineer', 'Engineering team member'),
    ('product', 'Product team member')
ON CONFLICT (name) DO NOTHING;

-- Insert default permissions
INSERT INTO permissions (name, description, resource_type) VALUES 
    ('chat:read', 'View chat sessions', 'chat'),
    ('chat:write', 'Send chat messages', 'chat'),
    ('files:read', 'View files', 'files'),
    ('files:write', 'Upload and modify files', 'files'),
    ('files:delete', 'Delete files', 'files'),
    ('users:read', 'View user information', 'users'),
    ('users:write', 'Create and modify users', 'users'),
    ('users:delete', 'Delete users', 'users'),
    ('roles:read', 'View roles and permissions', 'roles'),
    ('roles:write', 'Create and modify roles', 'roles'),
    ('analytics:read', 'View analytics and reports', 'analytics'),
    ('admin:all', 'Full administrative access', 'admin')
ON CONFLICT (name) DO NOTHING;

-- Insert default admin user (password: admin123)
INSERT INTO users (username, email, full_name, password_hash, is_superuser) 
VALUES ('admin', 'admin@example.com', 'System Administrator', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8xqUx3QJlC', true)
ON CONFLICT (username) DO NOTHING;

-- Get admin user and role IDs for default assignments
DO $$
DECLARE
    admin_user_id UUID;
    admin_role_id UUID;
    admin_permission_id UUID;
BEGIN
    -- Get admin user ID
    SELECT id INTO admin_user_id FROM users WHERE username = 'admin';
    
    -- Get admin role ID
    SELECT id INTO admin_role_id FROM roles WHERE name = 'admin';
    
    -- Assign admin role to admin user
    INSERT INTO user_roles (user_id, role_id) 
    VALUES (admin_user_id, admin_role_id)
    ON CONFLICT (user_id, role_id) DO NOTHING;
    
    -- Give admin role all permissions
    FOR admin_permission_id IN SELECT id FROM permissions LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (admin_role_id, admin_permission_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    END LOOP;
    
    -- Give admin user access to all domains
    INSERT INTO domain_access (user_id, domain, access_level) VALUES 
        (admin_user_id, 'general', 'admin'),
        (admin_user_id, 'support', 'admin'),
        (admin_user_id, 'sales', 'admin'),
        (admin_user_id, 'engineering', 'admin'),
        (admin_user_id, 'product', 'admin')
    ON CONFLICT (user_id, domain) DO NOTHING;
END $$;

-- Insert some sample known issues for bug workflow testing
INSERT INTO known_issues (title, description, solution, severity, domain) VALUES 
    ('File upload timeout', 'Large file uploads timeout after 30 seconds', 'Increase timeout setting or use chunked upload', 'medium', 'support'),
    ('Memory leak in processing', 'Memory usage increases during bulk processing', 'Restart service every 24 hours, fix pending in next release', 'high', 'engineering'),
    ('Search performance slow', 'Vector search takes too long with large indices', 'Optimize FAISS index configuration', 'medium', 'engineering')
ON CONFLICT DO NOTHING; 