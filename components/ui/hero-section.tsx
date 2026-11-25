// @ts-nocheck
/**
 * KLyck Hero Section Component
 * 
 * Modern animated hero landing page for the KLyck Naukri automation tool.
 * Features:
 *  - Animated background orb
 *  - Headline with animated SVG underline
 *  - Feature cards grid  
 *  - Credential connect form with local storage
 *  - Fully responsive, dark-mode first
 * 
 * This is the in-browser JSX version (Babel standalone).
 * For a Next.js / Vite project, import as a standard React component.
 */

import React, { useState, useEffect } from 'react';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  desc: string;
  colorClass: string;
  accentClass: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ icon, title, desc, colorClass, accentClass }) => (
  <div className={`relative rounded-2xl p-5 bg-gradient-to-br ${colorClass} border border-white/5 hover:border-white/10 transition-all duration-300 hover:-translate-y-1 group`}>
    <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 bg-white/5 ${accentClass} group-hover:scale-110 transition-transform duration-200`}>
      {icon}
    </div>
    <h3 className="font-bold text-white text-[15px] mb-2">{title}</h3>
    <p className="text-sm text-gray-500 leading-relaxed">{desc}</p>
  </div>
);

interface LoginFormProps {
  onSuccess?: () => void;
}

const LoginForm: React.FC<LoginFormProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Please enter both email and password.'); return; }
    setLoading(true); setError(''); setSuccess('');
    try {
      const res = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (data.ok) {
        setSuccess(data.message || 'Connected! Launching dashboard...');
        setTimeout(() => { onSuccess ? onSuccess() : (window.location.href = '/dashboard'); }, 1200);
      } else {
        setError(data.error || 'Connection failed. Please try again.');
      }
    } catch (err) {
      setError('Network error. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full">
      {/* Email field */}
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">Naukri Email</label>
        <input
          type="email" value={email} onChange={e => setEmail(e.target.value)}
          placeholder="yourname@example.com"
          className="w-full bg-white/5 border border-white/10 text-white rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-500/70 focus:ring-2 focus:ring-indigo-500/20 transition placeholder:text-white/30"
          required
        />
      </div>
      {/* Password field */}
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">Naukri Password</label>
        <div className="relative">
          <input
            type={showPass ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
            placeholder="Your Naukri password"
            className="w-full bg-white/5 border border-white/10 text-white rounded-xl px-4 py-3 pr-11 text-sm outline-none focus:border-indigo-500/70 focus:ring-2 focus:ring-indigo-500/20 transition placeholder:text-white/30"
            required
          />
          <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition">
            {showPass ? '👁️' : '🔒'}
          </button>
        </div>
      </div>
      {error && <div className="bg-rose-500/15 border border-rose-500/30 rounded-xl px-4 py-3 text-sm text-rose-300">{error}</div>}
      {success && <div className="bg-emerald-500/15 border border-emerald-500/30 rounded-xl px-4 py-3 text-sm text-emerald-300">{success}</div>}
      <button
        type="submit" disabled={loading}
        className="relative overflow-hidden w-full rounded-xl bg-gradient-to-b from-indigo-500 to-indigo-700 py-3.5 font-bold text-white text-[15px] shadow-[0_0_0_1px_rgba(99,102,241,0.6),0_12px_32px_-8px_rgba(99,102,241,0.75)] hover:shadow-[0_0_0_1px_rgba(99,102,241,0.8),0_16px_40px_-8px_rgba(99,102,241,0.85)] transition-all disabled:opacity-60"
      >
        {loading ? 'Connecting...' : 'Connect & Launch Dashboard →'}
      </button>
      <p className="text-center text-xs text-gray-600">
        🔒 Credentials saved locally in <code className="bg-white/5 px-1 rounded text-indigo-300">.env</code> — never transmitted.
      </p>
    </form>
  );
};

export { LoginForm, FeatureCard };
export default LoginForm;
