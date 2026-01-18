import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export interface Segment {
    id: string;
    source: string;
    target: string;
    state: string;
    tags_map: Record<string, string>;
    errors?: string[];
}

export interface UploadResponse {
    session_id: string;
    segments: Segment[];
    filename: string;
}

export interface TranslateResponse {
    results: {
        id: string;
        target: string;
        errors: string[];
    }[];
}

export const api = {
    upload: async (file: File): Promise<UploadResponse> => {
        const formData = new FormData();
        formData.append('file', file);
        const res = await axios.post(`${API_BASE_URL}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return res.data;
    },

    translate: async (sessionId: string, segmentIds: string[], sourceLang: string, targetLang: string) => {
        const res = await axios.post<TranslateResponse>(`${API_BASE_URL}/translate`, {
            session_id: sessionId,
            segment_ids: segmentIds,
            source_lang: sourceLang,
            target_lang: targetLang
        });
        return res.data;
    },

    updateSegment: async (sessionId: string, segmentId: string, targetText: string) => {
        const res = await axios.post(`${API_BASE_URL}/update_segment`, {
            session_id: sessionId,
            segment_id: segmentId,
            target_text: targetText
        });
        return res.data;
    },

    downloadUrl: (sessionId: string) => `${API_BASE_URL}/download/${sessionId}`
};
