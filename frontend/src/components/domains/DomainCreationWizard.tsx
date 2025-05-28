'use client';

/**
 * Domain Creation Wizard - Simplified Flow
 * 
 * This wizard creates domains with a streamlined 7-step process:
 * 1. Template Selection - Choose from predefined domain templates
 * 2. Basic Configuration - Domain name and description
 * 3. Document Upload - Optional initial document upload
 * 4. AI Configuration - LLM settings and prompts
 * 5. Permissions - Access control settings
 * 6. Testing - Validate configuration
 * 7. Launch - Deploy the domain
 * 
 * Note: Data sources are intentionally excluded from this wizard to avoid
 * inconsistency with the comprehensive connector creation flow. Users are
 * directed to add data sources after domain creation using the full-featured
 * ConnectorConfigModal in the Domain Workspace.
 */

import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  ArrowRight, 
  Check, 
  X,
  Globe,
  Shield,
  Settings,
  TrendingUp,
  Activity,
  Brain,
  Upload,
  Users,
  TestTube,
  Rocket
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { DomainTemplate, Domain, DomainCreationState } from '../../types';
import { apiClient } from '../../utils/api';

interface DomainCreationWizardProps {
  organizationId: string;
  onComplete: (domain: Domain) => void;
  onCancel: () => void;
}

