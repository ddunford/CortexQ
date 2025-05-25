'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Users, 
  Globe, 
  BarChart3, 
  Settings, 
  Plus,
  TrendingUp,
  Activity,
  Clock,
  Shield,
  CreditCard,
  UserPlus
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import { Organization, Domain, Member, AnalyticsMetrics } from '../../types';
import { apiClient } from '../../utils/api';

interface OrganizationDashboardProps {
  organization: Organization;
  onCreateDomain: () => void;
  onManageTeam: () => void;
  onViewBilling: () => void;
}

const OrganizationDashboard: React.FC<OrganizationDashboardProps> = ({
  organization,
  onCreateDomain,
  onManageTeam,
  onViewBilling,
}) => {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, [organization.id]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [domainsResponse, analyticsResponse] = await Promise.all([
        apiClient.getDomains(organization.id),
        apiClient.getAnalytics(),
      ]);

      if (domainsResponse.success) {
        setDomains(domainsResponse.data);
      }

      if (analyticsResponse.success) {
        setAnalytics(analyticsResponse.data);
      }
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'draft': return 'text-yellow-600 bg-yellow-100';
      case 'configuring': return 'text-blue-600 bg-blue-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getDomainIcon = (domain: Domain) => {
    const iconMap: Record<string, React.ReactNode> = {
      support: <Shield className="h-5 w-5" />,
      sales: <TrendingUp className="h-5 w-5" />,
      engineering: <Settings className="h-5 w-5" />,
      product: <Activity className="h-5 w-5" />,
      general: <Globe className="h-5 w-5" />,
    };
    // Use domain_name or display_name, with fallback
    const domainKey = (domain.domain_name || domain.display_name || domain.name || '').toLowerCase();
    return iconMap[domainKey] || <Globe className="h-5 w-5" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="h-12 w-12 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
            <Building2 className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{organization.name}</h1>
            <p className="text-gray-500">{organization.description || 'Organization Dashboard'}</p>
          </div>
        </div>
        <div className="flex space-x-3">
          <Button variant="outline" onClick={onManageTeam} icon={<UserPlus className="h-4 w-4" />}>
            Manage Team
          </Button>
          <Button onClick={onCreateDomain} icon={<Plus className="h-4 w-4" />}>
            Create Domain
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardContent className="flex items-center">
            <div className="flex-shrink-0">
              <Globe className="h-8 w-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active Domains</p>
              <p className="text-2xl font-bold text-gray-900">
                {domains.filter(d => d.is_active).length}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center">
            <div className="flex-shrink-0">
              <Users className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Team Members</p>
              <p className="text-2xl font-bold text-gray-900">{organization.member_count}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center">
            <div className="flex-shrink-0">
              <BarChart3 className="h-8 w-8 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Queries</p>
              <p className="text-2xl font-bold text-gray-900">
                {analytics?.totalQueries.toLocaleString() || '0'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center">
            <div className="flex-shrink-0">
              <Activity className="h-8 w-8 text-orange-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active Users</p>
              <p className="text-2xl font-bold text-gray-900">
                {analytics?.activeUsers || '0'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Domains Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Domains</CardTitle>
            <Button variant="outline" size="sm" onClick={onCreateDomain}>
              <Plus className="h-4 w-4 mr-2" />
              New Domain
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {domains.length === 0 ? (
            <div className="text-center py-8">
              <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No domains yet</h3>
              <p className="text-gray-500 mb-4">Create your first domain to get started with AI-powered knowledge management.</p>
              <Button onClick={onCreateDomain}>Create Your First Domain</Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {domains.map((domain) => (
                <div
                  key={domain.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow duration-200 cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg ${domain.color || 'bg-blue-100'}`}>
                        {getDomainIcon(domain)}
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900">{domain.display_name || domain.name}</h4>
                        <p className="text-sm text-gray-500">{domain.description}</p>
                      </div>
                    </div>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(domain.is_active ? 'active' : 'inactive')}`}>
                      {domain.is_active ? 'active' : 'inactive'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm text-gray-500">
                    <span className="flex items-center">
                      <Clock className="h-4 w-4 mr-1" />
                      {new Date(domain.created_at).toLocaleDateString()}
                    </span>
                                          <span className="text-blue-600">
                        Domain
                      </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Activity & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analytics?.topQueries?.slice(0, 5).map((query, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{query.query}</p>
                    <p className="text-xs text-gray-500">{query.count} queries</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-900">{(query.averageConfidence * 100).toFixed(1)}%</p>
                    <p className="text-xs text-gray-500">confidence</p>
                  </div>
                </div>
              )) || (
                <p className="text-gray-500 text-center py-4">No recent activity</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button 
                variant="outline" 
                className="w-full justify-start" 
                onClick={onCreateDomain}
                icon={<Plus className="h-4 w-4" />}
              >
                Create New Domain
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start" 
                onClick={onManageTeam}
                icon={<Users className="h-4 w-4" />}
              >
                Invite Team Members
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start" 
                onClick={onViewBilling}
                icon={<CreditCard className="h-4 w-4" />}
              >
                View Billing & Usage
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start" 
                icon={<Settings className="h-4 w-4" />}
              >
                Organization Settings
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Subscription Status */}
      <Card>
        <CardHeader>
          <CardTitle>Subscription & Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm font-medium text-gray-500">Current Plan</p>
              <p className="text-lg font-semibold text-gray-900 capitalize">{organization.subscription_tier}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Domains Used</p>
              <p className="text-lg font-semibold text-gray-900">
                {domains.length} / {organization.max_domains}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Team Members</p>
              <p className="text-lg font-semibold text-gray-900">
                {organization.member_count} / {organization.max_users}
              </p>
            </div>
          </div>
          <div className="mt-4">
            <Button variant="outline" onClick={onViewBilling}>
              Manage Subscription
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default OrganizationDashboard; 