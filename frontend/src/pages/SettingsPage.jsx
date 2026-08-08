import React, { useState, useEffect } from 'react';
import Toggle from '../components/ui/Toggle';
import { getAlertSettings, updateAlertSettings } from '../api/client';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    emailAlerts: true,
    emailAddress: 'safety@company.com',
    emailCooldown: '300',
    whatsappAlerts: false,
    whatsappNumber: '',
    whatsappCooldown: '300',
    confidenceThreshold: 50,
  });

  const REQUIRED_PPE = [
    { name: 'Safety Helmet', icon: 'health_and_safety' },
    { name: 'High-Visibility Vest', icon: 'dry_cleaning' },
    { name: 'Face Mask', icon: 'masks' },
  ];
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' or 'error'

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await getAlertSettings();
        const data = res.data;
        setSettings(prev => ({
          ...prev,
          emailAlerts: data.email_enabled ?? prev.emailAlerts,
          emailAddress: (data.email_recipients && data.email_recipients.length > 0) ? data.email_recipients.join(', ') : prev.emailAddress,
          emailCooldown: data.email_cooldown ? data.email_cooldown.toString() : prev.emailCooldown,
          whatsappAlerts: data.whatsapp_enabled ?? prev.whatsappAlerts,
          whatsappNumber: data.whatsapp_recipient ?? prev.whatsappNumber,
          whatsappCooldown: data.whatsapp_cooldown ? data.whatsapp_cooldown.toString() : prev.whatsappCooldown,
          confidenceThreshold: data.confidence_threshold ? Math.round(data.confidence_threshold * 100) : prev.confidenceThreshold,
        }));
      } catch (error) {
        console.error("Failed to fetch settings", error);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const payload = {
        email_enabled: settings.emailAlerts,
        email_recipients: settings.emailAddress.split(',').map(e => e.trim()).filter(e => e),
        email_cooldown: parseInt(settings.emailCooldown, 10),
        whatsapp_enabled: settings.whatsappAlerts,
        whatsapp_recipient: settings.whatsappNumber,
        whatsapp_cooldown: parseInt(settings.whatsappCooldown, 10),
        confidence_threshold: settings.confidenceThreshold / 100.0
      };
      await updateAlertSettings(payload);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      console.error("Failed to save settings", error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="max-w-3xl space-y-6 pb-12">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <h2 className="font-headline-lg text-sg-on-surface">System Configuration</h2>
        <div className="flex items-center gap-4">
          {saveStatus === 'success' && (
            <span className="flex items-center gap-1 text-sg-tertiary font-body-md font-medium">
              <span className="material-symbols-outlined text-lg">check_circle</span> Saved successfully
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="flex items-center gap-1 text-sg-error font-body-md font-medium">
              <span className="material-symbols-outlined text-lg">cancel</span> Error saving
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={`flex items-center gap-2 text-sg-on-primary px-6 py-2 rounded-lg transition-colors font-body-md font-bold shadow-[0_0_15px_rgba(255,182,147,0.15)] ${
              isSaving ? 'bg-sg-primary/50' : 'bg-sg-primary hover:bg-sg-primary-fixed-dim'
            }`}
          >
            <span className="material-symbols-outlined text-lg">save</span>
            <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
          </button>
        </div>
      </div>

      {/* Email Alerts Section */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low flex items-center gap-3">
          <span className="material-symbols-outlined text-sg-primary text-xl">mail</span>
          <h3 className="font-headline-sm text-sg-on-surface">Email Alerts</h3>
        </div>
        <div className="p-6 space-y-6">
          <Toggle
            label="Enable Email Notifications"
            checked={settings.emailAlerts}
            onChange={(e) => handleChange('emailAlerts', e.target.checked)}
          />
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="font-body-md text-sg-on-surface-variant font-medium">Recipient Email</label>
              <input
                type="email"
                value={settings.emailAddress}
                onChange={(e) => handleChange('emailAddress', e.target.value)}
                disabled={!settings.emailAlerts}
                className="w-full bg-sg-surface-container border border-sg-outline-variant rounded-lg px-4 py-2 text-sg-on-surface font-body-md focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary disabled:opacity-50 transition-colors"
              />
            </div>
            <div className="space-y-2">
              <label className="font-body-md text-sg-on-surface-variant font-medium">Cooldown Period (seconds)</label>
              <input
                type="number"
                value={settings.emailCooldown}
                onChange={(e) => handleChange('emailCooldown', e.target.value)}
                disabled={!settings.emailAlerts}
                className="w-full bg-sg-surface-container border border-sg-outline-variant rounded-lg px-4 py-2 text-sg-on-surface font-body-md focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary disabled:opacity-50 transition-colors"
              />
            </div>
          </div>
          <button disabled={!settings.emailAlerts} className="font-body-md text-sg-primary hover:underline disabled:opacity-50 disabled:no-underline transition-opacity">
            Send Test Email
          </button>
        </div>
      </div>

      {/* WhatsApp Alerts Section */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low flex items-center gap-3">
          <span className="material-symbols-outlined text-sg-primary text-xl">chat</span>
          <h3 className="font-headline-sm text-sg-on-surface">WhatsApp Alerts</h3>
        </div>
        <div className="p-6 space-y-6">
          <Toggle
            label="Enable WhatsApp Notifications"
            checked={settings.whatsappAlerts}
            onChange={(e) => handleChange('whatsappAlerts', e.target.checked)}
          />
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="font-body-md text-sg-on-surface-variant font-medium">Phone Number</label>
              <input
                type="text"
                placeholder="+1234567890"
                value={settings.whatsappNumber}
                onChange={(e) => handleChange('whatsappNumber', e.target.value)}
                disabled={!settings.whatsappAlerts}
                className="w-full bg-sg-surface-container border border-sg-outline-variant rounded-lg px-4 py-2 text-sg-on-surface font-body-md focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary disabled:opacity-50 transition-colors placeholder:text-sg-surface-bright"
              />
            </div>
            <div className="space-y-2">
              <label className="font-body-md text-sg-on-surface-variant font-medium">Cooldown Period (seconds)</label>
              <input
                type="number"
                value={settings.whatsappCooldown}
                onChange={(e) => handleChange('whatsappCooldown', e.target.value)}
                disabled={!settings.whatsappAlerts}
                className="w-full bg-sg-surface-container border border-sg-outline-variant rounded-lg px-4 py-2 text-sg-on-surface font-body-md focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary disabled:opacity-50 transition-colors"
              />
            </div>
          </div>
          <button disabled={!settings.whatsappAlerts} className="font-body-md text-sg-primary hover:underline disabled:opacity-50 disabled:no-underline transition-opacity">
            Send Test Message
          </button>
        </div>
      </div>

      {/* Detection Settings Section */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low flex items-center gap-3">
          <span className="material-symbols-outlined text-sg-primary text-xl">tune</span>
          <h3 className="font-headline-sm text-sg-on-surface">Detection Settings</h3>
        </div>
        <div className="p-6 space-y-8">
          <div>
            <div className="flex justify-between mb-2">
              <label className="font-body-md text-sg-on-surface font-medium">Confidence Threshold</label>
              <span className="font-data-mono text-sg-primary">{settings.confidenceThreshold}%</span>
            </div>
            <input
              type="range"
              min="10" max="95" step="5"
              value={settings.confidenceThreshold}
              onChange={(e) => handleChange('confidenceThreshold', parseInt(e.target.value))}
              className="w-full accent-sg-primary-container h-2 bg-sg-surface-container-lowest rounded-lg appearance-none cursor-pointer"
            />
            <p className="font-body-md text-sg-on-surface-variant mt-2">Lower values detect more objects but may increase false positives.</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="font-body-md text-sg-on-surface font-medium block">Always Required PPE</label>
              <p className="font-body-md text-sg-on-surface-variant text-sm mt-1">
                These items are always required and cannot be disabled.
              </p>
            </div>
            <ul className="space-y-2">
              {REQUIRED_PPE.map((item) => (
                <li
                  key={item.name}
                  className="flex items-center gap-3 px-4 py-2.5 bg-sg-surface-container-low border border-sg-outline-variant rounded-lg"
                >
                  <span className="material-symbols-outlined text-sg-tertiary">check_circle</span>
                  <span className="font-body-lg text-sg-on-surface flex-1">{item.name}</span>
                  <span className="font-label-caps text-sg-on-surface-variant">Required</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
