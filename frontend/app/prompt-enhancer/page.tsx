'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Loader2, Wand2, Copy, Check } from 'lucide-react';

export default function PromptEnhancer() {
  const [userPrompt, setUserPrompt] = useState('');
  const [brand, setBrand] = useState('airtel');
  const [aspectRatio, setAspectRatio] = useState('1:1');
  
  // Modular Parameters
  const [gender, setGender] = useState('');
  const [backgroundType, setBackgroundType] = useState('');
  const [textureType, setTextureType] = useState('recycled_paper');
  const [activity, setActivity] = useState('');
  const [hairLength, setHairLength] = useState('medium');
  const [hairTexture, setHairTexture] = useState('straight');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    if (!userPrompt.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false);

    try {
      const res = await fetch('http://localhost:8000/v1/generator/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_prompt: userPrompt,
          brand,
          aspect_ratio: aspectRatio,
          gender: gender || null,
          background_type: backgroundType || null,
          texture_type: backgroundType === 'textured' ? textureType : null,
          activity: activity || null,
          hair_length: gender === 'male' ? hairLength : null,
          hair_texture: gender === 'male' ? hairTexture : null,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Failed to generate prompt');
      }

      setResult(data.data.enhanced_prompt);
    } catch (err: any) {
      setError(err.message || 'An error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-900 overflow-y-auto">
      <div className="h-16 px-8 flex items-center border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-10">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Wand2 className="w-6 h-6 text-purple-400" />
          Prompt Enhancer
        </h1>
      </div>

      <div className="p-8 max-w-6xl mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left Side: Form */}
        <div className="space-y-6 bg-slate-800/40 p-6 rounded-2xl border border-slate-700/50 shadow-xl">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">User Prompt Idea</label>
            <textarea
              className="w-full h-32 bg-slate-900/50 border border-slate-700 rounded-xl p-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none transition-all"
              placeholder="E.g., A modern city skyline at night with fast internet vibes..."
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Brand</label>
              <select
                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              >
                <option value="airtel">Airtel</option>
                <option value="robi">Robi</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Aspect Ratio</label>
              <select
                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                value={aspectRatio}
                onChange={(e) => setAspectRatio(e.target.value)}
              >
                <option value="1:1">1:1 (Square)</option>
                <option value="16:9">16:9 (Landscape)</option>
                <option value="9:16">9:16 (Portrait Story)</option>
                <option value="4:5">4:5 (Vertical Post)</option>
              </select>
            </div>
          </div>

          <div className="space-y-4 pt-2 border-t border-slate-700/50">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Modular Parameters</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Subject Gender</label>
                <select
                  className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                >
                  <option value="">None (Auto)</option>
                  <option value="male">Male (Fair, Thin, Late-Teen)</option>
                  <option value="female">Female (Fair, Thin, Late-Teen)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Background Type</label>
                <select
                  className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  value={backgroundType}
                  onChange={(e) => setBackgroundType(e.target.value)}
                >
                  <option value="">None (Auto)</option>
                  <option value="solid">Solid</option>
                  <option value="doodly">🔴 Doodly — Radiating (sparse, from phone)</option>
                  <option value="doodly_scatter">✦ Doodly — Scatter (icons all around subject)</option>
                  <option value="textured">Textured</option>
                </select>
              </div>
            </div>

            {backgroundType === 'textured' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                <label className="block text-sm font-medium text-slate-300 mb-2">Texture Style</label>
                <select
                  className="w-full bg-blue-500/10 border border-blue-500/30 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={textureType}
                  onChange={(e) => setTextureType(e.target.value)}
                >
                  <option value="recycled_paper">Subtle Recycled Paper</option>
                  <option value="linen_weave">Soft Linen Weave</option>
                  <option value="fine_grain_plaster">Fine-Grain Plaster</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Primary Activity</label>
              <select
                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                value={activity}
                onChange={(e) => setActivity(e.target.value)}
              >
                <option value="">None (Auto)</option>
                <option value="gaming">Gaming</option>
                <option value="music">Music</option>
                <option value="streaming">Streaming/Movies</option>
                <option value="ecommerce">Ecommerce/Shopping</option>
                <option value="social">Social/Creator</option>
                <option value="voice_calling">Voice Calling</option>
                <option value="browsing">Browsing</option>
                <option value="e_learning">📚 E-Learning / Online Study</option>
              </select>
            </div>

            {gender === 'male' && (
              <div className="grid grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Hair Length</label>
                  <select
                    className="w-full bg-purple-500/10 border border-purple-500/30 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    value={hairLength}
                    onChange={(e) => setHairLength(e.target.value)}
                  >
                    <option value="medium">Medium</option>
                    <option value="long">Long</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Hair Texture</label>
                  <select
                    className="w-full bg-purple-500/10 border border-purple-500/30 rounded-xl p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    value={hairTexture}
                    onChange={(e) => setHairTexture(e.target.value)}
                  >
                    <option value="straight">Straight</option>
                    <option value="curly">Curly</option>
                    <option value="wavy_mixed">Wavy/Mixed</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !userPrompt.trim()}
            className="w-full py-4 rounded-xl bg-linear-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-lg flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-purple-500/20"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
            {loading ? 'Enhancing...' : 'Enhance Prompt'}
          </button>
        </div>

        {/* Right Side: Result */}
        <div className="h-[600px] flex flex-col bg-slate-800/40 rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden relative">
          <div className="p-4 border-b border-slate-700/50 bg-slate-800/80 flex items-center justify-between">
            <h2 className="font-semibold text-slate-200">Generated AI Prompt</h2>
            <button
              onClick={copyToClipboard}
              disabled={!result}
              className="p-2 rounded-lg bg-slate-700/50 hover:bg-slate-600 text-slate-300 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2 text-sm"
              title="Copy to clipboard"
            >
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          
          <div className="flex-1 overflow-auto p-6 relative group">
            {error ? (
              <div className="text-red-400 bg-red-400/10 p-4 rounded-lg border border-red-500/20">
                {error}
              </div>
            ) : result ? (
              <div className="prose prose-invert prose-p:leading-relaxed prose-headings:text-slate-100 max-w-none text-slate-300 pb-10">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-4 opacity-50">
                <Wand2 className="w-12 h-12" />
                <p>Provide a short idea to generate an enriched prompt.</p>
              </div>
            )}
            
            {loading && (
              <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-[2px] flex items-center justify-center z-10 transition-all">
                <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
