/**
 * Session Feedback Component - Pain/discomfort and general notes
 */
import { h } from 'preact';
import htm from 'htm';

import { updateSessionFeedback } from '../store.js';

const html = htm.bind(h);

export function SessionFeedback({ date, feedback }) {
    const handleChange = (field, value) => {
        updateSessionFeedback(date, { [field]: value });
    };

    return html`
        <div class="session-feedback">
            <h3 class="feedback-title">Session Feedback</h3>

            <div class="feedback-field">
                <label class="feedback-label">Pain / Discomfort (especially right knee)</label>
                <textarea
                    class="feedback-textarea"
                    placeholder="Note any pain, discomfort, or issues..."
                    value=${feedback.pain_discomfort || ''}
                    onInput=${(e) => handleChange('pain_discomfort', e.target.value)}
                />
            </div>

            <div class="feedback-field">
                <label class="feedback-label">General Notes</label>
                <textarea
                    class="feedback-textarea"
                    placeholder="How did the session feel overall?"
                    value=${feedback.general_notes || ''}
                    onInput=${(e) => handleChange('general_notes', e.target.value)}
                />
            </div>
        </div>
    `;
}
