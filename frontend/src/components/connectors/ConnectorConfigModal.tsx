import React, { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { ConnectorConfig, ApiResponse } from '../../types';
import { apiClient } from '../../utils/api';
import { 
  Settings, 
  Github, 
  Slack, 
  Globe, 
  TrendingUp, 
  Database,
  FileText,
  X,
  Check,
  AlertCircle
} from 'lucide-react';

interface ConnectorConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  domainId: string;
  onConnectorCreated?: (connector: ConnectorConfig) => void;
}

interface ConnectorTemplate {
  type: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  authType: 'oauth' | 'api_key' | 'none';
  fields: Array<{
    key: string;
    label: string;
    type: 'text' | 'password' | 'url' | 'select';
    required: boolean;
    placeholder?: string;
    options?: string[];
  }>;
}

const CONNECTOR_TEMPLATES: ConnectorTemplate[] = [
  {
    type: 'jira',
    name: 'Jira',
    description: 'Import tickets, issues, and project data from Atlassian Jira',
    icon: <Settings className="h-5 w-5" />,
    color: 'bg-blue-100 text-blue-600',
    authType: 'api_key',
    fields: [
      { key: 'base_url', label: 'Jira Base URL', type: 'url', required: true, placeholder: 'https://yourcompany.atlassian.net' },
      { key: 'username', label: 'Username/Email', type: 'text', required: true, placeholder: 'your-email@company.com' },
      { key: 'api_token', label: 'API Token', type: 'password', required: true, placeholder: 'Your Jira API token' },
      { key: 'project_keys', label: 'Project Keys', type: 'text', required: false, placeholder: 'PROJECT1,PROJECT2 (optional)' }
    ]
  },
  {
    type: 'github',
    name: 'GitHub',
    description: 'Import repositories, issues, pull requests, and documentation',
    icon: <Github className="h-5 w-5" />,
    color: 'bg-gray-100 text-gray-600',
    authType: 'api_key',
    fields: [
      { key: 'access_token', label: 'GitHub Token', type: 'password', required: true, placeholder: 'ghp_xxxxxxxxxxxx' },
      { key: 'owner', label: 'Repository Owner', type: 'text', required: true, placeholder: 'username or organization' },
      { key: 'repositories', label: 'Repositories', type: 'text', required: false, placeholder: 'repo1,repo2 (or leave empty for all)' }
    ]
  },
  {
    type: 'confluence',
    name: 'Confluence',
    description: 'Import wiki pages, spaces, and documentation',
    icon: <FileText className="h-5 w-5" />,
    color: 'bg-blue-100 text-blue-600',
    authType: 'api_key',
    fields: [
      { key: 'base_url', label: 'Confluence Base URL', type: 'url', required: true, placeholder: 'https://yourcompany.atlassian.net/wiki' },
      { key: 'username', label: 'Username/Email', type: 'text', required: true, placeholder: 'your-email@company.com' },
      { key: 'api_token', label: 'API Token', type: 'password', required: true, placeholder: 'Your Confluence API token' },
      { key: 'space_keys', label: 'Space Keys', type: 'text', required: false, placeholder: 'SPACE1,SPACE2 (optional)' }
    ]
  },
  {
    type: 'slack',
    name: 'Slack',
    description: 'Import conversations, channels, and shared files',
    icon: <Slack className="h-5 w-5" />,
    color: 'bg-green-100 text-green-600',
    authType: 'oauth',
    fields: [
      { key: 'workspace_url', label: 'Slack Workspace URL', type: 'url', required: true, placeholder: 'https://yourworkspace.slack.com' }
    ]
  },
  {
    type: 'hubspot',
    name: 'HubSpot',
    description: 'Import CRM data, contacts, deals, and marketing content',
    icon: <TrendingUp className="h-5 w-5" />,
    color: 'bg-orange-100 text-orange-600',
    authType: 'api_key',
    fields: [
      { key: 'api_key', label: 'HubSpot API Key', type: 'password', required: true, placeholder: 'Your HubSpot API key' },
      { key: 'portal_id', label: 'Portal ID', type: 'text', required: true, placeholder: 'Your HubSpot Portal ID' }
    ]
  },
  {
    type: 'web_scraper',
    name: 'Web Scraper',
    description: 'Crawl and index websites automatically',
    icon: <Globe className="h-5 w-5" />,
    color: 'bg-purple-100 text-purple-600',
    authType: 'api_key',
    fields: [
      { key: 'start_urls', label: 'Start URLs', type: 'text', required: true, placeholder: 'https://example.com,https://docs.example.com' },
      { key: 'max_depth', label: 'Max Crawl Depth', type: 'select', required: true, options: ['1', '2', '3', '4', '5'] },
      { key: 'max_pages', label: 'Max Pages', type: 'select', required: true, options: ['50', '100', '250', '500', '1000'] },
      { key: 'delay_ms', label: 'Delay (ms)', type: 'select', required: true, options: ['1000', '2000', '3000', '5000'] }
    ]
  }
];

