-- Multi-Domain RAG Schema Enhancement
-- This script adds domain support to the existing RAG Searcher database

-- Add domain support to existing tables
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS domain VARCHAR(50) DEFAULT 'general';
ALTER TABLE search_queries ADD COLUMN IF NOT EXISTS domain VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_domain VARCHAR(50) DEFAULT 'general';
ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_domains TEXT[] DEFAULT ARRAY['general'];
ALTER TABLE users ADD COLUMN IF NOT EXISTS domain_roles JSONB DEFAULT '{}';
ALTER TABLE files ADD COLUMN IF NOT EXISTS domain VARCHAR(50) DEFAULT 'general';

-- Create domain-specific configuration table
CREATE TABLE IF NOT EXISTS domain_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    embedding_model VARCHAR(100) DEFAULT 'nomic-embed-text',
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    specialized_prompts JSONB DEFAULT '{}',
    vector_index_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create domain permissions table
CREATE TABLE IF NOT EXISTS domain_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_name VARCHAR(50) REFERENCES domain_configs(domain_name) ON DELETE CASCADE,
    role_name VARCHAR(50) NOT NULL,
    permissions TEXT[] DEFAULT ARRAY['read'],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create domain data sources table
CREATE TABLE IF NOT EXISTS domain_data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_name VARCHAR(50) REFERENCES domain_configs(domain_name) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL, -- file, api, web, manual
    source_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default domains
INSERT INTO domain_configs (domain_name, display_name, description, specialized_prompts, vector_index_path) VALUES
('general', 'General Assistant', 'General purpose assistant for all queries', 
 '{"system_prompt": "You are a helpful assistant. Provide accurate and helpful information."}',
 './vector_index/general'),
('support', 'Support Assistant', 'Customer support and troubleshooting assistant', 
 '{"system_prompt": "You are a support assistant. Focus on troubleshooting, issue resolution, and providing step-by-step guidance. When helping with bugs, provide clear diagnostic steps and potential solutions."}',
 './vector_index/support'),
('sales', 'Sales Assistant', 'Sales enablement and product features assistant',
 '{"system_prompt": "You are a sales assistant. Focus on product capabilities, business value, competitive advantages, and compliance requirements. Help demonstrate ROI and address customer concerns."}',
 './vector_index/sales'),
('engineering', 'Engineering Assistant', 'Technical documentation and development assistant',
 '{"system_prompt": "You are an engineering assistant. Focus on technical accuracy, best practices, code examples, and architecture guidance. Provide detailed technical explanations and implementation details."}',
 './vector_index/engineering'),
('product', 'Product Assistant', 'Product management and planning assistant',
 '{"system_prompt": "You are a product assistant. Focus on user needs, product strategy, roadmap planning, and feature prioritization. Help with product decisions and user experience optimization."}',
 './vector_index/product')
ON CONFLICT (domain_name) DO NOTHING;

-- Insert default domain permissions
INSERT INTO domain_permissions (domain_name, role_name, permissions) VALUES
('general', 'user', ARRAY['read']),
('general', 'admin', ARRAY['read', 'write', 'admin']),
('support', 'user', ARRAY['read']),
('support', 'support_agent', ARRAY['read', 'write']),
('support', 'support_admin', ARRAY['read', 'write', 'admin']),
('sales', 'user', ARRAY['read']),
('sales', 'sales_rep', ARRAY['read', 'write']),
('sales', 'sales_manager', ARRAY['read', 'write', 'admin']),
('engineering', 'developer', ARRAY['read', 'write']),
('engineering', 'tech_lead', ARRAY['read', 'write', 'admin']),
('product', 'pm', ARRAY['read', 'write']),
('product', 'product_director', ARRAY['read', 'write', 'admin'])
ON CONFLICT DO NOTHING;

-- Update admin user to have access to all domains
UPDATE users SET 
    allowed_domains = ARRAY['general', 'support', 'sales', 'engineering', 'product'],
    domain_roles = '{
        "general": ["admin"],
        "support": ["support_admin"], 
        "sales": ["sales_manager"],
        "engineering": ["tech_lead"],
        "product": ["product_director"]
    }'::jsonb
WHERE username = 'admin';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_embeddings_domain ON embeddings(domain);
CREATE INDEX IF NOT EXISTS idx_search_queries_domain ON search_queries(domain);
CREATE INDEX IF NOT EXISTS idx_files_domain ON files(domain);
CREATE INDEX IF NOT EXISTS idx_users_primary_domain ON users(primary_domain);
CREATE INDEX IF NOT EXISTS idx_domain_configs_active ON domain_configs(is_active);

-- Create trigger for domain_configs updated_at
CREATE OR REPLACE FUNCTION update_domain_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_domain_configs_updated_at 
    BEFORE UPDATE ON domain_configs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_domain_configs_updated_at();

COMMIT; 