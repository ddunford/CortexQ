-- Migration script for Chat API service
-- Updates existing tables to match the new schema

-- Update chat_sessions table
ALTER TABLE chat_sessions 
    ADD COLUMN IF NOT EXISTS session_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS domain VARCHAR(50) DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS title VARCHAR(255),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update session_id from session_token if null
UPDATE chat_sessions SET session_id = session_token WHERE session_id IS NULL;

-- Make session_id unique and not null
UPDATE chat_sessions SET session_id = id::text WHERE session_id IS NULL;
ALTER TABLE chat_sessions ALTER COLUMN session_id SET NOT NULL;

-- Create unique constraint on session_id if not exists
DO $$
BEGIN
    ALTER TABLE chat_sessions ADD CONSTRAINT chat_sessions_session_id_unique UNIQUE (session_id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Update users table if missing columns
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS primary_domain VARCHAR(50) DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS allowed_domains JSONB DEFAULT '["general"]',
    ADD COLUMN IF NOT EXISTS domain_roles JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;

-- Update chat_messages table if missing columns
ALTER TABLE chat_messages 
    ADD COLUMN IF NOT EXISTS message_type VARCHAR(20);

-- Set default message types for existing messages
UPDATE chat_messages SET message_type = 'user' WHERE message_type IS NULL AND content LIKE '%user:%';
UPDATE chat_messages SET message_type = 'assistant' WHERE message_type IS NULL AND content LIKE '%assistant:%';
UPDATE chat_messages SET message_type = 'user' WHERE message_type IS NULL;

-- Add constraint for message_type
DO $$
BEGIN
    ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_message_type_check 
        CHECK (message_type IN ('user', 'assistant', 'system'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_active ON chat_sessions(is_active, last_activity);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_domain ON chat_sessions(domain);
CREATE INDEX IF NOT EXISTS idx_chat_messages_type ON chat_messages(message_type);

-- Insert demo users if not exist
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
ON CONFLICT (username) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    allowed_domains = EXCLUDED.allowed_domains,
    domain_roles = EXCLUDED.domain_roles,
    preferences = EXCLUDED.preferences;

-- Update admin user
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
ON CONFLICT (username) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    allowed_domains = EXCLUDED.allowed_domains,
    domain_roles = EXCLUDED.domain_roles,
    preferences = EXCLUDED.preferences;

COMMIT; 