export const ConnectorConfigModal: React.FC<ConnectorConfigModalProps> = ({
  isOpen,
  onClose,
  domainId,
  onConnectorCreated
}) => {
  const [step, setStep] = useState<'select' | 'configure' | 'test'>('select');
  const [selectedTemplate, setSelectedTemplate] = useState<ConnectorTemplate | null>(null);
  const [connectorName, setConnectorName] = useState('');
  const [connectorConfig, setConnectorConfig] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep('select');
      setSelectedTemplate(null);
      setConnectorName('');
      setConnectorConfig({});
      setError(null);
      setTestResult(null);
    }
  }, [isOpen]);

  const handleTemplateSelect = (template: ConnectorTemplate) => {
    setSelectedTemplate(template);
    setConnectorName(`${template.name} Integration`);
    setStep('configure');
    
    // Initialize config with default values
    const initialConfig: Record<string, string> = {};
    template.fields.forEach(field => {
      if (field.type === 'select' && field.options) {
        initialConfig[field.key] = field.options[0];
      } else {
        initialConfig[field.key] = '';
      }
    });
    setConnectorConfig(initialConfig);
  };

  const handleConfigChange = (key: string, value: string) => {
    setConnectorConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleBack = () => {
    if (step === 'configure') {
      setStep('select');
    } else if (step === 'test') {
      setStep('configure');
    }
  };

  const handleTestConnection = async () => {
    if (!selectedTemplate) return;
    
    setLoading(true);
    setError(null);
    setTestResult(null);
    
    try {
      // Create a temporary connector for testing
      const testConnector = {
        name: connectorName,
        connector_type: selectedTemplate.type,
        auth_config: {
          type: selectedTemplate.authType,
          credentials: connectorConfig
        },
        sync_config: {
          frequency: 'manual',
          batch_size: 10
        },
        is_enabled: false // Don't enable for testing
      };

      // For now, just validate the configuration locally
      // In a real implementation, you'd call a test endpoint
      const requiredFields = selectedTemplate.fields.filter(f => f.required);
      const missingFields = requiredFields.filter(f => !connectorConfig[f.key]);
      
      if (missingFields.length > 0) {
        setTestResult({
          success: false,
          message: `Missing required fields: ${missingFields.map(f => f.label).join(', ')}`
        });
      } else {
        setTestResult({
          success: true,
          message: 'Configuration looks good! Ready to create connector.'
        });
        setStep('test');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to test connection';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateConnector = async () => {
    if (!selectedTemplate) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const connectorData = {
        name: connectorName,
        connector_type: selectedTemplate.type,
        auth_config: {
          type: selectedTemplate.authType,
          ...connectorConfig // Include all the web scraper config fields
        },
        sync_config: {
          frequency: 'daily',
          schedule: '0 2 * * *', // 2 AM daily
          batch_size: 100,
          enable_incremental_sync: true
        },
        mapping_config: {},
        is_enabled: true
      };

      const response: ApiResponse<ConnectorConfig> = await apiClient.createConnector(domainId, connectorData);
      
      if (response.success && response.data) {
        onConnectorCreated?.(response.data);
        onClose();
      } else {
        const errorMessage = typeof response.message === 'string' 
          ? response.message 
          : 'Failed to create connector';
        setError(errorMessage);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create connector';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const renderSelectStep = () => (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Choose Integration Type</h3>
        <p className="text-gray-600">Select the type of data source you want to connect.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
        {CONNECTOR_TEMPLATES.map((template) => (
          <Card 
            key={template.type}
            className="cursor-pointer hover:shadow-md transition-all duration-200 hover:border-blue-300"
            onClick={() => handleTemplateSelect(template)}
          >
            <CardContent className="p-4">
              <div className="flex items-start space-x-3">
                <div className={`p-2 rounded-lg ${template.color}`}>
                  {template.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-gray-900 mb-1">{template.name}</h4>
                  <p className="text-sm text-gray-600 line-clamp-2">{template.description}</p>
                  <div className="mt-2 flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      template.authType === 'oauth' ? 'bg-green-100 text-green-700' :
                      template.authType === 'api_key' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {template.authType === 'oauth' ? 'OAuth' : 
                       template.authType === 'api_key' ? 'API Key' : 'No Auth'}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderConfigureStep = () => {
    if (!selectedTemplate) return null;
    
    return (
      <div className="space-y-4">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${selectedTemplate.color}`}>
            {selectedTemplate.icon}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{selectedTemplate.name} Configuration</h3>
            <p className="text-gray-600">{selectedTemplate.description}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Integration Name
            </label>
            <Input
              value={connectorName}
              onChange={(e) => setConnectorName(e.target.value)}
              placeholder="Enter a name for this integration"
            />
          </div>

          {selectedTemplate.fields.map((field) => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              {field.type === 'select' ? (
                <select 
                  value={connectorConfig[field.key] || ''}
                  onChange={(e) => handleConfigChange(field.key, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {field.options?.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              ) : (
                <Input
                  type={field.type}
                  value={connectorConfig[field.key] || ''}
                  onChange={(e) => handleConfigChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  required={field.required}
                />
              )}
            </div>
          ))}

          {selectedTemplate.authType === 'oauth' && (
            <div className="p-4 bg-blue-50 rounded-lg">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-blue-600" />
                <p className="text-sm text-blue-800">
                  OAuth authentication will be set up in the next step. You'll be redirected to {selectedTemplate.name} to authorize access.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderTestStep = () => (
    <div className="space-y-4">
      <div className="text-center">
        <div className={`mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4 ${
          testResult?.success ? 'bg-green-100' : 'bg-red-100'
        }`}>
          {testResult?.success ? (
            <Check className="h-6 w-6 text-green-600" />
          ) : (
            <AlertCircle className="h-6 w-6 text-red-600" />
          )}
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Connection Test</h3>
        <p className={`text-sm ${testResult?.success ? 'text-green-700' : 'text-red-700'}`}>
          {testResult?.message}
        </p>
      </div>

      {testResult?.success && (
        <div className="space-y-3">
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-2">Sync Configuration</h4>
            <div className="text-sm text-gray-600 space-y-1">
              <p><strong>Frequency:</strong> Daily at 2:00 AM</p>
              <p><strong>Batch Size:</strong> 100 records</p>
              <p><strong>Incremental Sync:</strong> Enabled</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Data Source Integration" size="lg">
      <div className="space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {step === 'select' && renderSelectStep()}
        {step === 'configure' && renderConfigureStep()}
        {step === 'test' && renderTestStep()}

        <div className="flex items-center justify-between pt-4 border-t">
          <div>
            {step !== 'select' && (
              <Button variant="outline" onClick={handleBack}>
                Back
              </Button>
            )}
          </div>
          
          <div className="flex space-x-3">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            
            {step === 'configure' && (
              <Button 
                onClick={handleTestConnection}
                loading={loading}
                disabled={!connectorName || !selectedTemplate}
              >
                Test Connection
              </Button>
            )}
            
            {step === 'test' && testResult?.success && (
              <Button 
                onClick={handleCreateConnector}
                loading={loading}
              >
                Create Integration
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}; 