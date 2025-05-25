'use client';

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  Mail, 
  Shield, 
  MoreVertical, 
  Edit, 
  Trash2, 
  X,
  Check,
  AlertCircle
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { apiClient } from '../../utils/api';

interface Member {
  id: string;
  user_id: string;
  username: string;
  email: string;
  full_name?: string;
  role: string;
  permissions: string[];
  joined_at: string;
  last_active?: string;
  is_active: boolean;
}

interface TeamManagementProps {
  organizationId: string;
  onClose: () => void;
}

const TeamManagement: React.FC<TeamManagementProps> = ({ organizationId, onClose }) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('user');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [editingMember, setEditingMember] = useState<string | null>(null);
  const [newRole, setNewRole] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');

  useEffect(() => {
    loadMembers();
    checkConnection();
  }, [organizationId]);

  const checkConnection = async () => {
    try {
      const response = await apiClient.getHealthStatus();
      setConnectionStatus(response.success ? 'connected' : 'disconnected');
    } catch (error) {
      setConnectionStatus('disconnected');
    }
  };

  const loadMembers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getOrganizationMembers(organizationId);
      if (response.success) {
        setMembers(response.data);
        setConnectionStatus('connected');
      } else {
        setError(response.message || 'Failed to load team members');
        if (response.message?.includes('Connection failed')) {
          setConnectionStatus('disconnected');
        }
      }
    } catch (error) {
      console.error('Failed to load members:', error);
      setError('Failed to load team members. Please check your connection.');
      setConnectionStatus('disconnected');
    } finally {
      setLoading(false);
    }
  };

  const handleInviteMember = async () => {
    if (!inviteEmail.trim()) {
      setError('Email is required');
      return;
    }

    setInviteLoading(true);
    setError(null);
    
    try {
      const response = await apiClient.inviteOrganizationMember(organizationId, {
        email: inviteEmail,
        role: inviteRole,
      });
      
      if (response.success) {
        setSuccess(`Invitation sent to ${inviteEmail}`);
        setInviteEmail('');
        setInviteRole('user');
        setShowInviteModal(false);
        // Note: Invited users won't appear in the list until they accept
      } else {
        setError(response.message || 'Failed to send invitation');
      }
    } catch (error) {
      console.error('Failed to invite member:', error);
      setError('Failed to send invitation');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleUpdateRole = async (memberId: string, role: string) => {
    try {
      const response = await apiClient.updateOrganizationMember(organizationId, memberId, role);
      if (response.success) {
        setMembers(prev => prev.map(member => 
          member.id === memberId ? { ...member, role } : member
        ));
        setEditingMember(null);
        setSuccess('Member role updated successfully');
      } else {
        setError(response.message || 'Failed to update member role');
      }
    } catch (error) {
      console.error('Failed to update member:', error);
      setError('Failed to update member role');
    }
  };

  const handleRemoveMember = async (memberId: string, memberEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${memberEmail} from the organization?`)) {
      return;
    }

    try {
      const response = await apiClient.removeOrganizationMember(organizationId, memberId);
      if (response.success) {
        setMembers(prev => prev.filter(member => member.id !== memberId));
        setSuccess('Member removed successfully');
      } else {
        setError(response.message || 'Failed to remove member');
      }
    } catch (error) {
      console.error('Failed to remove member:', error);
      setError('Failed to remove member');
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'owner': return 'bg-purple-100 text-purple-800';
      case 'admin': return 'bg-red-100 text-red-800';
      case 'manager': return 'bg-blue-100 text-blue-800';
      case 'user': return 'bg-green-100 text-green-800';
      case 'viewer': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading team members...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <Users className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">Team Management</h2>
            {/* Connection Status Indicator */}
            <div className="flex items-center space-x-2">
              <div className={`h-2 w-2 rounded-full ${
                connectionStatus === 'connected' ? 'bg-green-500' : 
                connectionStatus === 'disconnected' ? 'bg-red-500' : 
                'bg-yellow-500'
              }`}></div>
              <span className="text-xs text-gray-500">
                {connectionStatus === 'connected' ? 'Connected' : 
                 connectionStatus === 'disconnected' ? 'Disconnected' : 
                 'Checking...'}
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <Button onClick={() => setShowInviteModal(true)} icon={<UserPlus className="h-4 w-4" />}>
              Invite Member
            </Button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center">
            <AlertCircle className="h-5 w-5 text-red-600 mr-3" />
            <span className="text-red-800 flex-1">{error}</span>
            {connectionStatus === 'disconnected' && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setError(null);
                  loadMembers();
                  checkConnection();
                }}
                className="mr-2"
              >
                Retry
              </Button>
            )}
            <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
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

        {/* Members List */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          <div className="space-y-4">
            {members.map((member) => (
              <div key={member.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="h-10 w-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center">
                      <span className="text-white font-medium">
                        {(member.full_name || member.username || member.email).charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">
                        {member.full_name || member.username}
                      </h4>
                      <p className="text-sm text-gray-500">{member.email}</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getRoleColor(member.role)}`}>
                          {member.role}
                        </span>
                        <span className="text-xs text-gray-500">
                          Joined {formatDate(member.joined_at)}
                        </span>
                        {member.last_active && (
                          <span className="text-xs text-gray-500">
                            Last active {formatDate(member.last_active)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {editingMember === member.id ? (
                      <div className="flex items-center space-x-2">
                        <select
                          value={newRole}
                          onChange={(e) => setNewRole(e.target.value)}
                          className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                        >
                          <option value="viewer">Viewer</option>
                          <option value="user">User</option>
                          <option value="manager">Manager</option>
                          <option value="admin">Admin</option>
                        </select>
                        <Button
                          size="sm"
                          onClick={() => handleUpdateRole(member.id, newRole)}
                          icon={<Check className="h-3 w-3" />}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditingMember(null)}
                          icon={<X className="h-3 w-3" />}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        {member.role !== 'owner' && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingMember(member.id);
                                setNewRole(member.role);
                              }}
                              icon={<Edit className="h-3 w-3" />}
                            >
                              Edit Role
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRemoveMember(member.id, member.email)}
                              icon={<Trash2 className="h-3 w-3" />}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              Remove
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {members.length === 0 && (
              <div className="text-center py-8">
                <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No team members</h3>
                <p className="text-gray-500 mb-4">Invite team members to collaborate on this organization.</p>
                <Button onClick={() => setShowInviteModal(true)}>Invite Your First Member</Button>
              </div>
            )}
          </div>
        </div>

        {/* Invite Modal */}
        {showInviteModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-60">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Invite Team Member</h3>
                <button
                  onClick={() => setShowInviteModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    icon={<Mail className="h-4 w-4" />}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="viewer">Viewer - Can view content only</option>
                    <option value="user">User - Can view and interact</option>
                    <option value="manager">Manager - Can manage content</option>
                    <option value="admin">Admin - Full access</option>
                  </select>
                </div>

                <div className="flex space-x-3 pt-4">
                  <Button
                    onClick={handleInviteMember}
                    disabled={inviteLoading}
                    className="flex-1"
                  >
                    {inviteLoading ? 'Sending...' : 'Send Invitation'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowInviteModal(false)}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TeamManagement; 