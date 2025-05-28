-- Fix Connectors Data Inconsistency
-- This script helps diagnose and fix connector listing issues

-- 1. Check all connectors and their associations
SELECT 
    c.id,
    c.name,
    c.connector_type,
    c.organization_id,
    c.domain_id,
    c.is_enabled,
    c.created_at,
    o.name as org_name,
    od.domain_name
FROM connectors c
LEFT JOIN organizations o ON c.organization_id = o.id
LEFT JOIN organization_domains od ON c.domain_id = od.id
ORDER BY c.created_at DESC;

-- 2. Find orphaned connectors (connectors without valid org/domain)
SELECT 
    c.id,
    c.name,
    c.organization_id,
    c.domain_id,
    'Missing Organization' as issue
FROM connectors c
LEFT JOIN organizations o ON c.organization_id = o.id
WHERE o.id IS NULL

UNION ALL

SELECT 
    c.id,
    c.name,
    c.organization_id,
    c.domain_id,
    'Missing Domain' as issue
FROM connectors c
LEFT JOIN organization_domains od ON c.domain_id = od.id
WHERE od.id IS NULL;

-- 3. Check current organizations and domains
SELECT 
    o.id as org_id,
    o.name as org_name,
    o.slug,
    od.id as domain_id,
    od.domain_name
FROM organizations o
LEFT JOIN organization_domains od ON o.id = od.organization_id
ORDER BY o.created_at DESC;

-- 4. Find duplicate connector names within same domain
SELECT 
    domain_id,
    name,
    COUNT(*) as count
FROM connectors
GROUP BY domain_id, name
HAVING COUNT(*) > 1; 