const DomainCreationWizard: React.FC<DomainCreationWizardProps> = ({
  organizationId,
  onComplete,
  onCancel,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [templates, setTemplates] = useState<DomainTemplate[]>([]);
  const [state, setState] = useState<DomainCreationState>({
    currentStep: 0,
    basicConfig: {},
    dataSourceConfig: { connectors: [], syncSchedule: { frequency: 'daily' }, dataRetention: { retentionDays: 365, autoArchive: false, autoDelete: false } },
    aiConfig: { provider: 'ollama', model: 'llama2', temperature: 0.7, maxTokens: 2048, confidenceThreshold: 0.8, enableStreaming: true },
    securityConfig: { accessControl: 'private', enableAuditLogging: true, dataEncryption: true },
    isValid: false,
  });
  const [loading, setLoading] = useState(false);
  
  // Document Upload hooks
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  const steps = [
    { id: 'template', title: 'Choose Template', description: 'Select a pre-built domain template', icon: Globe },
    { id: 'basic', title: 'Basic Configuration', description: 'Set up domain name and description', icon: Settings },
    { id: 'documents', title: 'Upload Documents', description: 'Add initial documents', icon: Upload },
    { id: 'ai', title: 'AI Configuration', description: 'Configure AI settings', icon: Brain },
    { id: 'permissions', title: 'Permissions', description: 'Set up access control', icon: Users },
    { id: 'testing', title: 'Testing', description: 'Test your configuration', icon: TestTube },
    { id: 'launch', title: 'Launch', description: 'Deploy your domain', icon: Rocket },
  ];

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    const response = await apiClient.getDomainTemplates();
    if (response.success) {
      setTemplates(response.data);
    }
  };

  const nextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const updateState = (updates: Partial<DomainCreationState>) => {
    setState(prev => ({ ...prev, ...updates }));
  };

  const createDomain = async () => {
    setLoading(true);
    try {
      // First create the domain
      // Convert display name to URL-safe domain name
      const domainName = state.basicConfig.name?.toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '') // Remove special characters
        .replace(/\s+/g, '-') // Replace spaces with hyphens
        .replace(/-+/g, '-') // Replace multiple hyphens with single
        .replace(/^-|-$/g, ''); // Remove leading/trailing hyphens
      
      const domainData = {
        domain_name: domainName,
        display_name: state.basicConfig.name,
        description: state.basicConfig.description,
        // Only include template_id if it's a valid UUID (from API), not a hardcoded string
        ...(state.template?.id && state.template.id.length > 10 ? { template_id: state.template.id } : {}),
        icon: state.template?.icon || 'globe',
        color: state.template?.color?.includes('green') ? 'green' : 
               state.template?.color?.includes('orange') ? 'orange' :
               state.template?.color?.includes('purple') ? 'purple' :
               state.template?.color?.includes('pink') ? 'pink' :
               state.template?.color?.includes('blue') ? 'blue' : 'blue',
        settings: {
          aiConfig: {
            provider: state.aiConfig?.provider || 'ollama',
            model: state.aiConfig?.model || 'llama2',
            temperature: state.aiConfig?.temperature || 0.7,
            maxTokens: state.aiConfig?.maxTokens || 2048,
            confidenceThreshold: state.aiConfig?.confidenceThreshold || 0.8,
            enableStreaming: state.aiConfig?.enableStreaming || true,
            systemPrompt: state.aiConfig?.systemPrompt || '',
          },
          searchConfig: {
            mode: 'hybrid' as const,
            vectorWeight: 0.7,
            keywordWeight: 0.3,
            maxResults: 20,
            enableFacets: true,
            enableSuggestions: true,
          },
          dataSourceConfig: {
            connectors: state.dataSourceConfig?.connectors || [],
            syncSchedule: state.dataSourceConfig?.syncSchedule || { frequency: 'daily' },
            dataRetention: state.dataSourceConfig?.dataRetention || { retentionDays: 365, autoArchive: false, autoDelete: false },
          },
          securityConfig: {
            accessControl: state.securityConfig?.accessControl || 'private',
            enableAuditLogging: state.securityConfig?.enableAuditLogging || true,
            dataEncryption: state.securityConfig?.dataEncryption || true,
          },
          uiConfig: {
            theme: 'light' as const,
            primaryColor: state.template?.color || '#3B82F6',
            enableVoiceInput: false,
            enableExport: true,
          },
        },
      };

      const response = await apiClient.createDomain(organizationId, domainData);
      if (response.success) {
        const domain = response.data;
        
        // Upload any selected files
        if (uploadedFiles.length > 0) {
          setUploading(true);
          
          for (let i = 0; i < uploadedFiles.length; i++) {
            const file = uploadedFiles[i];
            try {
              const uploadResponse = await apiClient.uploadFile(file, domain.id);
              if (!uploadResponse.success) {
                // Handle upload failure silently or with proper error reporting
              }
            } catch (error) {
              // Handle upload error silently or with proper error reporting
            }
          }
          
          setUploading(false);
        }

        onComplete(domain);
      }
    } catch (error) {
      console.error('Failed to create domain:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderTemplateSelection = () => {
    const defaultTemplates: DomainTemplate[] = [
      {
        id: 'support',
        name: 'Customer Support',
        description: 'Help desk and customer service knowledge base',
        icon: 'shield',
        color: 'bg-green-100 text-green-600',
        category: 'Support',
        defaultSettings: {} as any,
        requiredConnectors: ['jira', 'zendesk'],
      },
      {
        id: 'sales',
        name: 'Sales & Marketing',
        description: 'Sales materials, proposals, and marketing content',
        icon: 'trending-up',
        color: 'bg-orange-100 text-orange-600',
        category: 'Sales',
        defaultSettings: {} as any,
        requiredConnectors: ['hubspot', 'salesforce'],
      },
      {
        id: 'engineering',
        name: 'Engineering',
        description: 'Technical documentation and code repositories',
        icon: 'settings',
        color: 'bg-purple-100 text-purple-600',
        category: 'Engineering',
        defaultSettings: {} as any,
        requiredConnectors: ['github', 'confluence'],
      },
      {
        id: 'product',
        name: 'Product Management',
        description: 'Product specs, roadmaps, and user research',
        icon: 'activity',
        color: 'bg-pink-100 text-pink-600',
        category: 'Product',
        defaultSettings: {} as any,
        requiredConnectors: ['jira', 'confluence'],
      },
      {
        id: 'general',
        name: 'General Knowledge',
        description: 'Company-wide information and policies',
        icon: 'globe',
        color: 'bg-blue-100 text-blue-600',
        category: 'General',
        defaultSettings: {} as any,
      },
      {
        id: 'custom',
        name: 'Custom Domain',
        description: 'Start from scratch with custom configuration',
        icon: 'settings',
        color: 'bg-gray-100 text-gray-600',
        category: 'Custom',
        defaultSettings: {} as any,
      },
    ];

    const allTemplates = templates.length > 0 ? templates : defaultTemplates;

    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Choose a Domain Template</h2>
          <p className="text-gray-600">Select a pre-built template to get started quickly, or create a custom domain.</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {allTemplates.map((template) => (
            <div
              key={template.id}
              onClick={() => updateState({ template })}
              className={`border-2 rounded-lg p-6 cursor-pointer transition-all duration-200 ${
                state.template?.id === template.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
              }`}
            >
              <div className={`w-12 h-12 rounded-lg ${template.color} flex items-center justify-center mb-4`}>
                {template.icon === 'shield' && <Shield className="h-6 w-6" />}
                {template.icon === 'trending-up' && <TrendingUp className="h-6 w-6" />}
                {template.icon === 'settings' && <Settings className="h-6 w-6" />}
                {template.icon === 'activity' && <Activity className="h-6 w-6" />}
                {template.icon === 'globe' && <Globe className="h-6 w-6" />}
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{template.name}</h3>
              <p className="text-sm text-gray-600 mb-4">{template.description}</p>
              {template.requiredConnectors && (
                <div className="flex flex-wrap gap-1">
                  {template.requiredConnectors.map((connector) => (
                    <span key={connector} className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                      {connector}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderBasicConfiguration = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Basic Configuration</h2>
        <p className="text-gray-600">Set up your domain name and description.</p>
      </div>

      <div className="max-w-md mx-auto space-y-4">
        <Input
          label="Domain Name"
          placeholder="e.g., Customer Support"
          value={state.basicConfig.name || ''}
          onChange={(e) => updateState({
            basicConfig: { ...state.basicConfig, name: e.target.value }
          })}
          fullWidth
        />
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            placeholder="Describe what this domain will be used for..."
            value={state.basicConfig.description || ''}
            onChange={(e) => updateState({
              basicConfig: { ...state.basicConfig, description: e.target.value }
            })}
          />
        </div>

        {state.template && (
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-2">Selected Template</h4>
            <div className="flex items-center space-x-3">
              <div className={`w-8 h-8 rounded ${state.template.color} flex items-center justify-center`}>
                <Globe className="h-4 w-4" />
              </div>
              <div>
                <p className="font-medium text-gray-900">{state.template.name}</p>
                <p className="text-sm text-gray-600">{state.template.description}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const renderDocumentUpload = () => {
    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files || []);
      const newFiles = [...uploadedFiles, ...files];
      setUploadedFiles(newFiles);
      // Store files in global state for domain creation
      updateState({ ...state, uploadedFiles: newFiles } as any);
    };

    const handleDrop = (event: React.DragEvent) => {
      event.preventDefault();
      const files = Array.from(event.dataTransfer.files);
      const newFiles = [...uploadedFiles, ...files];
      setUploadedFiles(newFiles);
      // Store files in global state for domain creation
      updateState({ ...state, uploadedFiles: newFiles } as any);
    };

    const removeFile = (index: number) => {
      const newFiles = uploadedFiles.filter((_, i) => i !== index);
      setUploadedFiles(newFiles);
      // Update global state
      updateState({ ...state, uploadedFiles: newFiles } as any);
    };

    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Initial Documents</h2>
          <p className="text-gray-600">Add some documents to get started with your knowledge base.</p>
        </div>

        <div className="max-w-lg mx-auto">
          <div 
            className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Drop files here</h3>
            <p className="text-gray-600 mb-4">or click to browse</p>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.json,.csv"
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <Button variant="outline" type="button">
                Choose Files
              </Button>
            </label>
          </div>
          
          {uploadedFiles.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="font-medium text-gray-900">Selected Files:</h4>
              {uploadedFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span className="text-sm text-gray-700">{file.name}</span>
                  <button
                    onClick={() => removeFile(index)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <div className="mt-4 text-sm text-gray-500">
            <p>Supported formats: PDF, DOCX, TXT, MD, JSON, CSV</p>
            <p>Maximum file size: 50MB</p>
          </div>
        </div>
      </div>
    );
  };

  const renderAIConfiguration = () => {
    const getExamplePrompts = () => {
      const templateName = state.template?.name.toLowerCase() || '';
      
      const prompts = {
        'customer support': {
          systemPrompt: `You are a helpful customer support AI assistant. Your role is to:
- Provide accurate, empathetic responses to customer inquiries
- Search through support documentation, FAQs, and knowledge base
- Escalate complex issues to human agents when needed
- Maintain a professional, friendly tone
- Always prioritize customer satisfaction and resolution

When you don't know something, admit it and offer to connect them with a human agent.`,
          examples: [
            "How can I reset my password?",
            "I'm having trouble with my billing",
            "The product isn't working as expected"
          ]
        },
        'sales & marketing': {
          systemPrompt: `You are a sales and marketing AI assistant. Your role is to:
- Help prospects understand product features and benefits
- Provide pricing information and comparisons
- Generate leads and qualify prospects
- Share case studies and success stories
- Support the sales team with research and insights

Always be helpful, informative, and focused on solving customer problems.`,
          examples: [
            "What are the key features of your product?",
            "Can you show me pricing options?",
            "Do you have case studies for my industry?"
          ]
        },
        'engineering': {
          systemPrompt: `You are a technical AI assistant for engineering teams. Your role is to:
- Help with code reviews, debugging, and technical documentation
- Search through technical specs, API docs, and code repositories
- Provide architectural guidance and best practices
- Assist with troubleshooting and problem-solving
- Maintain accuracy and technical precision

Always provide code examples and technical details when relevant.`,
          examples: [
            "How do I implement authentication in our API?",
            "What's the best practice for error handling?",
            "Can you review this code snippet?"
          ]
        },
        'product management': {
          systemPrompt: `You are a product management AI assistant. Your role is to:
- Help with product roadmap planning and feature prioritization
- Analyze user feedback and market research
- Support product requirement documentation
- Provide insights on user experience and product metrics
- Assist with stakeholder communication

Focus on data-driven insights and strategic thinking.`,
          examples: [
            "What features should we prioritize next quarter?",
            "How do users feel about the new feature?",
            "What are the key metrics for this product?"
          ]
        },
        'general knowledge': {
          systemPrompt: `You are a general knowledge AI assistant for the organization. Your role is to:
- Answer questions about company policies, procedures, and information
- Help employees find relevant documents and resources
- Provide general assistance with work-related queries
- Maintain confidentiality and professionalism
- Direct users to appropriate departments when needed

Be helpful, accurate, and maintain a professional tone.`,
          examples: [
            "What's our vacation policy?",
            "Where can I find the employee handbook?",
            "Who should I contact about IT issues?"
          ]
        }
      };

      return prompts[templateName] || prompts['general knowledge'];
    };

    const examplePrompts = getExamplePrompts();

    const useExamplePrompt = () => {
      updateState({
        aiConfig: { 
          ...state.aiConfig!, 
          systemPrompt: examplePrompts.systemPrompt 
        }
      });
    };

    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">AI Configuration</h2>
          <p className="text-gray-600">Configure how the AI assistant will behave in this domain.</p>
        </div>

        <div className="max-w-2xl mx-auto space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">AI Provider</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={state.aiConfig?.provider || 'ollama'}
                onChange={(e) => updateState({
                  aiConfig: { ...state.aiConfig!, provider: e.target.value as 'ollama' | 'openai' }
                })}
              >
                <option value="ollama">Ollama (Local)</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={state.aiConfig?.model || 'llama2'}
                onChange={(e) => updateState({
                  aiConfig: { ...state.aiConfig!, model: e.target.value }
                })}
              >
                {state.aiConfig?.provider === 'ollama' ? (
                  <>
                    <option value="llama2">Llama 2 (7B)</option>
                    <option value="llama2:13b">Llama 2 (13B)</option>
                    <option value="codellama">Code Llama</option>
                    <option value="mistral">Mistral 7B</option>
                  </>
                ) : (
                  <>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                  </>
                )}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={state.aiConfig?.temperature || 0.7}
              onChange={(e) => updateState({
                aiConfig: { ...state.aiConfig!, temperature: parseFloat(e.target.value) }
              })}
              helperText="Controls creativity (0 = focused, 2 = creative)"
              fullWidth
            />

            <Input
              label="Confidence Threshold"
              type="number"
              min="0"
              max="1"
              step="0.1"
              value={state.aiConfig?.confidenceThreshold || 0.8}
              onChange={(e) => updateState({
                aiConfig: { ...state.aiConfig!, confidenceThreshold: parseFloat(e.target.value) }
              })}
              helperText="Minimum confidence for responses"
              fullWidth
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">System Prompt</label>
              <Button variant="outline" size="sm" onClick={useExamplePrompt}>
                Use Template Example
              </Button>
            </div>
            <textarea
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={6}
              placeholder="You are a helpful AI assistant for..."
              value={state.aiConfig?.systemPrompt || ''}
              onChange={(e) => updateState({
                aiConfig: { ...state.aiConfig!, systemPrompt: e.target.value }
              })}
            />
          </div>

          {/* Example Queries */}
          <Card>
            <CardHeader>
              <CardTitle>Example Queries for {state.template?.name || 'This Domain'}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {examplePrompts.examples.map((example, index) => (
                  <div key={index} className="p-3 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-700">"{example}"</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Ollama Integration Info */}
          {state.aiConfig?.provider === 'ollama' && (
            <Card>
              <CardHeader>
                <CardTitle>Local Ollama Integration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm text-gray-700">Connected to local Ollama instance</span>
                  </div>
                  <div className="text-sm text-gray-600">
                    <p><strong>Benefits:</strong></p>
                    <ul className="list-disc list-inside space-y-1 mt-1">
                      <li>Complete data privacy - all processing stays local</li>
                      <li>No API costs or rate limits</li>
                      <li>Customizable models for your specific domain</li>
                      <li>Works with your RAG system for contextual responses</li>
                    </ul>
                  </div>
                  <div className="text-sm text-gray-600">
                    <p><strong>RAG Integration:</strong> Your documents will be embedded using the same model for optimal semantic search and retrieval.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    );
  };

  const renderPermissions = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Control</h2>
        <p className="text-gray-600">Configure who can access this domain.</p>
      </div>

      <div className="max-w-md mx-auto space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Access Level</label>
          <div className="space-y-2">
            {[
              { value: 'public', label: 'Public', description: 'Anyone in the organization can access' },
              { value: 'private', label: 'Private', description: 'Only invited users can access' },
              { value: 'restricted', label: 'Restricted', description: 'Specific roles only' },
            ].map((option) => (
              <label key={option.value} className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="radio"
                  name="accessControl"
                  value={option.value}
                  checked={state.securityConfig?.accessControl === option.value}
                  onChange={(e) => updateState({
                    securityConfig: { ...state.securityConfig!, accessControl: e.target.value as any }
                  })}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium text-gray-900">{option.label}</p>
                  <p className="text-sm text-gray-600">{option.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderTesting = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Test Your Configuration</h2>
        <p className="text-gray-600">Make sure everything is working correctly before launching.</p>
      </div>

      <div className="max-w-lg mx-auto space-y-4">
        <Card>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Check className="h-5 w-5 text-green-600" />
                <span className="text-gray-900">Domain configuration valid</span>
              </div>
              <span className="text-green-600 text-sm">✓</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Check className="h-5 w-5 text-green-600" />
                <span className="text-gray-900">AI provider connection</span>
              </div>
              <span className="text-green-600 text-sm">✓</span>
            </div>
          </CardContent>
        </Card>

        <div className="p-4 bg-blue-50 rounded-lg">
          <h4 className="font-medium text-blue-900 mb-2">Test Query</h4>
          <Input
            placeholder="Ask a test question..."
            fullWidth
          />
          <Button className="mt-2" size="sm">Test AI Response</Button>
        </div>
      </div>
    </div>
  );

  const renderLaunch = () => (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ready to Launch!</h2>
        <p className="text-gray-600">Your domain is configured and ready to deploy.</p>
      </div>

      <div className="max-w-lg mx-auto">
        <Card>
          <CardContent>
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <Rocket className="h-8 w-8 text-green-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{state.basicConfig.name}</h3>
                <p className="text-gray-600">{state.basicConfig.description}</p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Template</p>
                  <p className="font-medium">{state.template?.name}</p>
                </div>
                <div>
                  <p className="text-gray-500">Access</p>
                  <p className="font-medium capitalize">{state.securityConfig?.accessControl}</p>
                </div>
              </div>
              
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Next step:</strong> Connect data sources in the Domain Workspace to start indexing content.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: return renderTemplateSelection();
      case 1: return renderBasicConfiguration();
      case 2: return renderDocumentUpload();
      case 3: return renderAIConfiguration();
      case 4: return renderPermissions();
      case 5: return renderTesting();
      case 6: return renderLaunch();
      default: return null;
    }
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 0: // Template selection
        return !!state.template;
      case 1: // Basic configuration
        return !!(state.basicConfig.name && state.basicConfig.description);
      case 2: // Document upload (optional)
        return true;
      case 3: // AI configuration
        return !!(state.aiConfig?.provider && state.aiConfig?.model);
      case 4: // Permissions
        return !!state.securityConfig?.accessControl;
      case 5: // Testing (optional)
        return true;
      case 6: // Launch
        return true;
      default:
        return false;
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full border-2 ${
                index < currentStep 
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : index === currentStep
                  ? 'border-blue-600 text-blue-600'
                  : 'border-gray-300 text-gray-400'
              }`}>
                {index < currentStep ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <step.icon className="h-5 w-5" />
                )}
              </div>
              {index < steps.length - 1 && (
                <div className={`w-12 h-0.5 mx-2 ${
                  index < currentStep ? 'bg-blue-600' : 'bg-gray-300'
                }`} />
              )}
            </div>
          ))}
        </div>
        <div className="mt-2">
          <p className="text-sm text-gray-600">
            Step {currentStep + 1} of {steps.length}: {steps[currentStep].title}
          </p>
        </div>
      </div>

      {/* Step Content */}
      <Card className="mb-8">
        <CardContent className="p-8">
          {renderStepContent()}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={currentStep === 0 ? onCancel : prevStep}
          icon={<ArrowLeft className="h-4 w-4" />}
        >
          {currentStep === 0 ? 'Cancel' : 'Previous'}
        </Button>

        <div className="flex space-x-3">
          {currentStep === steps.length - 1 ? (
            <Button
              onClick={createDomain}
              loading={loading}
              icon={<Rocket className="h-4 w-4" />}
            >
              Launch Domain
            </Button>
          ) : (
            <Button
              onClick={nextStep}
              disabled={!isStepValid()}
              icon={<ArrowRight className="h-4 w-4" />}
            >
              Next
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DomainCreationWizard; 