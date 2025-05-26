'use client';

import React, { useState } from 'react';
import { 
  Building2, 
  CreditCard, 
  Settings, 
  X,
  Check,
  AlertCircle
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { Organization } from '../../types';
import { apiClient } from '../../utils/api';

interface OrganizationSettingsProps {
  organization: Organization;
  onClose: () => void;
  onOrganizationUpdate: (organization: Organization) => void;
}

const OrganizationSettings: React.FC<OrganizationSettingsProps> = ({ 
  organization, 
  onClose, 
  onOrganizationUpdate 
}) => {
  const [activeTab, setActiveTab] = useState('general');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Organization form state
  const [orgForm, setOrgForm] = useState({
    name: organization.name,
    description: organization.description || '',
    website: organization.website || '',
    industry: organization.industry || '',
  });

  const handleOrganizationUpdate = async () => {
    if (!orgForm.name.trim()) {
      setError('Organization name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.updateOrganization(organization.id, {
        name: orgForm.name,
        description: orgForm.description,
        website: orgForm.website,
        industry: orgForm.industry,
      });

      if (response.success) {
        setSuccess('Organization updated successfully');
        onOrganizationUpdate(response.data);
      } else {
        const errorMessage = typeof response.message === 'string' 
          ? response.message 
          : 'Failed to update organization';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Failed to update organization:', error);
      setError('Failed to update organization');
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'general', label: 'General', icon: <Building2 className="h-4 w-4" /> },
    { id: 'billing', label: 'Billing & Usage', icon: <CreditCard className="h-4 w-4" /> },
  ];

  const renderGeneralTab = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Organization Information</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Organization Name
            </label>
            <Input
              type="text"
              value={orgForm.name}
              onChange={(e) => setOrgForm(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Enter organization name"
              icon={<Building2 className="h-4 w-4" />}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={orgForm.description}
              onChange={(e) => setOrgForm(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe your organization"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Website
            </label>
            <Input
              type="url"
              value={orgForm.website}
              onChange={(e) => setOrgForm(prev => ({ ...prev, website: e.target.value }))}
              placeholder="https://yourcompany.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Industry
            </label>
            <select
              value={orgForm.industry}
              onChange={(e) => setOrgForm(prev => ({ ...prev, industry: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select an industry</option>
              <option value="technology">Technology</option>
              <option value="healthcare">Healthcare</option>
              <option value="finance">Finance</option>
              <option value="education">Education</option>
              <option value="retail">Retail</option>
              <option value="manufacturing">Manufacturing</option>
              <option value="consulting">Consulting</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Organization Slug
            </label>
            <Input
              type="text"
              value={organization.slug}
              disabled
              className="bg-gray-50"
            />
            <p className="text-xs text-gray-500 mt-1">Organization slug cannot be changed</p>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={handleOrganizationUpdate} disabled={loading}>
          {loading ? 'Updating...' : 'Update Organization'}
        </Button>
      </div>
    </div>
  );

  const renderBillingTab = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Current Plan</h3>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h4 className="text-lg font-semibold text-gray-900 capitalize">
                  {organization.subscription_tier} Plan
                </h4>
                <p className="text-gray-500">
                  {organization.subscription_tier === 'basic' && 'Perfect for small teams'}
                  {organization.subscription_tier === 'professional' && 'Great for growing businesses'}
                  {organization.subscription_tier === 'enterprise' && 'Full-featured for large organizations'}
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-gray-900">
                  {organization.subscription_tier === 'basic' && '$0'}
                  {organization.subscription_tier === 'professional' && '$29'}
                  {organization.subscription_tier === 'enterprise' && '$99'}
                </p>
                <p className="text-sm text-gray-500">per month</p>
              </div>
            </div>
            
            <div className="border-t border-gray-200 pt-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-500">Team Members</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {organization.member_count} / {organization.max_users}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Domains</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {organization.domain_count} / {organization.max_domains}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Storage</p>
                  <p className="text-lg font-semibold text-gray-900">
                    0 GB / {organization.max_storage_gb} GB
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Available Plans</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Basic Plan */}
          <Card className={organization.subscription_tier === 'basic' ? 'ring-2 ring-blue-500' : ''}>
            <CardContent className="p-6">
              <div className="text-center">
                <h4 className="text-lg font-semibold text-gray-900">Basic</h4>
                <p className="text-3xl font-bold text-gray-900 mt-2">$0</p>
                <p className="text-gray-500">per month</p>
              </div>
              <ul className="mt-6 space-y-3">
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  Up to 10 team members
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  3 domains
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  10 GB storage
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  Basic support
                </li>
              </ul>
              <Button 
                variant={organization.subscription_tier === 'basic' ? 'outline' : 'primary'}
                className="w-full mt-6"
                disabled={organization.subscription_tier === 'basic'}
              >
                {organization.subscription_tier === 'basic' ? 'Current Plan' : 'Downgrade'}
              </Button>
            </CardContent>
          </Card>

          {/* Professional Plan */}
          <Card className={organization.subscription_tier === 'professional' ? 'ring-2 ring-blue-500' : ''}>
            <CardContent className="p-6">
              <div className="text-center">
                <h4 className="text-lg font-semibold text-gray-900">Professional</h4>
                <p className="text-3xl font-bold text-gray-900 mt-2">$29</p>
                <p className="text-gray-500">per month</p>
              </div>
              <ul className="mt-6 space-y-3">
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  Up to 50 team members
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  10 domains
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  100 GB storage
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  Priority support
                </li>
              </ul>
              <Button 
                variant={organization.subscription_tier === 'professional' ? 'outline' : 'primary'}
                className="w-full mt-6"
                disabled={organization.subscription_tier === 'professional'}
              >
                {organization.subscription_tier === 'professional' ? 'Current Plan' : 'Upgrade'}
              </Button>
            </CardContent>
          </Card>

          {/* Enterprise Plan */}
          <Card className={organization.subscription_tier === 'enterprise' ? 'ring-2 ring-blue-500' : ''}>
            <CardContent className="p-6">
              <div className="text-center">
                <h4 className="text-lg font-semibold text-gray-900">Enterprise</h4>
                <p className="text-3xl font-bold text-gray-900 mt-2">$99</p>
                <p className="text-gray-500">per month</p>
              </div>
              <ul className="mt-6 space-y-3">
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  Up to 1000 team members
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  50 domains
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  1000 GB storage
                </li>
                <li className="flex items-center text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500 mr-2" />
                  24/7 dedicated support
                </li>
              </ul>
              <Button 
                variant={organization.subscription_tier === 'enterprise' ? 'outline' : 'primary'}
                className="w-full mt-6"
                disabled={organization.subscription_tier === 'enterprise'}
              >
                {organization.subscription_tier === 'enterprise' ? 'Current Plan' : 'Upgrade'}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <Settings className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">Organization Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center">
            <AlertCircle className="h-5 w-5 text-red-600 mr-3" />
            <span className="text-red-800">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-600 hover:text-red-800">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {success && (
          <div className="mx-6 mt-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center">
            <Check className="h-5 w-5 text-green-600 mr-3" />
            <span className="text-green-800">{success}</span>
            <button onClick={() => setSuccess(null)} className="ml-auto text-green-600 hover:text-green-800">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {activeTab === 'general' && renderGeneralTab()}
          {activeTab === 'billing' && renderBillingTab()}
        </div>
      </div>
    </div>
  );
};

export default OrganizationSettings; 