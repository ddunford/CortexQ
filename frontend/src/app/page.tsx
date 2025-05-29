'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Globe, 
  Plus,
  Menu,
  X,
  User,
  LogOut,
  Settings,
  Bell,
  Search,
  ChevronDown,
  MessageCircle,
  Database,
  BarChart3,
  Shield
} from 'lucide-react';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Card from '../components/ui/Card';
import OrganizationDashboard from '../components/organization/OrganizationDashboard';
import TeamManagement from '../components/organization/TeamManagement';
import OrganizationSettings from '../components/organization/OrganizationSettings';
import UserProfile from '../components/auth/UserProfile';
import DomainCreationWizard from '../components/domains/DomainCreationWizard';
import DomainWorkspace from '../components/workspace/DomainWorkspace';
import { User as UserType, Organization, Domain } from '../types';
import { api } from '../utils/api';

type ViewType = 'organization' | 'domain-workspace' | 'create-domain';

interface AppState {
  currentView: ViewType;
  selectedDomain?: Domain;
  activeDomainSection?: 'chat' | 'sources' | 'analytics' | 'audit' | 'settings';
  user?: UserType;
  organization?: Organization;
  domains: Domain[];
  sidebarOpen: boolean;
  loading: boolean;
  showTeamManagement: boolean;
  showOrganizationSettings: boolean;
  showUserProfile: boolean;
  showUserDropdown: boolean;
}

