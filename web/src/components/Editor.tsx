import React from 'react';
import { Segment } from '../utils/api';

interface EditorProps {
    segments: Segment[];
    onUpdate: (id: string, text: string) => void;
}

export const Editor: React.FC<EditorProps> = ({ segments, onUpdate }) => {
    const renderContentWithTags = (text: string) => {
        // Simple regex to highlight {n}
        const parts = text.split(/(\{\d+\})/g);
        return parts.map((part, i) => {
            if (part.match(/^\{\d+\}$/)) {
                return <span key={i} className="px-1 mx-0.5 rounded bg-amber-200 text-amber-800 font-mono text-xs">{part}</span>;
            }
            return part;
        });
    };

    return (
        <div className="w-full overflow-x-auto shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
            <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                    <tr>
                        <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">ID</th>
                        <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Source</th>
                        <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Target</th>
                        <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                    {segments.map((segment) => (
                        <tr key={segment.id}>
                            <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">{segment.id}</td>
                            <td className="px-3 py-4 text-sm text-gray-500 whitespace-pre-wrap max-w-md">
                                {renderContentWithTags(segment.source)}
                            </td>
                            <td className="px-3 py-4 text-sm text-gray-500">
                                <textarea
                                    className="w-full min-w-[300px] border-gray-300 rounded shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                                    rows={Math.max(2, Math.ceil(segment.target.length / 40))}
                                    value={segment.target}
                                    onChange={(e) => onUpdate(segment.id, e.target.value)}
                                />
                                {segment.errors && segment.errors.length > 0 && (
                                    <div className="mt-1 text-xs text-red-600">
                                        {segment.errors.map((e, i) => <div key={i}>{e}</div>)}
                                    </div>
                                )}
                            </td>
                            <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                                <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${segment.state === 'translated' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                    }`}>
                                    {segment.state}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};
