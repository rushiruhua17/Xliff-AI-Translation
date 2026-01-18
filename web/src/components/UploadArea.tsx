import React from 'react';
// For now, simple input.
// Let's use simple input to avoid extra deps if possible, or I can install it.
// Installing clsx and tailwind-merge was for utils.
// Let's stick to standard input for MVP to save time on deps, or use drag events manually.
// Let's use a simple detailed design.

interface UploadAreaProps {
    onFileSelected: (file: File) => void;
    isLoading: boolean;
}

export const UploadArea: React.FC<UploadAreaProps> = ({ onFileSelected, isLoading }) => {
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            onFileSelected(e.target.files[0]);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors">
            <div className="text-center">
                <h3 className="text-lg font-medium text-gray-900">Upload XLIFF File</h3>
                <p className="mt-1 text-sm text-gray-500">Drag and drop or click to select</p>
            </div>
            <input
                type="file"
                accept=".xlf,.xliff"
                className="mt-4 block w-full text-sm text-slate-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-indigo-50 file:text-indigo-700
                  hover:file:bg-indigo-100"
                onChange={handleFileChange}
                disabled={isLoading}
            />
            {isLoading && <p className="mt-4 text-indigo-600 animate-pulse">Processing...</p>}
        </div>
    );
};
