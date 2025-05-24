-- Chat API Database Schema
-- Creates tables for chat sessions, messages, and enhanced user management

-- Create users table if not exists (enhanced version)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),
    primary_domain VARCHAR(50) DEFAULT 'general',
    allowed_domains JSONB DEFAULT '["general"]',
    domain_roles JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Create chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
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

-- Create chat_messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_active ON chat_sessions(is_active, last_activity);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_domain ON chat_sessions(domain);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_type ON chat_messages(message_type);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Insert demo user if not exists
INSERT INTO users (username, email, full_name, allowed_domains, domain_roles, preferences) VALUES
('demo_user', 'demo@example.com', 'Demo User', 
 '["general", "support", "sales", "engineering", "product"]',
 '{
   "general": ["user"],
   "support": ["user"],
   "sales": ["user"],
   "engineering": ["user"],
   "product": ["user"]
 }',
 '{"default_domain": "general", "theme": "light"}')
ON CONFLICT (username) DO NOTHING;

-- Insert admin user if not exists
INSERT INTO users (username, email, full_name, allowed_domains, domain_roles, preferences) VALUES
('admin', 'admin@example.com', 'Administrator', 
 '["general", "support", "sales", "engineering", "product"]',
 '{
   "general": ["admin"],
   "support": ["support_admin"],
   "sales": ["sales_manager"],
   "engineering": ["tech_lead"],
   "product": ["product_director"]
 }',
 '{"default_domain": "general", "theme": "dark"}')
ON CONFLICT (username) DO NOTHING;

-- Create trigger to update last_activity on message insert
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

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS trigger_update_session_activity ON chat_messages;
CREATE TRIGGER trigger_update_session_activity
    AFTER INSERT ON chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_session_activity();

COMMIT; 