export default function HomePage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [state, setState] = useState<AppState>({
    currentView: 'organization',
    activeDomainSection: 'chat',
    domains: [],
    sidebarOpen: true,
    loading: true,
    showTeamManagement: false,
    showOrganizationSettings: false,
    showUserProfile: false,
    showUserDropdown: false,
  });

  useEffect(() => {
    // Set up the unauthorized handler to log out on 401 responses
    api.setUnauthorizedHandler(() => {
      console.log('401 Unauthorized detected - logging out...');
      logout();
    });

    const token = localStorage.getItem('cortexq_token') || localStorage.getItem('rag_token');
    if (token) {
      api.setToken(token);
      setIsAuthenticated(true);
      loadUserData();
    }
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (state.showUserDropdown) {
        setState(prev => ({ ...prev, showUserDropdown: false }));
      }
    };

    if (state.showUserDropdown) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [state.showUserDropdown]);

  const loadUserData = async () => {
    setState(prev => ({ ...prev, loading: true }));
    try {
      const userResponse = await api.getCurrentUser();
      if (userResponse.success) {
        const user = userResponse.data;
        setState(prev => ({ ...prev, user }));

        // Load organizations - get the first one or create one
        const orgsResponse = await api.getOrganizations();
        if (orgsResponse.success && orgsResponse.data.length > 0) {
          const organization = orgsResponse.data[0];
          setState(prev => ({ ...prev, organization }));

          // Load domains
          const domainsResponse = await api.getDomains(organization.id);
          if (domainsResponse.success) {
            setState(prev => ({ ...prev, domains: domainsResponse.data }));
          }
        } else {
          // No organizations found - this indicates a data issue
          console.error('No organizations found for user. This may indicate a data issue.');
          console.log('Organizations response:', orgsResponse);
          setState(prev => ({ ...prev, organization: null, domains: [] }));
        }
      } else {
        // If user data fails to load, the unauthorized handler will logout if it's a 401
        console.error('Failed to load user data:', userResponse.message);
      }
    } catch (error) {
      console.error('Failed to load user data:', error);
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  const login = async (email: string, password: string) => {
    try {
      const response = await api.login(email, password);
      if (response.success) {
        api.setToken(response.data.access_token);
        setIsAuthenticated(true);
        loadUserData();
      }
    } catch (error) {
      console.error('Login error:', error);
    }
  };

  const logout = () => {
    api.clearToken();
    setIsAuthenticated(false);
    setState({
      currentView: 'organization',
      domains: [],
      sidebarOpen: true,
      loading: false,
      showTeamManagement: false,
      showOrganizationSettings: false,
      showUserProfile: false,
      showUserDropdown: false,
    });
  };

  const handleCreateDomain = () => {
    setState(prev => ({ ...prev, currentView: 'create-domain' }));
  };

  const handleDomainCreated = (domain: Domain) => {
    setState(prev => ({
      ...prev,
      domains: [...prev.domains, domain],
      currentView: 'domain-workspace',
      selectedDomain: domain,
    }));
  };

  const handleSelectDomain = (domain: Domain) => {
    setState(prev => ({
      ...prev,
      currentView: 'domain-workspace',
      selectedDomain: domain,
      activeDomainSection: 'chat'
    }));
  };

  const handleDomainSectionChange = (section: 'chat' | 'sources' | 'analytics' | 'audit' | 'settings') => {
    setState(prev => ({
      ...prev,
      activeDomainSection: section
    }));
  };

  const handleBackToOrganization = () => {
    setState(prev => ({
      ...prev,
      currentView: 'organization',
      selectedDomain: undefined,
      activeDomainSection: 'chat'
    }));
  };

  const handleManageTeam = () => {
    setState(prev => ({ ...prev, showTeamManagement: true }));
  };

  const handleViewBilling = () => {
    setState(prev => ({ ...prev, showOrganizationSettings: true }));
  };

  const handleShowUserProfile = () => {
    setState(prev => ({ ...prev, showUserProfile: true }));
  };

  const handleCloseModals = () => {
    setState(prev => ({
      ...prev,
      showTeamManagement: false,
      showOrganizationSettings: false,
      showUserProfile: false,
      showUserDropdown: false,
    }));
  };

  const handleUserUpdate = (updatedUser: UserType) => {
    setState(prev => ({ ...prev, user: updatedUser }));
  };

  const handleOrganizationUpdate = (updatedOrganization: Organization) => {
    setState(prev => ({ ...prev, organization: updatedOrganization }));
  };

  if (!isAuthenticated) {
    return <LoginForm onLogin={login} />;
  }

  if (state.loading && !state.user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cortex-primary"></div>
      </div>
    );
  }

  const renderSidebar = () => (
    <div className={`${state.sidebarOpen ? 'w-72' : 'w-20'} bg-white border-r border-gray-200 transition-all duration-300 flex flex-col shadow-sm`}>
      {/* Logo */}
      <div className="p-6 border-b border-gray-100">
        <div className="flex items-center">
          <div className="h-12 w-12 flex items-center justify-center">
            <img 
              src="/LogoIcon.png" 
              alt="CortexQ" 
              className="h-10 w-10"
              onError={(e) => {
                // Fallback to gradient icon if logo doesn't load
                e.currentTarget.style.display = 'none';
                const fallback = e.currentTarget.nextElementSibling as HTMLElement;
                if (fallback) fallback.classList.remove('hidden');
              }}
            />
                         <div className="hidden h-12 w-12 bg-gradient-to-r from-cortex-primary to-cortex-aqua rounded-xl flex items-center justify-center">
                <Building2 className="h-7 w-7 text-white" />
            </div>
          </div>
          {state.sidebarOpen && (
            <div className="ml-3">
                              <h1 className="text-xl font-bold text-gray-900">CortexQ</h1>
              <p className="text-sm text-gray-500">{state.organization?.name}</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <div className="space-y-1">
          {/* Organization Dashboard */}
          <button
            onClick={handleBackToOrganization}
            className={`w-full flex items-center px-4 py-3 rounded-xl transition-all duration-200 group ${
              state.currentView === 'organization'
                ? 'bg-cortex-grey text-cortex-primary shadow-sm border border-cortex-primary/20'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <Building2 className="h-5 w-5 flex-shrink-0" />
            {state.sidebarOpen && (
              <div className="ml-3 text-left">
                <p className="text-sm font-medium">Organization</p>
                <p className="text-xs text-gray-500">Dashboard & Settings</p>
              </div>
            )}
          </button>

          {/* Domains Section */}
          {state.sidebarOpen && (
            <div className="pt-4">
              <div className="flex items-center justify-between px-4 py-2">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Domains</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCreateDomain}
                  className="h-6 w-6 p-0"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="space-y-1">
                {state.domains.map((domain) => (
                  <button
                    key={domain.id}
                    onClick={() => handleSelectDomain(domain)}
                    className={`w-full flex items-center px-4 py-3 rounded-xl transition-all duration-200 group ${
                      state.selectedDomain?.id === domain.id && state.currentView === 'domain-workspace'
                        ? 'bg-cortex-grey text-cortex-primary shadow-sm border border-cortex-primary/20'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${domain.color || 'bg-gray-100'}`}>
                      <Globe className="h-4 w-4" />
                    </div>
                    <div className="ml-3 text-left">
                      <p className="text-sm font-medium">{domain.display_name || domain.name}</p>
                      <p className="text-xs text-gray-500 capitalize">{domain.is_active ? 'active' : 'inactive'}</p>
                    </div>
                  </button>
                ))}
                
                {/* Domain Sub-Navigation */}
                {state.selectedDomain && state.currentView === 'domain-workspace' && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <div className="px-4 py-2">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {state.selectedDomain.display_name || state.selectedDomain.name} Options
                      </h4>
                    </div>
                    <div className="space-y-1">
                      {[
                        { id: 'chat', label: 'AI Assistant', icon: MessageCircle, description: 'Chat with domain AI' },
                        { id: 'sources', label: 'Data Sources', icon: Database, description: 'Files and integrations' },
                        { id: 'analytics', label: 'Analytics', icon: BarChart3, description: 'Usage insights' },
                        { id: 'audit', label: 'Audit', icon: Shield, description: 'Activity logs' },
                        { id: 'settings', label: 'Settings', icon: Settings, description: 'Domain configuration' },
                      ].map((section) => (
                        <button
                          key={section.id}
                          onClick={() => handleDomainSectionChange(section.id as any)}
                          className={`w-full flex items-center px-6 py-2 rounded-lg transition-all duration-200 group ${
                            state.activeDomainSection === section.id
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                          }`}
                        >
                          <section.icon className={`h-4 w-4 flex-shrink-0 ${
                            state.activeDomainSection === section.id ? 'text-blue-600' : 'text-gray-400'
                          }`} />
                          <div className="ml-3 text-left">
                            <p className="text-sm font-medium">{section.label}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                {state.domains.length === 0 && (
                  <div className="px-4 py-8 text-center">
                    <Globe className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-500 mb-2">No domains yet</p>
                    <Button size="sm" onClick={handleCreateDomain}>
                      Create Domain
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* User Menu */}
      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center">
          <div className="h-8 w-8 bg-gray-300 rounded-full flex items-center justify-center">
            <User className="h-4 w-4 text-gray-600" />
          </div>
          {state.sidebarOpen && (
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">{state.user?.email}</p>
              <p className="text-xs text-gray-500 capitalize">{state.user?.roles?.[0] || 'user'}</p>
            </div>
          )}
          {state.sidebarOpen && (
            <button
              onClick={logout}
              className="p-1 text-gray-400 hover:text-gray-600"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderTopBar = () => (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setState(prev => ({ ...prev, sidebarOpen: !prev.sidebarOpen }))}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <Menu className="h-5 w-5" />
          </button>
          
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <span>{state.organization?.name}</span>
            {state.selectedDomain && (
              <>
                <span>/</span>
                <span className="text-gray-900 font-medium">{state.selectedDomain.display_name || state.selectedDomain.name}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search..."
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cortex-primary focus:border-transparent"
            />
          </div>
          
          <button className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 relative">
            <Bell className="h-5 w-5" />
            <span className="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full"></span>
          </button>
          
          <div className="relative">
            <button 
              className="flex items-center space-x-2 p-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              onClick={() => setState(prev => ({ ...prev, showUserDropdown: !prev.showUserDropdown }))}
            >
              <div className="h-6 w-6 bg-gray-300 rounded-full flex items-center justify-center">
                <User className="h-3 w-3 text-gray-600" />
              </div>
              <span className="text-sm font-medium">{state.user?.email || 'User'}</span>
              <ChevronDown className="h-4 w-4" />
            </button>
            
            {state.showUserDropdown && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                <button
                  onClick={() => {
                    handleShowUserProfile();
                    setState(prev => ({ ...prev, showUserDropdown: false }));
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                >
                  <Settings className="h-4 w-4" />
                  <span>Profile Settings</span>
                </button>
                <hr className="my-1" />
                <button
                  onClick={() => {
                    logout();
                    setState(prev => ({ ...prev, showUserDropdown: false }));
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderMainContent = () => {
    if (!state.organization) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Building2 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">No Organization Found</h2>
            <p className="text-gray-600 mb-4">
              You don't seem to be a member of any organization yet.
            </p>
            <Button 
              onClick={() => window.location.reload()}
              className="mr-2"
            >
              Refresh
            </Button>
            <Button 
              variant="ghost"
              onClick={logout}
            >
              Sign Out
            </Button>
          </div>
        </div>
      );
    }

    switch (state.currentView) {
      case 'organization':
        return (
          <OrganizationDashboard
            organization={state.organization}
            onCreateDomain={handleCreateDomain}
            onManageTeam={handleManageTeam}
            onViewBilling={handleViewBilling}
          />
        );
      
      case 'create-domain':
        return (
          <DomainCreationWizard
            organizationId={state.organization.id}
            onComplete={handleDomainCreated}
            onCancel={handleBackToOrganization}
          />
        );
      
      case 'domain-workspace':
        return state.selectedDomain ? (
          <DomainWorkspace
            domain={state.selectedDomain}
            activeSection={state.activeDomainSection}
            onSectionChange={handleDomainSectionChange}
            onEditDomain={() => {}}
            onDeleteDomain={() => {}}
          />
        ) : null;
      
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      {renderSidebar()}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        {renderTopBar()}

        {/* Content Area */}
        <main className="flex-1 p-6 overflow-auto">
          {renderMainContent()}
        </main>
      </div>

      {/* Modal Components */}
      {state.showTeamManagement && state.organization && (
        <TeamManagement
          organizationId={state.organization.id}
          onClose={handleCloseModals}
        />
      )}

      {state.showOrganizationSettings && state.organization && (
        <OrganizationSettings
          organization={state.organization}
          onClose={handleCloseModals}
          onOrganizationUpdate={handleOrganizationUpdate}
        />
      )}

      {state.showUserProfile && state.user && (
        <UserProfile
          user={state.user}
          onClose={handleCloseModals}
          onUserUpdate={handleUserUpdate}
        />
      )}
    </div>
  );
}

function LoginForm({ onLogin }: { onLogin: (email: string, password: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      if (isRegister) {
        // Handle registration (email as primary identifier)
        const response = await api.register({
          email,
          password,
        });
        
        if (response.success) {
          // Auto-login after successful registration
          await onLogin(email, password);
        } else {
          const errorMessage = typeof response.message === 'string' 
            ? response.message 
            : 'Registration failed';
          setError(errorMessage);
        }
      } else {
        // Handle login
        await onLogin(email, password);
      }
    } catch (error) {
      console.error('Authentication error:', error);
      const errorMessage = isRegister ? 'Registration failed' : 'Login failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
            <div className="min-h-screen bg-gradient-to-br from-cortex-grey to-white flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <div className="p-8">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <img 
                src="/LogoWord.png" 
                alt="CortexQ" 
                className="h-12 w-auto"
                onError={(e) => {
                  // Fallback to icon + text if logo doesn't load
                  e.currentTarget.style.display = 'none';
                  const fallback = e.currentTarget.nextElementSibling as HTMLElement;
                  if (fallback) fallback.classList.remove('hidden');
                }}
              />
              <div className="hidden h-12 w-12 bg-gradient-to-r from-cortex-primary to-cortex-aqua rounded-xl flex items-center justify-center">
                <Building2 className="h-6 w-6 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">CortexQ</h1>
            <p className="text-gray-600">
              {isRegister ? 'Create your account to get started' : 'Ask Smarter. Know Faster.'}
            </p>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 text-center">
              {isRegister ? 'Create Account' : 'Sign In'}
            </h2>
            <p className="text-sm text-gray-600 text-center mt-1">
              {isRegister 
                ? 'Enter your email and password to create your account' 
                : 'Enter your credentials to access your workspace'
              }
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}



            <Input
              label={isRegister ? "Email Address" : "Email"}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={isRegister ? "Enter your work email" : "Enter your email"}
              autoComplete="email"
              fullWidth
              required
            />
            
            <Input
              label={isRegister ? "Create Password" : "Password"}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isRegister ? "Create a secure password" : "Enter your password"}
              autoComplete={isRegister ? "new-password" : "current-password"}
              fullWidth
              required
            />

            <Button
              type="submit"
              loading={loading}
              className="w-full"
            >
              {isRegister ? 'Create Account' : 'Sign In'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
                setEmail('');
                setPassword('');
              }}
              className="text-sm text-cortex-primary hover:text-cortex-navy"
            >
              {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
} 