import React, { useState } from 'react';
import { UploadArea } from './components/UploadArea';
import { Editor } from './components/Editor';
import { api, UploadResponse, Segment } from './utils/api';

function App() {
  const [session, setSession] = useState<UploadResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [segments, setSegments] = useState<Segment[]>([]);

  const handleFileSelected = async (file: File) => {
    setIsLoading(true);
    try {
      const res = await api.upload(file);
      setSession(res);
      setSegments(res.segments);
    } catch (error) {
      console.error("Upload failed", error);
      alert("Upload failed. See console.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTranslateAll = async () => {
    if (!session) return;
    setIsTranslating(true);
    try {
      // Collect IDs of segments that need translation (new or empty target)
      // Or just translate all that are not 'final'?
      // For MVP, translated all currently displayed segments
      const ids = segments.map(s => s.id);
      const res = await api.translate(session.session_id, ids, 'en', 'zh-CN');

      // Update local state
      const resultsMap = new Map(res.results.map(r => [r.id, r]));

      setSegments(prev => prev.map(s => {
        const update = resultsMap.get(s.id);
        if (update) {
          return { ...s, target: update.target, state: 'translated', errors: update.errors };
        }
        return s;
      }));

    } catch (error) {
      console.error("Translation failed", error);
      alert("Translation failed.");
    } finally {
      setIsTranslating(false);
    }
  };

  const handleUpdateSegment = (id: string, text: string) => {
    setSegments(prev => prev.map(s => s.id === id ? { ...s, target: text } : s));
    // Optionally sync to backend periodically
    if (session) {
      // Fire and forget update
      api.updateSegment(session.session_id, id, text);
    }
  };

  const handleDownload = () => {
    if (session) {
      window.open(api.downloadUrl(session.session_id), '_blank');
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 font-sans text-gray-900">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">XLIFF AI Assistant</h1>
          {session && (
            <div className="space-x-4">
              <button
                onClick={handleTranslateAll}
                disabled={isTranslating}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors"
              >
                {isTranslating ? 'Translating...' : 'Translate All'}
              </button>
              <button
                onClick={handleDownload}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              >
                Export XLIFF
              </button>
            </div>
          )}
        </div>
      </header>
      <main>
        <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          {!session ? (
            <div className="py-12">
              <UploadArea onFileSelected={handleFileSelected} isLoading={isLoading} />
            </div>
          ) : (
            <div className="py-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-medium">File: {session.filename}</h2>
                <span className="text-sm text-gray-500">{segments.length} segments</span>
              </div>
              <Editor segments={segments} onUpdate={handleUpdateSegment} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
